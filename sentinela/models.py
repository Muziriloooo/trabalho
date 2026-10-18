"""Entidades das Fases 1–10; verificação exclusivamente com dados artificiais."""
from datetime import datetime, timezone
from uuid import uuid4

from flask_login import UserMixin
from sqlalchemy import CheckConstraint, ForeignKeyConstraint, Index, UniqueConstraint
from werkzeug.security import check_password_hash, generate_password_hash

from .extensions import db


def utcnow():
    return datetime.now(timezone.utc)


class Organization(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    identifier = db.Column(db.String(64), nullable=False, default=lambda: uuid4().hex[:12])
    responsible = db.Column(db.String(120), nullable=False, default="")
    status = db.Column(db.String(20), nullable=False, default="active")
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utcnow)
    __table_args__ = (CheckConstraint("status in ('active', 'inactive')", name="organization_status"),
                      Index("uq_organization_identifier", "identifier", unique=True))


class Site(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    organization_id = db.Column(db.Integer, db.ForeignKey("organization.id"), nullable=False, index=True)
    name = db.Column(db.String(120), nullable=False)
    identifier = db.Column(db.String(64), nullable=False, default=lambda: uuid4().hex[:12])
    responsible = db.Column(db.String(120), nullable=False, default="")
    address = db.Column(db.String(255), nullable=False, default="")
    location_description = db.Column(db.String(255))
    timezone = db.Column(db.String(64), nullable=False, default="America/Sao_Paulo")
    status = db.Column(db.String(20), nullable=False, default="active")
    __table_args__ = (
        CheckConstraint("status in ('active', 'inactive')", name="site_status"),
        Index("uq_site_org_identifier", "organization_id", "identifier", unique=True),
        Index("uq_site_id_org", "id", "organization_id", unique=True),
    )


class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    organization_id = db.Column(db.Integer, db.ForeignKey("organization.id"), nullable=True, index=True)
    email = db.Column(db.String(254), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(32), nullable=False, default="operator")
    active = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utcnow)
    organization = db.relationship(Organization)
    __table_args__ = (
        Index("uq_user_id_org", "id", "organization_id", unique=True),
        CheckConstraint("role in ('platform_admin', 'organization_admin', 'supervisor', 'operator', 'access_user')", name="user_role"),
        CheckConstraint("role = 'platform_admin' OR organization_id IS NOT NULL", name="user_organization"),
    )

    @property
    def is_active(self):
        return self.active

    def set_password(self, password):
        if len(password) < 12 or len(password) > 128:
            raise ValueError("Use uma senha de 12 a 128 caracteres.")
        self.password_hash = generate_password_hash(password, method="scrypt")

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)


class RoleAssignment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    organization_id = db.Column(db.Integer, db.ForeignKey("organization.id"), nullable=False, index=True)
    user_id = db.Column(db.Integer, nullable=False, index=True)
    site_id = db.Column(db.Integer, nullable=True)
    role = db.Column(db.String(32), nullable=False)
    granted_by = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utcnow)
    __table_args__ = (
        ForeignKeyConstraint(["user_id", "organization_id"], ["user.id", "user.organization_id"]),
        ForeignKeyConstraint(["site_id", "organization_id"], ["site.id", "site.organization_id"]),
        CheckConstraint("role in ('operator', 'supervisor')", name="assignment_role"),
        Index("uq_assignment_site", "user_id", "site_id", unique=True),
        Index("uq_assignment_global", "user_id", unique=True, sqlite_where=db.text("site_id IS NULL"), postgresql_where=db.text("site_id IS NULL")),
    )


class ConnectionSecret(db.Model):
    id = db.Column(db.String(32), primary_key=True, default=lambda: uuid4().hex)
    organization_id = db.Column(db.Integer, db.ForeignKey("organization.id"), nullable=False)
    ciphertext = db.Column(db.LargeBinary, nullable=False)
    __table_args__ = (Index("uq_secret_id_org", "id", "organization_id", unique=True),)


