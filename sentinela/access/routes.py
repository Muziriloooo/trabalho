from flask import Blueprint, abort, flash, redirect, render_template, url_for
from flask_login import current_user
from sqlalchemy import select

from ..core.forms import ConfirmationForm
from ..core.permissions import console_required, organization_admin_required, visible_sites
from ..extensions import db, limiter
from ..models import AccessCredential, AccessEvent, AccessPermission, AccessPoint, AccessSubject, Site, utcnow
from ..services.access import REASONS, decide, issue
from ..services.audit import audit
from ..services.persistence import commit
from .forms import DecisionForm, IssueForm, PermissionForm, PointForm, SubjectForm

bp = Blueprint("access", __name__, url_prefix="/access")


def points_query():
    return select(AccessPoint).where(AccessPoint.organization_id == current_user.organization_id,
                                    AccessPoint.site_id.in_(visible_sites().with_only_columns(Site.id)))


def subjects_query():
    return select(AccessSubject).where(AccessSubject.organization_id == current_user.organization_id)


def own_subject(subject_id):
    subject = db.session.scalar(subjects_query().where(AccessSubject.id == subject_id))
    if not subject: abort(404)
    return subject


@bp.route("", methods=["GET", "POST"])
@console_required
@limiter.limit("20 per minute", methods=["POST"], key_func=lambda: current_user.get_id())
def index():
    points = db.session.scalars(points_query().order_by(AccessPoint.name)).all()
    form = DecisionForm()
    form.point_id.choices = [(point.id, point.name) for point in points]
    result = None
    if form.validate_on_submit():
        point = db.session.scalar(points_query().where(AccessPoint.id == form.point_id.data))
        if not point: abort(404)
        result = decide(point=point, token=form.token.data, actor_id=current_user.id)
        audit("access.simulated", result)
        if not commit(): abort(409)
        form.token.data = ""
    records = db.session.scalars(select(AccessEvent).where(AccessEvent.organization_id == current_user.organization_id,
                       AccessEvent.site_id.in_(visible_sites().with_only_columns(Site.id))).order_by(AccessEvent.id.desc()).limit(100)).all()
    return render_template("access/index.html", title="Controle de Acesso", active_slug="access", form=form, points=points, records=records,
                           result=result, reasons=REASONS), 422 if form.is_submitted() and result is None else 200


@bp.get("/people")
@organization_admin_required
def people():
    subjects = db.session.scalars(subjects_query().order_by(AccessSubject.display_name).limit(100)).all()
    permissions = db.session.scalars(select(AccessPermission).where(AccessPermission.organization_id == current_user.organization_id).order_by(AccessPermission.id.desc()).limit(100)).all()
    credentials = db.session.scalars(select(AccessCredential).where(AccessCredential.organization_id == current_user.organization_id).order_by(AccessCredential.id.desc()).limit(100)).all()
    return render_template("access/people.html", title="Pessoas Autorizadas", active_slug="people", subjects=subjects, permissions=permissions,
                           credentials=credentials, subjects_by_id={s.id:s for s in subjects})


@bp.route("/people/new", methods=["GET", "POST"])
@organization_admin_required
def create_subject():
    return save_subject()


@bp.route("/people/<int:subject_id>/edit", methods=["GET", "POST"])
@organization_admin_required
def edit_subject(subject_id):
    return save_subject(own_subject(subject_id))


def save_subject(subject=None):
    form = SubjectForm(obj=subject)
    if form.validate_on_submit():
        subject = subject or AccessSubject(organization_id=current_user.organization_id)
        subject.display_name, subject.external_reference, subject.active = form.display_name.data, form.external_reference.data, form.active.data
        db.session.add(subject)
        from sqlalchemy.exc import IntegrityError
        try: db.session.flush()
        except IntegrityError:
            db.session.rollback(); flash("Referência interna já utilizada.", "error")
        else:
            audit("subject.saved", subject)
            if commit(): return redirect(url_for("access.people"))
    return render_template("management/form.html", title="Pessoa autorizada", active_slug="people", form=form,
                           help_text="Cadastro mínimo; nenhuma foto, biometria ou documento sensível. Desativar impede novas decisões permitidas."), 422 if form.is_submitted() else 200


