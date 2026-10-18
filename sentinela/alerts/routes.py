from flask import Blueprint, abort, flash, jsonify, redirect, render_template, request, url_for
from flask_login import current_user
from sqlalchemy import func, or_, select, update

from ..core.permissions import console_required, visible_sites
from ..extensions import db
from ..models import Alert, AlertActivity, RoleAssignment, SecurityEvent, Site, User, utcnow
from ..services.audit import audit
from ..services.events import EVENT_LABELS, SOURCE_LABELS
from ..services.persistence import commit
from .forms import AlertForm, STATUSES

bp = Blueprint("alerts", __name__, url_prefix="/alerts")


def visible_alerts():
    return select(Alert).where(Alert.organization_id == current_user.organization_id, Alert.site_id.in_(visible_sites().with_only_columns(Site.id)))


def eligible_users(site_id):
    grant = select(RoleAssignment.user_id).where(RoleAssignment.organization_id == current_user.organization_id,
                                                or_(RoleAssignment.site_id == site_id, RoleAssignment.site_id.is_(None)))
    return db.session.scalars(select(User).where(User.organization_id == current_user.organization_id, User.active.is_(True),
                             or_(User.role == "organization_admin", (User.role.in_(["operator", "supervisor"])) & User.id.in_(grant))).order_by(User.email)).all()


@bp.get("")
@console_required
def index():
    query = visible_alerts().join(SecurityEvent, Alert.event_id == SecurityEvent.id)
    status, priority, search = request.args.get("status", ""), request.args.get("priority", ""), request.args.get("q", "")[:80]
    if status in STATUSES:
        query = query.where(Alert.status == status)
    if priority in {"attention", "critical"}:
        query = query.where(SecurityEvent.severity == priority)
    if search:
        kinds = [key for key, label in EVENT_LABELS.items() if search.casefold() in label.casefold() or search in key]
        query = query.where(SecurityEvent.event_type.in_(kinds))
    alerts = db.session.scalars(query.order_by(Alert.id.desc()).limit(100)).all()
    return render_template("alerts/index.html", title="Central de Alertas", active_slug="alerts", alerts=alerts, labels=EVENT_LABELS,
                           sources=SOURCE_LABELS, statuses=STATUSES, status_filter=status, priority_filter=priority, search=search)


@bp.get("/summary")
@console_required
def summary():
    count = db.session.scalar(select(func.count()).select_from(visible_alerts().where(Alert.status.in_(["new", "acknowledged", "in_review"])).subquery()))
    return jsonify(pending=count)


@bp.route("/<int:alert_id>", methods=["GET", "POST"])
@console_required
def detail(alert_id):
    alert = db.session.scalar(visible_alerts().where(Alert.id == alert_id))
    if not alert:
        abort(404)
    form = AlertForm(data={"status": alert.status, "assigned_to": alert.assigned_to or 0})
    users = eligible_users(alert.site_id)
    # Operador assume a própria ocorrência; supervisão e administração podem atribuir.
    manager = current_user.role == "organization_admin" or db.session.scalar(select(RoleAssignment.id).where(
        RoleAssignment.user_id == current_user.id, RoleAssignment.organization_id == current_user.organization_id,
        RoleAssignment.role == "supervisor", or_(RoleAssignment.site_id == alert.site_id, RoleAssignment.site_id.is_(None)))) is not None
    if not manager:
        users = [user for user in users if user.id == current_user.id or user.id == alert.assigned_to]
    form.assigned_to.choices = [(0, "Sem responsável")] + [(user.id, user.email) for user in users]
    transitions = {"new": {"new", "acknowledged", "discarded"}, "acknowledged": {"acknowledged", "in_review", "resolved", "discarded"},
                   "in_review": {"in_review", "resolved", "discarded"}, "resolved": {"resolved"}, "discarded": {"discarded"}}
    if form.validate_on_submit():
        valid = True
        if form.status.data not in transitions[alert.status]:
            form.status.errors = ["Transição inválida. Reconheça a ocorrência antes de avançar."]; valid = False
        if form.status.data in {"resolved", "discarded"} and not form.note.data.strip():
            form.note.errors = ["Informe uma justificativa."]; valid = False
        if not manager and form.assigned_to.data not in {0, current_user.id, alert.assigned_to}:
            abort(403)
        if not manager and alert.assigned_to not in {None, current_user.id} and form.assigned_to.data != alert.assigned_to:
            abort(403)
        if alert.status in {"resolved", "discarded"}:
            form.status.errors = ["Ocorrência encerrada; o histórico permanece somente para consulta."]; valid = False
        if valid:
            previous = alert.status
            changes = {"status": form.status.data, "assigned_to": form.assigned_to.data or None, "version": alert.version + 1}
            if previous == "new" and form.status.data in {"acknowledged", "in_review"}:
                changes["acknowledged_at"] = utcnow()
            if form.status.data in {"resolved", "discarded"}:
                changes["resolved_at"] = utcnow()
            updated = db.session.execute(update(Alert).where(Alert.id == alert.id, Alert.version == alert.version).values(**changes))
            if updated.rowcount != 1:
                db.session.rollback(); abort(409)
            db.session.refresh(alert)
            db.session.add(AlertActivity(organization_id=current_user.organization_id, alert_id=alert.id, actor_id=current_user.id,
                                         action=f"{previous}:{alert.status}", note=form.note.data.strip()))
            audit("alert.updated", alert)
            if commit():
                flash("Providência registrada no histórico.", "success")
                return redirect(url_for("alerts.detail", alert_id=alert.id))
    history = db.session.scalars(select(AlertActivity).where(AlertActivity.alert_id == alert.id, AlertActivity.organization_id == current_user.organization_id).order_by(AlertActivity.id)).all()
    return render_template("alerts/detail.html", title=f"Alerta #{alert.id}", active_slug="alerts", alert=alert, form=form, history=history,
                           labels=EVENT_LABELS, sources=SOURCE_LABELS, statuses=STATUSES), 422 if form.is_submitted() else 200