class Camera(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    organization_id = db.Column(db.Integer, db.ForeignKey("organization.id"), nullable=False, index=True)
    site_id = db.Column(db.Integer, nullable=False, index=True)
    name = db.Column(db.String(120), nullable=False)
    identifier = db.Column(db.String(64), nullable=False)
    manufacturer = db.Column(db.String(80), nullable=False, default="")
    model = db.Column(db.String(80), nullable=False, default="")
    location_description = db.Column(db.String(255), nullable=False, default="")
    protocol = db.Column(db.String(12), nullable=False, default="demo")
    gateway_path = db.Column(db.String(64), nullable=False, default="")
    connection_secret_reference = db.Column(db.String(32), nullable=True)
    enabled = db.Column(db.Boolean, nullable=False, default=True)
    connection_status = db.Column(db.String(20), nullable=False, default="unknown")
    last_seen_at = db.Column(db.DateTime(timezone=True))
    last_checked_at = db.Column(db.DateTime(timezone=True))
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utcnow)
    created_by = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    site = db.relationship(Site, foreign_keys=[site_id, organization_id], overlaps="")
    __table_args__ = (
        ForeignKeyConstraint(["site_id", "organization_id"], ["site.id", "site.organization_id"]),
        ForeignKeyConstraint(["connection_secret_reference", "organization_id"], ["connection_secret.id", "connection_secret.organization_id"]),
        UniqueConstraint("organization_id", "identifier"),
        Index("uq_camera_id_org", "id", "organization_id", unique=True),
        CheckConstraint("protocol in ('demo', 'rtsp', 'rtsps')", name="camera_protocol"),
        CheckConstraint("connection_status in ('unknown', 'online', 'offline', 'demo')", name="camera_status"),
    )


class CameraHealthEvent(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    organization_id = db.Column(db.Integer, nullable=False)
    camera_id = db.Column(db.Integer, nullable=False, index=True)
    event_type = db.Column(db.String(24), nullable=False)
    reason_code = db.Column(db.String(32), nullable=False)
    occurred_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utcnow)
    __table_args__ = (ForeignKeyConstraint(["camera_id", "organization_id"], ["camera.id", "camera.organization_id"], ondelete="CASCADE"),)


class AuditLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    organization_id = db.Column(db.Integer, db.ForeignKey("organization.id"), nullable=False, index=True)
    actor_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    action = db.Column(db.String(48), nullable=False)
    resource_type = db.Column(db.String(32), nullable=False)
    resource_id = db.Column(db.Integer, nullable=False)
    occurred_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utcnow)


class AnalysisPolicy(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    organization_id = db.Column(db.Integer, nullable=False)
    camera_id = db.Column(db.Integer, nullable=False, unique=True)
    enabled = db.Column(db.Boolean, nullable=False, default=False)
    motion_enabled = db.Column(db.Boolean, nullable=False, default=True)
    obstruction_enabled = db.Column(db.Boolean, nullable=False, default=True)
    motion_ratio = db.Column(db.Float, nullable=False, default=0.03)
    roi_x = db.Column(db.Float, nullable=False, default=0)
    roi_y = db.Column(db.Float, nullable=False, default=0)
    roi_w = db.Column(db.Float, nullable=False, default=1)
    roi_h = db.Column(db.Float, nullable=False, default=1)
    cooldown_seconds = db.Column(db.Integer, nullable=False, default=60)
    start_time = db.Column(db.String(5), nullable=False, default="00:00")
    end_time = db.Column(db.String(5), nullable=False, default="00:00")
    weekdays = db.Column(db.String(13), nullable=False, default="0,1,2,3,4,5,6")
    updated_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utcnow)
    __table_args__ = (
        ForeignKeyConstraint(["camera_id", "organization_id"], ["camera.id", "camera.organization_id"], ondelete="CASCADE"),
        CheckConstraint("motion_ratio >= 0.001 AND motion_ratio <= 1", name="analysis_sensitivity"),
        CheckConstraint("roi_x >= 0 AND roi_y >= 0 AND roi_w > 0 AND roi_h > 0 AND roi_x + roi_w <= 1.000001 AND roi_y + roi_h <= 1.000001", name="analysis_roi"),
        CheckConstraint("cooldown_seconds >= 10 AND cooldown_seconds <= 3600", name="analysis_cooldown"),
    )


