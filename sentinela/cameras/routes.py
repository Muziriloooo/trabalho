from datetime import timedelta, timezone

from flask import Blueprint, current_app, abort, flash, jsonify, redirect, render_template, request, url_for
from flask_login import current_user
from sqlalchemy import or_, select, update
from sqlalchemy.exc import IntegrityError

from ..core.forms import CameraForm, ConfirmationForm, DeleteCameraForm
from ..core.permissions import console_required, get_camera, organization_admin_required, visible_cameras, visible_sites
from ..extensions import db, limiter
from ..models import Camera, CameraHealthEvent, SecurityEvent, Site, utcnow
from ..services import gateway, vault
from ..services.audit import audit
from ..services.persistence import commit

bp = Blueprint("cameras", __name__, url_prefix="/cameras")

REASONS = {
    "demo": "Vídeo sintético disponível; nenhuma conexão real foi feita.",
    "ready": "Gateway confirmou a fonte disponível.",
    "not_ready": "Gateway informou que a fonte está indisponível.",
    "gateway_not_configured": "Gateway HTTPS ou sua lista de destinos não configurados.",
    "gateway_destination_denied": "Destino de gateway não permitido.",
    "credentials_unavailable": "Credencial protegida indisponível.",
    "gateway_auth_failed": "Autenticação no gateway recusada.",
    "source_unavailable": "Caminho da câmera não encontrado no gateway.",
    "gateway_unavailable": "Gateway indisponível ou resposta não permitida.",
    "gateway_timeout": "Tempo limite ao consultar o gateway.",
    "gateway_unreachable": "Não foi possível alcançar o gateway com TLS válido.",
    "invalid_gateway_response": "Resposta de saúde do gateway inválida.",
    "gateway_response_too_large": "Resposta excedeu o limite permitido.",
    "invalid_gateway_path": "Referência ao caminho inválida.",
}


def status_payload(camera):
    state = camera.connection_status
    now = utcnow()
    checked = camera.last_checked_at
    if not camera.enabled or camera.site.status != "active":
        state = "disabled"
    elif camera.protocol == "demo":
        state = "demo"
    elif not checked or (now - checked.replace(tzinfo=timezone.utc)).total_seconds() > current_app.config["CAMERA_STATUS_TTL"]:
        state = "unknown"
    return {"id": camera.id, "status": state, "demo": camera.protocol == "demo",
            "last_checked_at": checked.replace(tzinfo=timezone.utc).isoformat() if checked else None,
            "last_seen_at": camera.last_seen_at.replace(tzinfo=timezone.utc).isoformat() if camera.last_seen_at else None}


@bp.get("")
@console_required
def index():
    query = visible_cameras()
    search = request.args.get("q", "")[:120]
    if search:
        query = query.where(Camera.name.contains(search, autoescape=True) | Camera.identifier.contains(search, autoescape=True))
    site_id = request.args.get("site", type=int)
    if site_id:
        from ..core.permissions import get_site
        get_site(site_id)
        query = query.where(Camera.site_id == site_id)
    status = request.args.get("status", "")
    available = Camera.enabled.is_(True) & (Site.status == "active")
    cutoff = utcnow() - timedelta(seconds=current_app.config["CAMERA_STATUS_TTL"])
    if status == "disabled":
        query = query.where(or_(Camera.enabled.is_(False), Site.status != "active"))
    elif status == "demo":
        query = query.where(available, Camera.protocol == "demo")
    elif status in {"online", "offline"}:
        query = query.where(available, Camera.protocol != "demo", Camera.connection_status == status, Camera.last_checked_at >= cutoff)
    elif status == "unknown":
        query = query.where(available, Camera.protocol != "demo", or_(Camera.last_checked_at.is_(None), Camera.last_checked_at < cutoff, Camera.connection_status == "unknown"))
    cameras = db.session.scalars(query.order_by(Camera.name).limit(100)).all()
    states = {c.id: status_payload(c) for c in cameras}
    return render_template("cameras/index.html", title="Câmeras", active_slug="cameras", cameras=cameras, states=states,
                           sites=db.session.scalars(visible_sites().order_by(Site.name)).all(), search=search, site_filter=site_id, status_filter=status)


@bp.route("/new", methods=["GET", "POST"])
@organization_admin_required
def create():
    return save_camera()


@bp.route("/<int:camera_id>/edit", methods=["GET", "POST"])
@organization_admin_required
def edit(camera_id):
    return save_camera(get_camera(camera_id))


