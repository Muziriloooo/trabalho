from io import BytesIO

from flask import Blueprint, abort, flash, redirect, render_template, request, send_file, url_for
from flask_login import current_user
from sqlalchemy import select

from ..core.permissions import console_required, organization_admin_required, visible_sites
from ..extensions import db, limiter
from ..models import OrganizationBranding, ReportRun, Site
from ..services import analytics, reports as service
from ..services.audit import audit
from ..services.persistence import commit
from .forms import ExportForm, KINDS, LogoForm, ReportForm, SOURCES

bp=Blueprint('reports',__name__,url_prefix='/reports')


def authorize_report(report):
    if not report or report.organization_id!=current_user.organization_id:abort(404)
    if report.generated_by!=current_user.id and current_user.role!='organization_admin':abort(404)
    if report.kind=='audit' and current_user.role!='organization_admin':abort(403)
    visible=set(db.session.scalars(visible_sites().with_only_columns(Site.id)).all())
    if not set(report.site_ids)<=visible:abort(404)
    return report


def own_report(report_id):
    return authorize_report(db.session.get(ReportRun,report_id))


@bp.route('',methods=['GET','POST'])
@console_required
@limiter.limit('10 per minute',methods=['POST'],key_func=lambda:current_user.get_id())
def index():
    form=ReportForm()
    sites=db.session.scalars(visible_sites().order_by(Site.name)).all()
    form.site_id.choices=[(0,'Todas no meu escopo')]+[(s.id,s.name) for s in sites]
    if current_user.role!='organization_admin':form.kind.choices=[(key,label) for key,label in KINDS.items() if key!='audit']
    if form.validate_on_submit():
        if form.kind.data=='audit' and (form.site_id.data or form.source.data!='all'):
            form.kind.errors=['Auditoria administrativa abrange a organização: selecione todas as unidades e todas as fontes.']
        else:
            filters=analytics.Filters.from_form(form)
            try:data=analytics.build(filters)
            except analytics.CapacityExceeded as error:form.end.errors=[str(error)]
            else:
                branding=db.session.scalar(select(OrganizationBranding).where(OrganizationBranding.organization_id==current_user.organization_id))
                report=ReportRun(organization_id=current_user.organization_id,generated_by=current_user.id,
                    organization_name=current_user.organization.name,generator_name=current_user.email,kind=form.kind.data,purpose=form.purpose.data,
                    start_date=form.start.data,end_date=form.end.data,source=form.source.data,site_ids=data['site_ids'],
                    payload=service.payload(form.kind.data,data,filters,current_user.organization_id),logo_png=branding.logo_png if branding else None)
                db.session.add(report);db.session.flush();audit('report.generated',report)
                if commit():return redirect(url_for('reports.detail',report_id=report.id))
    recent=db.session.scalars(select(ReportRun).where(ReportRun.organization_id==current_user.organization_id,
            ReportRun.generated_by==current_user.id).order_by(ReportRun.id.desc()).limit(20)).all()
    visible_ids={s.id for s in sites}
    recent=[r for r in recent if set(r.site_ids)<=visible_ids and (r.kind!='audit' or current_user.role=='organization_admin')]
    return render_template('reports/index.html',title='Relatórios',active_slug='reports',form=form,recent=recent,kinds=KINDS),422 if form.is_submitted() else 200


@bp.get('/<int:report_id>')
@console_required
def detail(report_id):
    report=own_report(report_id)
    return render_template('reports/detail.html',title=KINDS[report.kind],active_slug='reports',report=report,kinds=KINDS,sources=SOURCES,form=ExportForm())


@bp.post('/<int:report_id>/export/<format>')
@console_required
@limiter.limit('10 per minute',key_func=lambda:current_user.get_id())
def export(report_id,format):
    report=own_report(report_id)
    if format not in {'csv','pdf'}:abort(404)
    form=ExportForm()
    if not form.validate_on_submit():abort(400)
    content=service.csv_bytes(report) if format=='csv' else service.pdf_bytes(report,KINDS[report.kind])
    audit('report.exported_'+format,report)
    if not commit():abort(409)
    return send_file(BytesIO(content),mimetype='text/csv; charset=utf-8' if format=='csv' else 'application/pdf',as_attachment=True,
                     download_name=f'sentinela-{report.identifier}.{format}',max_age=0)


@bp.route('/branding',methods=['GET','POST'])
@organization_admin_required
def branding():
    form=LogoForm()
    row=db.session.scalar(select(OrganizationBranding).where(OrganizationBranding.organization_id==current_user.organization_id))
    if form.validate_on_submit():
        try:
            if form.remove.data:
                if row:db.session.delete(row)
                resource=current_user.organization
            else:
                if not form.logo.data:raise ValueError('Selecione um logo ou marque a remoção.')
                data=service.normalize_logo(form.logo.data)
                row=row or OrganizationBranding(organization_id=current_user.organization_id)
                row.logo_png=data;db.session.add(row);db.session.flush();resource=row
            audit('report.branding_updated',resource)
            if commit():return redirect(url_for('reports.index'))
        except ValueError as error:form.logo.errors=[str(error)]
    return render_template('reports/branding.html',title='Logo da organização',active_slug='reports',form=form,has_logo=bool(row)),422 if form.is_submitted() else 200


@bp.get('/logo')
@console_required
def logo():
    row=db.session.scalar(select(OrganizationBranding).where(OrganizationBranding.organization_id==current_user.organization_id))
    if not row:abort(404)
    return send_file(BytesIO(row.logo_png),mimetype='image/png',max_age=0)


@bp.get('/<int:report_id>/logo')
@console_required
def report_logo(report_id):
    report=own_report(report_id)
    if not report.logo_png:abort(404)
    return send_file(BytesIO(report.logo_png),mimetype='image/png',max_age=0)
