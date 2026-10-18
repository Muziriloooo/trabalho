from flask import Blueprint, abort, flash, redirect, render_template, url_for
from flask_login import current_user
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from ..core.forms import AssignmentForm, ConfirmationForm, MemberForm
from ..core.permissions import get_site, organization_admin_required, visible_sites
from ..extensions import db
from ..models import RoleAssignment, Site, User
from ..services.audit import audit
from ..services.persistence import commit

bp = Blueprint("team", __name__, url_prefix="/team")


def own_member(user_id):
    user = db.session.scalar(select(User).where(User.id == user_id, User.organization_id == current_user.organization_id,
                                               User.role.in_(["operator", "supervisor"])))
    if not user:
        abort(404)
    return user


@bp.route("", methods=["GET", "POST"])
@organization_admin_required
def index():
    members = db.session.scalars(select(User).where(User.organization_id == current_user.organization_id,
                                                   User.role.in_(["operator", "supervisor"])).order_by(User.email).limit(100)).all()
    sites = db.session.scalars(visible_sites().order_by(Site.name)).all()
    form = AssignmentForm()
    form.user_id.choices = [(u.id, u.email) for u in members if u.active]
    form.site_id.choices = [(0, "Todas as unidades da organização")] + [(s.id, s.name) for s in sites if s.status == "active"]
    if form.validate_on_submit():
        own_member(form.user_id.data)
        if form.site_id.data:
            get_site(form.site_id.data)
        existing = db.session.scalar(select(RoleAssignment).where(
            RoleAssignment.organization_id == current_user.organization_id,
            RoleAssignment.user_id == form.user_id.data,
            RoleAssignment.site_id == (form.site_id.data or None)))
        if existing:
            existing.role = form.role.data
            existing.granted_by = current_user.id
            assignment = existing
        else:
            assignment = RoleAssignment(organization_id=current_user.organization_id, user_id=form.user_id.data,
                                        site_id=form.site_id.data or None, role=form.role.data, granted_by=current_user.id)
            db.session.add(assignment)
        db.session.flush()
        audit("scope.granted", assignment)
        if commit():
            flash("Escopo de acesso atualizado.", "success")
            return redirect(url_for("team.index"))
    assignments = db.session.scalars(select(RoleAssignment).where(RoleAssignment.organization_id == current_user.organization_id).order_by(RoleAssignment.id).limit(200)).all()
    return render_template("management/team.html", title="Usuários e escopos", active_slug="users", form=form,
                           members=members, assignments=assignments, sites_by_id={s.id: s for s in sites}, users_by_id={u.id: u for u in members}), 422 if form.is_submitted() else 200


@bp.route("/new", methods=["GET", "POST"])
@organization_admin_required
def create():
    form = MemberForm()
    if form.validate_on_submit():
        member = User(organization_id=current_user.organization_id, email=form.email.data, role=form.role.data)
        member.set_password(form.password.data)
        db.session.add(member)
        try:
            db.session.flush()
        except IntegrityError:
            db.session.rollback()
            flash("Este e-mail não está disponível.", "error")
        else:
            audit("member.created", member)
            if commit():
                flash("Usuário criado sem escopos. Conceda acesso às unidades desejadas.", "success")
                return redirect(url_for("team.index"))
    return render_template("management/form.html", title="Cadastrar operador ou supervisor", active_slug="users", form=form,
                           help_text="Forneça a senha inicial por um canal seguro. Nenhuma unidade é liberada automaticamente."), 422 if form.is_submitted() else 200


@bp.route("/scopes/<int:assignment_id>/revoke", methods=["GET", "POST"])
@organization_admin_required
def revoke(assignment_id):
    assignment = db.session.scalar(select(RoleAssignment).where(RoleAssignment.id == assignment_id, RoleAssignment.organization_id == current_user.organization_id))
    if not assignment:
        abort(404)
    form = ConfirmationForm()
    if form.validate_on_submit():
        audit("scope.revoked", assignment)
        db.session.delete(assignment)
        if commit():
            flash("Escopo revogado. As próximas requisições de mídia serão bloqueadas.", "success")
            return redirect(url_for("team.index"))
    return render_template("management/form.html", title="Revogar escopo", active_slug="users", form=form,
                           help_text="O usuário perde este escopo imediatamente. Outros escopos concedidos permanecem válidos."), 422 if form.is_submitted() else 200


@bp.route("/<int:user_id>/state", methods=["GET", "POST"])
@organization_admin_required
def state(user_id):
    user = own_member(user_id)
    form = ConfirmationForm()
    if form.validate_on_submit():
        user.active = not user.active
        audit("member.state_changed", user)
        if commit():
            return redirect(url_for("team.index"))
    return render_template("management/form.html", title="Desativar usuário" if user.active else "Reativar usuário", form=form,
                           help_text=user.email, active_slug="users"), 422 if form.is_submitted() else 200