class AnalysisJob(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    organization_id = db.Column(db.Integer, nullable=False)
    camera_id = db.Column(db.Integer, nullable=False, index=True)
    requested_by = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    status = db.Column(db.String(16), nullable=False, default="pending")
    reason_code = db.Column(db.String(48), nullable=False, default="")
    event_count = db.Column(db.Integer, nullable=False, default=0)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utcnow)
    started_at = db.Column(db.DateTime(timezone=True))
    finished_at = db.Column(db.DateTime(timezone=True))
    __table_args__ = (
        ForeignKeyConstraint(["camera_id", "organization_id"], ["camera.id", "camera.organization_id"], ondelete="CASCADE"),
        CheckConstraint("status in ('pending','running','completed','failed','skipped')", name="analysis_job_status"),
        Index("uq_analysis_active_camera", "camera_id", unique=True, sqlite_where=db.text("status IN ('pending','running')"), postgresql_where=db.text("status IN ('pending','running')")),
    )


class SecurityEvent(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    organization_id = db.Column(db.Integer, db.ForeignKey("organization.id"), nullable=False, index=True)
    site_id = db.Column(db.Integer, nullable=False, index=True)
    camera_id = db.Column(db.Integer, nullable=True)
    event_type = db.Column(db.String(40), nullable=False)
    severity = db.Column(db.String(16), nullable=False)
    source = db.Column(db.String(24), nullable=False)
    reason_code = db.Column(db.String(64), nullable=False, default="")
    occurred_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utcnow)
    __table_args__ = (
        ForeignKeyConstraint(["site_id", "organization_id"], ["site.id", "site.organization_id"]),
        ForeignKeyConstraint(["camera_id", "organization_id"], ["camera.id", "camera.organization_id"]),
        Index("uq_event_id_org_site", "id", "organization_id", "site_id", unique=True),
        CheckConstraint("severity in ('info','attention','critical')", name="event_severity"),
        CheckConstraint("source in ('synthetic','gateway','youtube_client','access_simulation')", name="event_source"),
    )


class EventGate(db.Model):
    id = db.Column(db.String(64), primary_key=True)
    next_allowed_at = db.Column(db.DateTime(timezone=True), nullable=False)


class Alert(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    organization_id = db.Column(db.Integer, nullable=False, index=True)
    site_id = db.Column(db.Integer, nullable=False, index=True)
    event_id = db.Column(db.Integer, nullable=False, unique=True)
    status = db.Column(db.String(16), nullable=False, default="new")
    assigned_to = db.Column(db.Integer, nullable=True)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utcnow)
    acknowledged_at = db.Column(db.DateTime(timezone=True))
    resolved_at = db.Column(db.DateTime(timezone=True))
    version = db.Column(db.Integer, nullable=False, default=0)
    event = db.relationship(SecurityEvent, foreign_keys=[event_id, organization_id, site_id])
    __table_args__ = (
        ForeignKeyConstraint(["event_id", "organization_id", "site_id"], ["security_event.id", "security_event.organization_id", "security_event.site_id"]),
        ForeignKeyConstraint(["assigned_to", "organization_id"], ["user.id", "user.organization_id"]),
        Index("uq_alert_id_org", "id", "organization_id", unique=True),
        CheckConstraint("status in ('new','acknowledged','in_review','resolved','discarded')", name="alert_status"),
    )


class AlertActivity(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    organization_id = db.Column(db.Integer, nullable=False)
    alert_id = db.Column(db.Integer, nullable=False, index=True)
    actor_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    action = db.Column(db.String(32), nullable=False)
    note = db.Column(db.String(500), nullable=False, default="")
    occurred_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utcnow)
    __table_args__ = (ForeignKeyConstraint(["alert_id", "organization_id"], ["alert.id", "alert.organization_id"]),)


