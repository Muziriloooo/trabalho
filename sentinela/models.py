"""Entidades mínimas da Fase 1; sem dados de câmeras ou biometria."""
from datetime import datetime, timezone

from flask_login import UserMixin
from sqlalchemy import CheckConstraint
from werkzeug.security import check_password_hash, generate_password_hash

from .extensions import db


def utcnow():
    return datetime.now(timezone.utc)


class Organization(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    status = db.Column(db.String(20), nullable=False, default="active")
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utcnow)
    __table_args__ = (CheckConstraint("status in ('active', 'inactive')", name="organization_status"),)


class Site(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    organization_id = db.Column(db.Integer, db.ForeignKey("organization.id"), nullable=False, index=True)
    name = db.Column(db.String(120), nullable=False)
    location_description = db.Column(db.String(255))
    timezone = db.Column(db.String(64), nullable=False, default="America/Sao_Paulo")
    status = db.Column(db.String(20), nullable=False, default="active")
    __table_args__ = (CheckConstraint("status in ('active', 'inactive')", name="site_status"),)


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
