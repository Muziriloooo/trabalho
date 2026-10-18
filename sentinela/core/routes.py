from flask import Blueprint, abort, jsonify, redirect, render_template, url_for
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError

from ..extensions import db
from ..models import Camera, Organization, RoleAssignment, Site, User
from .navigation import NAVIGATION
from .permissions import console_required

bp = Blueprint("core", __name__)


@bp.app_context_processor
def navigation_context():
    return {"navigation": NAVIGATION}


@bp.get("/modules/<slug>")
@console_required
def module(slug):
    implemented = {"cameras": "cameras.index", "monitoring": "monitoring.index", "sites": "sites.index", "users": "team.index"}
    if slug in implemented:
        return redirect(url_for(implemented[slug]))
    item = next((item for item in NAVIGATION if item[3] == slug), None)
    if not item:
        abort(404)
    return render_template("module.html", title=item[1], description=item[4], module_icon=item[2], active_slug=slug)


@bp.get("/health")
def health():
    try:
        for model in (Organization, User, Site, RoleAssignment, Camera):
            db.session.execute(select(model).limit(1))
    except SQLAlchemyError:
        db.session.rollback()
        return jsonify(status="unavailable"), 503
    return jsonify(status="ok", version="0.4.0", phase=4)