class AccessSubject(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    organization_id = db.Column(db.Integer, db.ForeignKey("organization.id"), nullable=False, index=True)
    display_name = db.Column(db.String(120), nullable=False)
    external_reference = db.Column(db.String(64), nullable=False)
    active = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utcnow)
    __table_args__ = (UniqueConstraint("organization_id", "external_reference"), Index("uq_subject_id_org", "id", "organization_id", unique=True))


class AccessPoint(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    organization_id = db.Column(db.Integer, nullable=False)
    site_id = db.Column(db.Integer, nullable=False)
    name = db.Column(db.String(120), nullable=False)
    enabled = db.Column(db.Boolean, nullable=False, default=True)
    __table_args__ = (ForeignKeyConstraint(["site_id", "organization_id"], ["site.id", "site.organization_id"]),
                      Index("uq_point_id_org", "id", "organization_id", unique=True))


class AccessPermission(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    organization_id = db.Column(db.Integer, nullable=False)
    subject_id = db.Column(db.Integer, nullable=False)
    site_id = db.Column(db.Integer, nullable=False)
    weekdays = db.Column(db.String(13), nullable=False, default="0,1,2,3,4,5,6")
    start_time = db.Column(db.String(5), nullable=False, default="00:00")
    end_time = db.Column(db.String(5), nullable=False, default="00:00")
    __table_args__ = (ForeignKeyConstraint(["subject_id", "organization_id"], ["access_subject.id", "access_subject.organization_id"]),
                      ForeignKeyConstraint(["site_id", "organization_id"], ["site.id", "site.organization_id"]), UniqueConstraint("subject_id", "site_id"))


class AccessCredential(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    organization_id = db.Column(db.Integer, nullable=False)
    subject_id = db.Column(db.Integer, nullable=False)
    token_hash = db.Column(db.String(64), nullable=False, unique=True)
    credential_type = db.Column(db.String(16), nullable=False, default="one_time")
    expires_at = db.Column(db.DateTime(timezone=True), nullable=False)
    revoked_at = db.Column(db.DateTime(timezone=True))
    used_at = db.Column(db.DateTime(timezone=True))
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utcnow)
    __table_args__ = (ForeignKeyConstraint(["subject_id", "organization_id"], ["access_subject.id", "access_subject.organization_id"]),
                      CheckConstraint("credential_type = 'one_time'", name="credential_type"),
                      Index('uq_credential_id_org', 'id', 'organization_id', unique=True))


class AccessEvent(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    organization_id = db.Column(db.Integer, nullable=False, index=True)
    site_id = db.Column(db.Integer, nullable=False)
    access_point_id = db.Column(db.Integer, nullable=False)
    subject_id = db.Column(db.Integer, nullable=True)
    actor_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    decision = db.Column(db.String(16), nullable=False)
    reason_code = db.Column(db.String(32), nullable=False)
    method = db.Column(db.String(16), nullable=False, default="one_time")
    occurred_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utcnow)
    __table_args__ = (ForeignKeyConstraint(["access_point_id", "organization_id"], ["access_point.id", "access_point.organization_id"]),
                      ForeignKeyConstraint(["subject_id", "organization_id"], ["access_subject.id", "access_subject.organization_id"]),
                      ForeignKeyConstraint(["site_id", "organization_id"], ["site.id", "site.organization_id"]),
                      CheckConstraint("decision in ('allowed','denied')", name="access_decision"),
                      Index('uq_access_event_id_org_site', 'id', 'organization_id', 'site_id', unique=True))


class VerificationPolicy(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    organization_id = db.Column(db.Integer, db.ForeignKey('organization.id'), nullable=False, unique=True)
    enabled = db.Column(db.Boolean, nullable=False, default=False)
    version = db.Column(db.Integer, nullable=False, default=1)
    purpose = db.Column(db.String(500), nullable=False)
    controller = db.Column(db.String(120), nullable=False)
    legal_review = db.Column(db.String(500), nullable=False)
    risk_review = db.Column(db.String(500), nullable=False)
    necessity_review = db.Column(db.String(500), nullable=False)
    workplace_review = db.Column(db.String(500), nullable=False)
    alternative = db.Column(db.String(500), nullable=False)
    retention_days = db.Column(db.Integer, nullable=False, default=7)
    model_version = db.Column(db.String(40), nullable=False, default='synthetic-vector-v1')
    threshold = db.Column(db.Float, nullable=False, default=.95)
    updated_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utcnow)
    __table_args__ = (CheckConstraint('retention_days >= 1 AND retention_days <= 30', name='verification_retention'),
                      CheckConstraint('threshold >= 0.5 AND threshold <= 1', name='verification_threshold'))


class VerificationEnrollment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    organization_id = db.Column(db.Integer, nullable=False)
    subject_id = db.Column(db.Integer, nullable=False, unique=True)
    policy_version = db.Column(db.Integer, nullable=False)
    model_version = db.Column(db.String(40), nullable=False)
    ciphertext = db.Column(db.LargeBinary, nullable=True)
    authorization_reference = db.Column(db.String(240), nullable=False, default='')
    enrolled_by = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    enrolled_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utcnow)
    expires_at = db.Column(db.DateTime(timezone=True), nullable=False)
    revoked_at = db.Column(db.DateTime(timezone=True))
    __table_args__ = (ForeignKeyConstraint(['subject_id', 'organization_id'], ['access_subject.id', 'access_subject.organization_id']),)


class VerificationChallenge(db.Model):
    id = db.Column(db.String(32), primary_key=True, default=lambda: uuid4().hex)
    organization_id = db.Column(db.Integer, nullable=False)
    site_id = db.Column(db.Integer, nullable=False)
    point_id = db.Column(db.Integer, nullable=False)
    credential_id = db.Column(db.Integer, nullable=False)
    actor_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    expires_at = db.Column(db.DateTime(timezone=True), nullable=False)
    used_at = db.Column(db.DateTime(timezone=True))
    __table_args__ = (ForeignKeyConstraint(['point_id', 'organization_id'], ['access_point.id', 'access_point.organization_id']),
                      ForeignKeyConstraint(['site_id', 'organization_id'], ['site.id', 'site.organization_id']),
                      ForeignKeyConstraint(['credential_id','organization_id'], ['access_credential.id','access_credential.organization_id']))


class VerificationRecord(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    organization_id = db.Column(db.Integer, db.ForeignKey('organization.id'), nullable=False, index=True)
    site_id = db.Column(db.Integer, nullable=False)
    access_event_id = db.Column(db.Integer, nullable=False, unique=True)
    credential_id = db.Column(db.Integer, nullable=True)
    outcome = db.Column(db.String(32), nullable=False)
    model_version = db.Column(db.String(40), nullable=False, default='synthetic-vector-v1')
    occurred_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utcnow)
    __table_args__ = (ForeignKeyConstraint(['site_id', 'organization_id'], ['site.id', 'site.organization_id']),
                      ForeignKeyConstraint(['credential_id','organization_id'], ['access_credential.id','access_credential.organization_id']),
                      ForeignKeyConstraint(['access_event_id','organization_id','site_id'], ['access_event.id','access_event.organization_id','access_event.site_id']))


class OrganizationBranding(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    organization_id = db.Column(db.Integer, db.ForeignKey('organization.id'), nullable=False, unique=True)
    logo_png = db.Column(db.LargeBinary, nullable=False)


class ReportRun(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    identifier = db.Column(db.String(32), nullable=False, unique=True, default=lambda: uuid4().hex)
    organization_id = db.Column(db.Integer, db.ForeignKey('organization.id'), nullable=False, index=True)
    generated_by = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    organization_name = db.Column(db.String(120), nullable=False)
    generator_name = db.Column(db.String(254), nullable=False)
    kind = db.Column(db.String(32), nullable=False)
    purpose = db.Column(db.String(240), nullable=False)
    start_date = db.Column(db.Date, nullable=False)
    end_date = db.Column(db.Date, nullable=False)
    source = db.Column(db.String(24), nullable=False)
    site_ids = db.Column(db.JSON, nullable=False)
    payload = db.Column(db.JSON, nullable=False)
    logo_png = db.Column(db.LargeBinary, nullable=True)
    generated_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utcnow)
