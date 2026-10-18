"""Entidades das Fases 1–4, sem dados biométricos."""
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
