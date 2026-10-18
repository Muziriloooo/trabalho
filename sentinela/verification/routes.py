from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from flask_login import current_user
from sqlalchemy import select, update

from ..access.routes import own_subject, points_query, subjects_query
from ..core.forms import ConfirmationForm
from ..core.permissions import console_required, organization_admin_required, visible_sites
from ..extensions import db, limiter
from ..models import AccessPoint, Site, VerificationChallenge, VerificationEnrollment, VerificationPolicy, VerificationRecord, utcnow
from ..services import verification as service
from ..services.audit import audit
from ..services.persistence import commit
from .forms import CaptureForm, EnrollmentForm, PolicyForm, StartForm

bp = Blueprint('verification', __name__, url_prefix='/verification')


def own_enrollments():
    return select(VerificationEnrollment).where(VerificationEnrollment.organization_id == current_user.organization_id)


@bp.route('', methods=['GET','POST'])
@console_required
@limiter.limit('10 per minute', methods=['POST'], key_func=lambda:current_user.get_id())
def index():
    form=StartForm()
    form.point_id.choices=[(p.id,p.name) for p in db.session.scalars(points_query().order_by('name')).all()]
    result=None
    if request.files: abort(400)
    if form.validate_on_submit():
        point=db.session.scalar(points_query().where(AccessPoint.id==form.point_id.data))
        if not point: abort(404)
        challenge,result=service.start(point,form.token.data,current_user.id)
        form.token.data=''
        audit('verification.started' if challenge else 'verification.result',point if challenge else result)
        if commit():
            if challenge:return redirect(url_for('verification.capture',challenge_id=challenge.id))
    records=db.session.scalars(select(VerificationRecord).where(VerificationRecord.organization_id==current_user.organization_id,
            VerificationRecord.site_id.in_(visible_sites().with_only_columns(Site.id))).order_by(VerificationRecord.id.desc()).limit(50)).all()
    return render_template('verification/index.html',title='Verificação 1:1 — teste sintético',active_slug='verification',form=form,
                           policy=service.policy_for(current_user.organization_id),records=records,result=result,outcomes=service.OUTCOMES), 422 if form.is_submitted() and result is None else 200


@bp.route('/policy',methods=['GET','POST'])
@organization_admin_required
def policy():
    row=service.policy_for(current_user.organization_id)
    form=PolicyForm(obj=row)
    if form.validate_on_submit():
        row=row or VerificationPolicy(organization_id=current_user.organization_id,version=0)
        for name in ('enabled','purpose','controller','legal_review','necessity_review','risk_review','workplace_review','alternative','retention_days','threshold'):
            setattr(row,name,getattr(form,name).data)
        row.version+=1;row.updated_at=utcnow()
        db.session.add(row);db.session.flush()
        db.session.execute(update(VerificationEnrollment).where(VerificationEnrollment.organization_id==current_user.organization_id,
            VerificationEnrollment.ciphertext.is_not(None)).values(ciphertext=None,authorization_reference='',revoked_at=utcnow()).execution_options(synchronize_session=False))
        audit('verification.policy_updated',row)
        if commit():
            flash('Política de teste salva. Referências anteriores precisam de novo cadastro; biometria real continua desativada.','success')
            return redirect(url_for('verification.enrollments'))
    return render_template('management/form.html',title='Política de verificação sintética',active_slug='verification',form=form,
                           help_text='Preparação do fluxo 1:1. Registrar referências não comprova adequação legal nem valida modelo, precisão ou proteção contra fraude. Nenhuma captura facial real é habilitada.'),422 if form.is_submitted() else 200


@bp.get('/enrollments')
@organization_admin_required
def enrollments():
    rows=db.session.scalars(own_enrollments().order_by(VerificationEnrollment.id.desc()).limit(100)).all()
    subjects=db.session.scalars(subjects_query()).all()
    return render_template('verification/enrollments.html',title='Referências sintéticas',active_slug='verification',rows=rows,
                           subjects={s.id:s for s in subjects},policy=service.policy_for(current_user.organization_id),now=utcnow(),usable=service.usable)


@bp.route('/enrollments/new',methods=['GET','POST'])
@organization_admin_required
def enroll():
    form=EnrollmentForm()
    form.subject_id.choices=[(s.id,s.display_name) for s in db.session.scalars(subjects_query()).all() if s.active]
    if request.files:abort(400)
    if form.validate_on_submit():
        policy=service.policy_for(current_user.organization_id)
        try:
            if not policy:raise service.VerificationUnavailable('Configure e habilite a política de teste primeiro.')
            row=service.enroll(own_subject(form.subject_id.data),policy,current_user.id,form.authorization_reference.data)
        except service.VerificationUnavailable as error:
            flash(str(error),'error')
        else:
            audit('verification.enrolled',row)
            if commit():return redirect(url_for('verification.enrollments'))
    return render_template('management/form.html',title='Cadastro assistido de teste',active_slug='verification',form=form,
                           help_text='Gera somente um vetor artificial cifrado, associado a um cadastro declarado. Não recebe fotografia, vídeo ou template facial real.'),422 if form.is_submitted() else 200


@bp.route('/enrollments/<int:enrollment_id>/erase',methods=['GET','POST'])
@organization_admin_required
def erase(enrollment_id):
    row=db.session.scalar(own_enrollments().where(VerificationEnrollment.id==enrollment_id))
    if not row:abort(404)
    form=ConfirmationForm()
    if form.validate_on_submit():
        service.erase(row);audit('verification.erased',row)
        if commit():return redirect(url_for('verification.enrollments'))
    return render_template('management/form.html',title='Revogar e excluir referência de teste',active_slug='verification',form=form,
                           help_text='Remove o conteúdo cifrado e a referência de autorização. Mantém apenas o registro mínimo da exclusão. A alternativa não biométrica continua disponível.'),422 if form.is_submitted() else 200


@bp.route('/capture/<challenge_id>',methods=['GET','POST'])
@console_required
@limiter.limit('10 per minute',methods=['POST'],key_func=lambda:current_user.get_id())
def capture(challenge_id):
    challenge=db.session.scalar(select(VerificationChallenge).where(VerificationChallenge.id==challenge_id,
              VerificationChallenge.organization_id==current_user.organization_id,VerificationChallenge.actor_id==current_user.id))
    if not challenge:abort(404)
    point=db.session.scalar(points_query().where(AccessPoint.id==challenge.point_id))
    if not point:abort(404)
    if request.files:abort(400)
    form=CaptureForm()
    if form.validate_on_submit():
        try:result=service.finish(challenge,point,current_user.id,form.scenario.data)
        except service.VerificationUnavailable as error:
            db.session.rollback();flash(str(error),'error');return redirect(url_for('verification.index'))
        audit('verification.result',result)
        if commit():
            flash(service.OUTCOMES[result.outcome]+' — resultado exclusivamente de teste. Método não biométrico disponível.','success' if result.outcome=='approved' else 'error')
            return redirect(url_for('verification.index'))
    return render_template('management/form.html',title='Comparação sintética 1:1',active_slug='verification',form=form,
                           help_text='Credencial apresentada e vinculada pelo servidor a uma única referência. Desafio de dois minutos e uso único. Não há busca de desconhecidos, câmera, pontuação exibida ou prova de vida.'),422 if form.is_submitted() else 200
