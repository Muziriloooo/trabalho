from functools import wraps

from flask import abort
from flask_login import current_user, login_required
from sqlalchemy import exists, or_, select

from ..extensions import db
from ..models import Camera, RoleAssignment, Site


def console_required(view):
    @wraps(view)
    @login_required
    def wrapped(*args, **kwargs):
        user = current_user
        if (user.role not in {"organization_admin", "supervisor", "operator"}
                or not user.organization or user.organization.status != "active"):
            abort(403)
        return view(*args, **kwargs)
    return wrapped


def organization_admin_required(view):
    @wraps(view)
    @console_required
    def wrapped(*args, **kwargs):
        if current_user.role != "organization_admin":
            abort(403)
        return view(*args, **kwargs)
    return wrapped


def site_scope():
    """Escopo de unidade resolvido no servidor, inclusive para requisições de mídia."""
    if current_user.role == "organization_admin":
        return True
    return exists(select(RoleAssignment.id).where(
        RoleAssignment.user_id == current_user.id,
        RoleAssignment.organization_id == current_user.organization_id,
        RoleAssignment.role.in_(["operator", "supervisor"]),
        or_(RoleAssignment.site_id.is_(None), RoleAssignment.site_id == Site.id),
    ))


def visible_sites(active_only=False):
    query = select(Site).where(Site.organization_id == current_user.organization_id, site_scope())
    if active_only:
        query = query.where(Site.status == "active")
    return query


def get_site(site_id):
    site = db.session.scalar(visible_sites().where(Site.id == site_id))
    if site is None:
        abort(404)
    return site


def visible_cameras():
    return select(Camera).join(Site, (Site.id == Camera.site_id) & (Site.organization_id == Camera.organization_id)).where(
        Camera.organization_id == current_user.organization_id, site_scope())


def get_camera(camera_id, playable=False):
    camera = db.session.scalar(visible_cameras().where(Camera.id == camera_id))
    if camera is None:
        abort(404)
    if playable and (not camera.enabled or camera.site.status != "active"):
        abort(409, description="Equipamento ou unidade desativados.")
    return camera
