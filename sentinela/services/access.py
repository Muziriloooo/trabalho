import hashlib
import secrets
from datetime import timedelta

from sqlalchemy import exists, func, select, update

from ..extensions import db
from ..models import AccessCredential, AccessEvent, AccessPermission, AccessPoint, AccessSubject, Site, utcnow
from .events import emit_event
from .schedules import as_utc, in_schedule

REASONS = {"allowed": "Credencial válida e permissão confirmada", "invalid": "Credencial inválida", "revoked": "Credencial revogada",
           "expired": "Credencial vencida", "used": "Credencial já utilizada", "subject_inactive": "Cadastro inativo",
           "point_inactive": "Ponto ou unidade inativos", "no_permission": "Sem permissão para esta unidade",
           "outside_schedule": "Fora do horário autorizado", "state_changed": "Credencial ou permissão alterada durante a tentativa",
           "policy_unavailable": "Não foi possível validar o horário autorizado"}


def issue(subject, ttl):
    token = secrets.token_urlsafe(32)
    credential = AccessCredential(organization_id=subject.organization_id, subject_id=subject.id,
                                  token_hash=hashlib.sha256(token.encode()).hexdigest(), expires_at=utcnow() + timedelta(seconds=ttl))
    db.session.add(credential)
    return credential, token


def decide(*, point, token, actor_id, now=None):
    now = now or utcnow()
    credential = db.session.scalar(select(AccessCredential).where(AccessCredential.organization_id == point.organization_id,
                                   AccessCredential.token_hash == hashlib.sha256(token.encode()).hexdigest()))
    subject = db.session.get(AccessSubject, credential.subject_id) if credential else None
    site = db.session.get(Site, point.site_id)
    permission = db.session.scalar(select(AccessPermission).where(AccessPermission.organization_id == point.organization_id,
                                  AccessPermission.subject_id == subject.id, AccessPermission.site_id == point.site_id)) if subject else None
    reason = "allowed"
    if not point.enabled or site.status != "active": reason = "point_inactive"
    elif not credential: reason = "invalid"
    elif credential.revoked_at: reason = "revoked"
    elif as_utc(credential.expires_at) <= as_utc(now): reason = "expired"
    elif credential.used_at: reason = "used"
    elif not subject.active: reason = "subject_inactive"
    elif not permission: reason = "no_permission"
    else:
        try:
            if not in_schedule(now, site.timezone, permission.start_time, permission.end_time, permission.weekdays): reason = "outside_schedule"
        except (ValueError, KeyError):
            reason = "policy_unavailable"
    if reason == "allowed":
        used = db.session.execute(update(AccessCredential).where(AccessCredential.id == credential.id, AccessCredential.used_at.is_(None),
                    AccessCredential.revoked_at.is_(None), AccessCredential.expires_at > now,
                    exists(select(AccessSubject.id).where(AccessSubject.id==subject.id,AccessSubject.active.is_(True))),
                    exists(select(AccessPoint.id).where(AccessPoint.id==point.id,AccessPoint.enabled.is_(True))),
                    exists(select(Site.id).where(Site.id==site.id,Site.status=="active",Site.timezone==site.timezone)),
                    exists(select(AccessPermission.id).where(AccessPermission.id==permission.id,
                        AccessPermission.weekdays==permission.weekdays,AccessPermission.start_time==permission.start_time,
                        AccessPermission.end_time==permission.end_time)))
                    .values(used_at=now).returning(AccessCredential.id)).scalar()
        if not used: reason = "state_changed"
    event = AccessEvent(organization_id=point.organization_id, site_id=point.site_id, access_point_id=point.id,
                        subject_id=subject.id if subject else None, actor_id=actor_id, decision="allowed" if reason == "allowed" else "denied", reason_code=reason, occurred_at=now)
    db.session.add(event); db.session.flush()
    if event.decision == "denied":
        denied = db.session.scalar(select(func.count()).select_from(AccessEvent).where(AccessEvent.organization_id == point.organization_id,
                                  AccessEvent.access_point_id == point.id, AccessEvent.decision == "denied", AccessEvent.occurred_at >= now - timedelta(minutes=5)))
        if denied >= 3:
            emit_event(organization_id=point.organization_id, site_id=point.site_id, event_type="access_denied_repeated", source="access_simulation",
                       cooldown=300, gate_suffix=str(point.id), reason_code="three_denials_in_five_minutes", now=now)
    return event
