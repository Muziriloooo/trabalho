from pathlib import Path

import pytest
from flask_migrate import downgrade, upgrade
from sqlalchemy import inspect
from sqlalchemy.exc import IntegrityError

from sentinela import create_app
from sentinela.extensions import db
from sentinela.models import Site, User
from conftest import TEST_HASH


def test_foreign_keys_and_role_constraints(app):
    with app.app_context():
        db.session.add(Site(name="Invalid site", organization_id=999999))
        with pytest.raises(IntegrityError):
            db.session.commit()
        db.session.rollback()
        db.session.add(User(email="invalid@example.test", role="operator", password_hash=TEST_HASH))
        with pytest.raises(IntegrityError):
            db.session.commit()
        db.session.rollback()


def test_versioned_migration_roundtrip_and_bootstrap(tmp_path, monkeypatch):
    monkeypatch.setenv("SENTINELA_ENV", "development")
    database = tmp_path / "migration.db"
    app = create_app({"TESTING": True, "SQLALCHEMY_DATABASE_URI": f"sqlite:///{database}", "RATELIMIT_ENABLED": False})
    migrations = str(Path(__file__).resolve().parents[1] / "migrations")
    with app.app_context():
        assert app.test_client().get("/health").status_code == 503
        upgrade(directory=migrations)
        upgrade(directory=migrations)
        assert {"organization", "site", "user"} <= set(inspect(db.engine).get_table_names())
        assert app.test_client().get("/health").status_code == 200
        runner = app.test_cli_runner()
        result = runner.invoke(args=["setup-local"], input="first@example.test\nA-local-test-password!\nA-local-test-password!\n")
        assert result.exit_code == 0, result.output
        assert "Administrador local criado" in result.output
        assert "Já existe usuário" in runner.invoke(args=["setup-local"]).output
        downgrade(directory=migrations, revision="base")
        assert "user" not in inspect(db.engine).get_table_names()
        upgrade(directory=migrations)
        assert "user" in inspect(db.engine).get_table_names()
        db.session.remove()
        db.engine.dispose()


def test_production_requires_explicit_configuration(monkeypatch):
    monkeypatch.setenv("SENTINELA_ENV", "production")
    monkeypatch.delenv("SECRET_KEY", raising=False)
    monkeypatch.delenv("DATABASE_URL", raising=False)
    with pytest.raises(ValueError, match="Produção exige"):
        create_app()


def test_secure_production_cookies_and_headers(monkeypatch):
    monkeypatch.setenv("SENTINELA_ENV", "production")
    monkeypatch.setenv("SECRET_KEY", "test-only-production-key-with-enough-length")
    monkeypatch.setenv("DATABASE_URL", "sqlite://")
    app = create_app({"TESTING": True, "RATELIMIT_ENABLED": False})
    response = app.test_client().get("/login")
    assert "Secure" in response.headers["Set-Cookie"]
    assert "HttpOnly" in response.headers["Set-Cookie"]
    assert "SameSite=Lax" in response.headers["Set-Cookie"]
    assert response.headers["Strict-Transport-Security"] == "max-age=31536000"
