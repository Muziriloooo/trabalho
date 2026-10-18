from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user
from sqlalchemy import func, select

from ..core.forms import SiteForm
from ..core.permissions import console_required, get_site, organization_admin_required, visible_sites
from ..extensions import db
from ..models import Camera, Site
from ..services.audit import audit
from ..services.persistence import commit

bp = Blueprint("sites", __name__, url_prefix="/sites")


@bp.get("")
@console_required
def index():
    query = visible_sites()
    search = request.args.get("q", "")[:120]
    if search:
        query = query.where(Site.name.contains(search, autoescape=True))
    status = request.args.get("status", "")
    if status in {"active", "inactive"}:
        query = query.where(Site.status == status)
    sites = db.session.scalars(query.order_by(Site.name).limit(100)).all()
    counts = dict(db.session.execute(select(Camera.site_id, func.count(Camera.id)).where(
        Camera.organization_id == current_user.organization_id,
        Camera.site_id.in_([s.id for s in sites])).group_by(Camera.site_id)).all())
    return render_template("management/sites.html", title="Unidades", active_slug="sites", sites=sites, counts=counts, search=search, status_filter=status)


@bp.route("/new", methods=["GET", "POST"])
@organization_admin_required
def create():
    return save_site()


@bp.route("/<int:site_id>/edit", methods=["GET", "POST"])
@organization_admin_required
def edit(site_id):
    return save_site(get_site(site_id))


def save_site(site=None):
    form = SiteForm(obj=site)
    valid = form.validate_on_submit()
    if valid and site and site.status == "active" and form.status.data == "inactive" and not form.confirm.data:
        form.confirm.errors = ["Confirme a desativação."]
        valid = False
    if valid:
        creating = site is None
        site = site or Site(organization_id=current_user.organization_id)
        for name in ("name", "identifier", "responsible", "address", "location_description", "timezone", "status"):
            setattr(site, name, getattr(form, name).data)
        db.session.add(site)
        # Audit usa o identificador após o insert, na mesma transação.
        from sqlalchemy.exc import IntegrityError
        try:
            db.session.flush()
        except IntegrityError:
            db.session.rollback()
            flash("Identificador já utilizado nesta organização.", "error")
        else:
            audit("site.created" if creating else "site.updated", site)
            if commit():
                flash("Unidade salva.", "success")
                return redirect(url_for("sites.index"))
    return render_template("management/form.html", title="Editar unidade" if site else "Nova unidade", form=form, active_slug="sites",
                           help_text="Unidades inativas não podem transmitir vídeo nem receber novas câmeras."), 422 if form.is_submitted() else 200