@bp.route("/points/new", methods=["GET", "POST"])
@organization_admin_required
def create_point():
    form = PointForm()
    form.site_id.choices = [(site.id, site.name) for site in db.session.scalars(visible_sites(active_only=True)).all()]
    if form.validate_on_submit():
        point = AccessPoint(organization_id=current_user.organization_id, site_id=form.site_id.data, name=form.name.data, enabled=form.enabled.data)
        db.session.add(point); db.session.flush(); audit("access_point.created", point)
        if commit(): return redirect(url_for("access.index"))
    return render_template("management/form.html", title="Novo ponto de acesso simulado", active_slug="access", form=form,
                           help_text="Somente simula decisões. Não controla fechaduras nem sistemas de emergência."), 422 if form.is_submitted() else 200


@bp.route("/points/<int:point_id>/state", methods=["GET", "POST"])
@organization_admin_required
def point_state(point_id):
    point = db.session.scalar(points_query().where(AccessPoint.id == point_id))
    if not point: abort(404)
    form = ConfirmationForm()
    if form.validate_on_submit():
        point.enabled = not point.enabled; audit("access_point.state_changed", point)
        if commit(): return redirect(url_for("access.index"))
    return render_template("management/form.html", title="Alterar estado do ponto simulado", active_slug="access", form=form,
                           help_text=point.name), 422 if form.is_submitted() else 200


@bp.route("/permissions/new", methods=["GET", "POST"])
@organization_admin_required
def permission():
    form = PermissionForm()
    form.site_id.choices = [(site.id, site.name) for site in db.session.scalars(visible_sites(active_only=True)).all()]
    form.subject_id.choices = [(subject.id, subject.display_name) for subject in db.session.scalars(subjects_query().where(AccessSubject.active.is_(True))).all()]
    if form.validate_on_submit():
        row = db.session.scalar(select(AccessPermission).where(AccessPermission.organization_id == current_user.organization_id,
                  AccessPermission.subject_id == form.subject_id.data, AccessPermission.site_id == form.site_id.data))
        row = row or AccessPermission(organization_id=current_user.organization_id, subject_id=form.subject_id.data, site_id=form.site_id.data)
        row.start_time, row.end_time, row.weekdays = form.start_time.data, form.end_time.data, form.weekdays.data
        db.session.add(row); db.session.flush(); audit("access_permission.saved", row)
        if commit(): return redirect(url_for("access.people"))
    return render_template("management/form.html", title="Permissão por unidade", active_slug="people", form=form,
                           help_text="Horários no fuso da unidade. Uma permissão não é uma credencial: é necessário apresentar um token válido de uso único."), 422 if form.is_submitted() else 200


@bp.route("/permissions/<int:permission_id>/revoke", methods=["GET", "POST"])
@organization_admin_required
def revoke_permission(permission_id):
    row = db.session.scalar(select(AccessPermission).where(AccessPermission.id == permission_id, AccessPermission.organization_id == current_user.organization_id))
    if not row: abort(404)
    form = ConfirmationForm()
    if form.validate_on_submit():
        audit("access_permission.revoked", row); db.session.delete(row)
        if commit(): return redirect(url_for("access.people"))
    return render_template("management/form.html", title="Revogar permissão de unidade", active_slug="people", form=form), 422 if form.is_submitted() else 200


@bp.route("/credentials/new", methods=["GET", "POST"])
@organization_admin_required
def create_credential():
    form = IssueForm()
    form.subject_id.choices = [(subject.id, subject.display_name) for subject in db.session.scalars(subjects_query().where(AccessSubject.active.is_(True))).all()]
    if form.validate_on_submit():
        subject = own_subject(form.subject_id.data)
        credential, token = issue(subject, form.ttl.data)
        db.session.flush(); audit("credential.issued", credential)
        if commit():
            return render_template("access/issued.html", title="Credencial de uso único", active_slug="people", token=token, credential=credential)
    return render_template("management/form.html", title="Emitir credencial temporária", active_slug="people", form=form,
                           help_text="O token é exibido somente na emissão e só pode ser utilizado uma vez. Não envie por canais públicos."), 422 if form.is_submitted() else 200


@bp.route("/credentials/<int:credential_id>/revoke", methods=["GET", "POST"])
@organization_admin_required
def revoke_credential(credential_id):
    credential = db.session.scalar(select(AccessCredential).where(AccessCredential.id == credential_id, AccessCredential.organization_id == current_user.organization_id))
    if not credential: abort(404)
    form = ConfirmationForm()
    if form.validate_on_submit():
        credential.revoked_at = utcnow(); audit("credential.revoked", credential)
        if commit(): return redirect(url_for("access.people"))
    return render_template("management/form.html", title="Revogar credencial", active_slug="people", form=form), 422 if form.is_submitted() else 200
