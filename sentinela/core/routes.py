from flask import Blueprint, abort, jsonify, render_template
from sqlalchemy import text

from ..extensions import db
from .navigation import NAVIGATION
from .permissions import console_required

bp = Blueprint("core", __name__)


@bp.app_context_processor
def navigation_context():
    return {"navigation": NAVIGATION}


@bp.get("/modules/<slug>")
@console_required
def module(slug):
    item = next((item for item in NAVIGATION if item[3] == slug), None)
    if not item:
        abort(404)
    return render_template("module.html", title=item[1], description=item[4], module_icon=item[2], active_slug=slug)


@bp.get("/health")
def health():
    try:
        db.session.execute(text("SELECT 1"))
        # Além da conexão, verifica que o schema mínimo foi migrado.
        db.session.execute(text("SELECT id FROM organization LIMIT 1"))
        db.session.execute(text("SELECT id FROM user LIMIT 1"))
    except Exception:
        db.session.rollback()
        return jsonify(status="unavailable"), 503
    return jsonify(status="ok", version="0.1.0", phase=1)
