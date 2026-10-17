"""Configuração calculada na criação da aplicação, sem segredos no código."""
import os
from datetime import timedelta


def environment_config():
    environment = os.getenv("SENTINELA_ENV", "development")
    if environment not in {"development", "production"}:
        raise ValueError("SENTINELA_ENV deve ser development ou production.")
    production = environment == "production"
    secret = os.getenv("SECRET_KEY")
    database = os.getenv("DATABASE_URL")
    if production and (not secret or len(secret) < 32 or not database):
        raise ValueError("Produção exige SECRET_KEY com pelo menos 32 caracteres e DATABASE_URL.")
    return {
        "ENVIRONMENT": environment,
        "SECRET_KEY": secret,
        "SQLALCHEMY_DATABASE_URI": database or "sqlite:///sentinela.db",
        "SQLALCHEMY_TRACK_MODIFICATIONS": False,
        "SESSION_COOKIE_HTTPONLY": True,
        "SESSION_COOKIE_SAMESITE": "Lax",
        "SESSION_COOKIE_SECURE": production,
        "PERMANENT_SESSION_LIFETIME": timedelta(hours=8),
        "REMEMBER_COOKIE_HTTPONLY": True,
        "REMEMBER_COOKIE_SECURE": production,
        "MAX_CONTENT_LENGTH": 64 * 1024,
        "WTF_CSRF_TIME_LIMIT": 7200,
        "RATELIMIT_STORAGE_URI": "memory://",
        "RATELIMIT_ENABLED": True,
        "RATELIMIT_HEADERS_ENABLED": True,
    }