def save_camera(camera=None):
    form = CameraForm(obj=camera)
    sites = db.session.scalars(visible_sites(active_only=True).order_by(Site.name)).all()
    form.site_id.choices = [(site.id, site.name) for site in sites]
    if form.validate_on_submit():
        creating = camera is None
        camera = camera or Camera(organization_id=current_user.organization_id, created_by=current_user.id)
        previous_connection = (camera.protocol, camera.gateway_path, camera.site_id)
        for name in ("name", "identifier", "site_id", "manufacturer", "model", "location_description", "protocol"):
            setattr(camera, name, getattr(form, name).data)
        camera.gateway_path = form.gateway_path.data if camera.protocol != "demo" else ""
        changed = previous_connection != (camera.protocol, camera.gateway_path, camera.site_id) or form.clear_credentials.data or bool(form.gateway_password.data)
        if changed or creating:
            camera.connection_status = "demo" if camera.protocol == "demo" else "unknown"
            camera.last_checked_at = None
            camera.last_seen_at = None
        db.session.add(camera)
        try:
            db.session.flush()
            if camera.protocol == "demo" or form.clear_credentials.data:
                vault.clear_credentials(camera)
            elif form.gateway_password.data:
                vault.save_credentials(camera, form.gateway_username.data, form.gateway_password.data)
            audit("camera.created" if creating else "camera.updated", camera)
            if commit():
                flash("Câmera salva. Execute a verificação para consultar uma fonte real.", "success")
                return redirect(url_for("cameras.detail", camera_id=camera.id))
        except IntegrityError:
            db.session.rollback()
            flash("Identificador já utilizado nesta organização ou unidade inválida.", "error")
        except vault.SecretUnavailable as error:
            db.session.rollback()
            flash(str(error), "error")
    return render_template("management/form.html", title="Editar câmera" if camera else "Cadastrar câmera", form=form, active_slug="cameras",
                           help_text=f"Demonstração usa vídeo sintético local. Fontes reais exigem MediaMTX HTTPS. Provisione no gateway o prefixo org-{current_user.organization_id}-- seguido da referência cadastrada abaixo. Não informe URLs ou credenciais da câmera: elas ficam somente no gateway. Campos de credencial em branco preservam a credencial de leitura já salva."), 422 if form.is_submitted() else 200


@bp.get("/<int:camera_id>")
@console_required
def detail(camera_id):
    camera = get_camera(camera_id)
    history = db.session.scalars(select(CameraHealthEvent).where(CameraHealthEvent.camera_id == camera.id,
                                                                CameraHealthEvent.organization_id == current_user.organization_id).order_by(CameraHealthEvent.id.desc()).limit(100)).all()
    return render_template("cameras/detail.html", title=camera.name, active_slug="cameras", camera=camera, state=status_payload(camera),
                           history=history, reasons=REASONS)


@bp.get("/<int:camera_id>/status")
@console_required
def status(camera_id):
    return jsonify(status_payload(get_camera(camera_id)))


@bp.post("/<int:camera_id>/check")
@organization_admin_required
@limiter.limit("10 per minute", key_func=lambda: current_user.get_id())
def check(camera_id):
    camera = get_camera(camera_id, playable=True)
    previous_state = camera.connection_status
    now = utcnow()
    if camera.last_checked_at and (now - camera.last_checked_at.replace(tzinfo=timezone.utc)).total_seconds() < 10:
        abort(429)
    if camera.protocol == "demo":
        state, reason = "demo", "demo"
    else:
        try:
            ready = gateway.probe(camera)
            state, reason = ("online", "ready") if ready else ("offline", "not_ready")
        except gateway.GatewayError as error:
            reason = error.code
            # Erro de configuração ou autenticação do gateway não prova câmera offline.
            state = "offline" if reason == "source_unavailable" else "unknown"
    camera.connection_status, camera.last_checked_at = state, now
    if state == "online":
        camera.last_seen_at = now
    db.session.add(CameraHealthEvent(organization_id=camera.organization_id, camera_id=camera.id, event_type=state, reason_code=reason))
    if camera.protocol != "demo":
        from ..services.events import emit_event
        kind = "camera_offline" if state == "offline" else "camera_reconnected" if state == "online" and previous_state == "offline" else "integration_failure" if state == "unknown" else None
        if kind:
            emit_event(organization_id=camera.organization_id, site_id=camera.site_id, camera_id=camera.id, event_type=kind,
                       source="gateway", reason_code=reason, cooldown=60)
    audit("camera.checked", camera)
    if not commit():
        abort(409)
    flash(REASONS.get(reason, "Verificação inconclusiva."), "success" if state in {"online", "demo"} else "error")
    return redirect(url_for("cameras.detail", camera_id=camera.id))


@bp.route("/<int:camera_id>/state", methods=["GET", "POST"])
@organization_admin_required
def state(camera_id):
    camera = get_camera(camera_id)
    form = ConfirmationForm()
    if form.validate_on_submit():
        camera.enabled = not camera.enabled
        camera.connection_status = "unknown"
        camera.last_checked_at = None
        camera.last_seen_at = None
        audit("camera.state_changed", camera)
        if commit():
            return redirect(url_for("cameras.detail", camera_id=camera.id))
    return render_template("management/form.html", title="Desativar câmera" if camera.enabled else "Reativar câmera", form=form,
                           help_text="A desativação interrompe novas requisições de mídia. Não exclui o histórico.", active_slug="cameras"), 422 if form.is_submitted() else 200


@bp.route("/<int:camera_id>/delete", methods=["GET", "POST"])
@organization_admin_required
def delete(camera_id):
    camera = get_camera(camera_id)
    form = DeleteCameraForm()
    if form.validate_on_submit():
        if form.identifier.data != camera.identifier:
            form.identifier.errors = ["O identificador não corresponde à câmera."]
        else:
            vault.clear_credentials(camera)
            audit("camera.deleted", camera)
            # Preserva eventos/alertas existentes ao remover o equipamento.
            db.session.execute(update(SecurityEvent).where(SecurityEvent.camera_id == camera.id, SecurityEvent.organization_id == current_user.organization_id).values(camera_id=None))
            db.session.delete(camera)
            if commit():
                flash("Câmera, credencial e histórico de disponibilidade removidos; eventos e alertas preservados.", "success")
                return redirect(url_for("cameras.index"))
    return render_template("management/form.html", title="Remover câmera", form=form,
                           help_text=f"Esta operação é irreversível. Identificador: {camera.identifier}", active_slug="cameras"), 422 if form.is_submitted() else 200
