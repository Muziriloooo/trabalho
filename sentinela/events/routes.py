from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from flask_login import current_user
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from ..core.permissions import console_required, get_camera, organization_admin_required, visible_cameras, visible_sites
from ..extensions import db, limiter
from ..models import AnalysisJob, AnalysisPolicy, Camera, SecurityEvent, Site, utcnow
from ..services.analysis import run_job
from ..services.audit import audit
from ..services.events import EVENT_LABELS, SOURCE_LABELS, emit_event
from ..services.persistence import commit
from .forms import JobForm, PolicyForm, YouTubeObservationForm

bp = Blueprint("events", __name__, url_prefix="/events")


def visible_events():
    return select(SecurityEvent).where(SecurityEvent.organization_id == current_user.organization_id,
                                        SecurityEvent.site_id.in_(visible_sites().with_only_columns(Site.id)))


@bp.get("")
@console_required
def index():
    query = visible_events()
    kind, source = request.args.get("type", ""), request.args.get("source", "")
    if kind in EVENT_LABELS:
        query = query.where(SecurityEvent.event_type == kind)
    if source in SOURCE_LABELS:
        query = query.where(SecurityEvent.source == source)
    records = db.session.scalars(query.order_by(SecurityEvent.id.desc()).limit(100)).all()
    cameras = db.session.scalars(visible_cameras().order_by(Camera.name).limit(100)).all()
    jobs = db.session.scalars(select(AnalysisJob).where(AnalysisJob.organization_id == current_user.organization_id,
                            AnalysisJob.camera_id.in_([camera.id for camera in cameras])).order_by(AnalysisJob.id.desc()).limit(30)).all()
    return render_template("events/index.html", title="Eventos e análise", active_slug="events", events=records, cameras=cameras, jobs=jobs,
                           labels=EVENT_LABELS, sources=SOURCE_LABELS, type_filter=kind, source_filter=source,
                           job_reasons={"sample_analyzed": "Amostra analisada", "disabled_or_revoked": "Análise desativada ou autorização revogada",
                                        "outside_schedule": "Fora do horário configurado", "internal_analysis_error": "Falha interna na análise"})


@bp.route("/cameras/<int:camera_id>/policy", methods=["GET", "POST"])
@organization_admin_required
def policy(camera_id):
    camera = get_camera(camera_id)
    policy = db.session.scalar(select(AnalysisPolicy).where(AnalysisPolicy.camera_id == camera.id, AnalysisPolicy.organization_id == current_user.organization_id))
    form = PolicyForm(obj=policy)
    if form.validate_on_submit():
        policy = policy or AnalysisPolicy(camera_id=camera.id, organization_id=current_user.organization_id)
        for name in ("enabled", "motion_enabled", "obstruction_enabled", "motion_ratio", "roi_x", "roi_y", "roi_w", "roi_h", "cooldown_seconds", "start_time", "end_time", "weekdays"):
            setattr(policy, name, getattr(form, name).data)
        policy.updated_at = utcnow()
        db.session.add(policy); db.session.flush(); audit("analysis.policy_updated", policy)
        if commit():
            flash("Configuração de análise salva. Nenhum processamento contínuo foi iniciado.", "success")
            return redirect(url_for("events.index"))
    return render_template("management/form.html", title=f"Análise: {camera.name}", active_slug="events", form=form,
                           help_text="Área normalizada na imagem. Horários no fuso da unidade. Movimento não significa crime. Detecção de pessoas ou identificação facial não são executadas."), 422 if form.is_submitted() else 200


@bp.route("/cameras/<int:camera_id>/analyze", methods=["GET", "POST"])
@organization_admin_required
@limiter.limit("10 per minute", methods=["POST"], key_func=lambda: current_user.get_id())
def analyze(camera_id):
    camera = get_camera(camera_id, playable=True)
    form = JobForm()
    if form.validate_on_submit():
        policy = db.session.scalar(select(AnalysisPolicy).where(AnalysisPolicy.camera_id == camera.id, AnalysisPolicy.enabled.is_(True)))
        if not policy:
            flash("Ative e autorize a análise desta câmera primeiro.", "error")
            return redirect(url_for("events.policy", camera_id=camera.id))
        existing = db.session.scalar(select(AnalysisJob).where(AnalysisJob.camera_id == camera.id, AnalysisJob.status.in_(["pending", "running"])))
        if existing:
            flash("Já existe uma análise pendente ou em execução para esta câmera.", "error")
            return redirect(url_for("events.index"))
        job = AnalysisJob(organization_id=current_user.organization_id, camera_id=camera.id, requested_by=current_user.id)
        db.session.add(job)
        try:
            db.session.flush()
        except IntegrityError:
            db.session.rollback()
            flash("Outra solicitação já enfileirou esta câmera.", "error")
            return redirect(url_for("events.index"))
        audit("analysis.requested", job); db.session.commit()
        if form.mode.data == "now" and camera.protocol == "demo":
            run_job(job.id)
            flash("Análise de vídeo sintético concluída; confira o resultado da tarefa.", "success")
        else:
            flash("Tarefa enfileirada. Execute o worker process-analysis; fontes reais não são decodificadas no servidor web.", "success")
        return redirect(url_for("events.index"))
    return render_template("management/form.html", title=f"Analisar amostra: {camera.name}", active_slug="events", form=form,
                           help_text="Analisa até 72 quadros, sem guardar imagens permanentemente. Fontes reais exigem gateway e worker. O player YouTube não fornece quadros ao backend."), 422 if form.is_submitted() else 200


@bp.post("/youtube-observation")
@console_required
@limiter.limit("10 per minute", key_func=lambda: current_user.get_id())
def youtube_observation():
    form = YouTubeObservationForm()
    form.site_id.choices = [(site.id, site.name) for site in db.session.scalars(visible_sites(active_only=True).order_by(Site.name)).all()]
    if not form.validate_on_submit():
        return render_template("management/form.html", title="Resultado do teste YouTube", form=form, active_slug="events",
                               help_text="Relato manual do operador; não verifica nem analisa a transmissão no backend."), 422
    event = emit_event(organization_id=current_user.organization_id, site_id=form.site_id.data, event_type=form.result.data,
                       source="youtube_client", severity="attention" if form.result.data == "youtube_playback_error" else "info",
                       reason_code="manual_report_CKpA7U_wAbw", cooldown=60)
    if event:
        audit("youtube.observed", event)
    if commit():
        flash("Resultado manual registrado." if event else "Resultado repetido suprimido pelo intervalo de 60 segundos.", "success")
    return redirect(url_for("events.index"))
