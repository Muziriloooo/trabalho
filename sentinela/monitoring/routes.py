from pathlib import Path

from flask import Blueprint, Response, abort, jsonify, render_template, request, send_file
from sqlalchemy import select

from ..core.permissions import console_required, get_camera, get_site, visible_cameras, visible_sites
from ..extensions import db, limiter
from ..models import Camera, Site
from ..services import gateway
from ..cameras.routes import status_payload

bp = Blueprint("monitoring", __name__, url_prefix="/monitoring")


@bp.get("/youtube/status")
@console_required
def youtube_status():
    # Exemplo público, sem associação ao inventário privado de uma organização.
    return jsonify(status="public", video_id="CKpA7U_wAbw")


@bp.get("")
@console_required
def index():
    query = visible_cameras().where(Camera.enabled.is_(True), Site.status == "active")
    site_id = request.args.get("site", type=int)
    if site_id:
        get_site(site_id)
        query = query.where(Camera.site_id == site_id)
    camera_id = request.args.get("camera", type=int)
    if camera_id:
        get_camera(camera_id, playable=True)
        query = query.where(Camera.id == camera_id)
    cameras = db.session.scalars(query.order_by(Camera.name).limit(9)).all()
    return render_template("monitoring/index.html", title="Monitoramento", active_slug="monitoring", cameras=cameras,
                           sites=db.session.scalars(visible_sites(active_only=True).order_by(Site.name)).all(), site_filter=site_id, camera_filter=camera_id,
                           states={c.id: status_payload(c) for c in cameras})


@bp.get("/<int:camera_id>/demo.mp4")
@console_required
def demo(camera_id):
    camera = get_camera(camera_id, playable=True)
    if camera.protocol != "demo":
        abort(404)
    path = Path(__file__).resolve().parent.parent / "media" / "demo.mp4"
    return send_file(path, mimetype="video/mp4", conditional=True, max_age=0)


@bp.get("/<int:camera_id>/media/<asset>")
@console_required
@limiter.limit("600 per minute")
def media(camera_id, asset):
    camera = get_camera(camera_id, playable=True)
    if camera.protocol == "demo" or not gateway.SAFE_ASSET.fullmatch(asset) or request.query_string:
        abort(404)
    manifest = asset.endswith(".m3u8")
    try:
        data = gateway.fetch(camera, "HLS", f"/{gateway.source_name(camera)}/{asset}", 256 * 1024 if manifest else 12 * 1024 * 1024)
        if manifest:
            data = gateway.rewrite_manifest(data, camera.id)
    except gateway.GatewayError as error:
        return jsonify(error=error.code), error.status
    content_type = "application/vnd.apple.mpegurl" if manifest else "video/mp2t" if asset.endswith(".ts") else "video/mp4"
    return Response(data, content_type=content_type)
