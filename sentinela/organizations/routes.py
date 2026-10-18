from flask import Blueprint, abort, flash, redirect, render_template, url_for
from flask_login import current_user, login_required
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from ..core.forms import OrganizationForm
from ..core.permissions import organization_admin_required
from ..extensions import db
from ..models import Organization
from ..services.audit import audit
from ..services.persistence import commit

bp = Blueprint("organizations", __name__)


@bp.route("/organization", methods=["GET", "POST"])
@organization_admin_required
def current():
    return edit_organization(current_user.organization)


@bp.route("/organizations", methods=["GET", "POST"])
@login_required
def index():
    if current_user.role != "platform_admin":
        abort(403)
    form = OrganizationForm()
    if form.validate_on_submit():
        org = Organization(name=form.name.data, identifier=form.identifier.data, responsible=form.responsible.data, status=form.status.data)
        db.session.add(org)
        # O registro de criação integra a mesma transação.
        try:
            db.session.flush()
        except IntegrityError:
            db.session.rollback()
            flash("Identificador indisponível. Revise os dados.", "error")
        else:
            audit("organization.created", org, org.id)
            if commit():
                flash("Organização cadastrada. Nenhum acesso a câmeras foi concedido.", "success")
                return redirect(url_for("organizations.index"))
    return render_template("management/organizations.html", title="Organizações", form=form,
                           organizations=db.session.scalars(select(Organization).order_by(Organization.name).limit(100)).all(), active_slug="organizations"), 422 if form.is_submitted() else 200


@bp.route("/organizations/<int:organization_id>/edit", methods=["GET", "POST"])
@login_required
def edit(organization_id):
    if current_user.role != "platform_admin":
        abort(403)
    org = db.get_or_404(Organization, organization_id)
    return edit_organization(org)


def edit_organization(org):
    form = OrganizationForm(obj=org)
    valid = form.validate_on_submit()
    if valid and org.status == "active" and form.status.data == "inactive" and not form.confirm.data:
        form.confirm.errors = ["Confirme a desativação."]
        valid = False
    if valid:
        for field in ("name", "identifier", "responsible", "status"):
            setattr(org, field, getattr(form, field).data)
        audit("organization.updated", org, org.id)
        if commit():
            flash("Organização atualizada.", "success")
            return redirect(url_for("organizations.index" if current_user.role == "platform_admin" else "organizations.current"))
    return render_template("management/form.html", title="Editar organização", form=form, active_slug="organizations",
                           help_text="A desativação interrompe o acesso da organização. A reativação pode ser feita pelo administrador da plataforma."), 422 if form.is_submitted() else 200
