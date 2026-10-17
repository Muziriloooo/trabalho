import re

import pytest
from werkzeug.security import generate_password_hash

from sentinela import create_app
from sentinela.extensions import db
from sentinela.models import Organization, User

TEST_PASSWORD = "Local-test-only-2026!"
TEST_HASH = generate_password_hash(TEST_PASSWORD)


@pytest.fixture
def app(monkeypatch):
    monkeypatch.setenv("SENTINELA_ENV", "development")
    app = create_app({"TESTING": True, "SECRET_KEY": "test-session-key-only",
                      "SQLALCHEMY_DATABASE_URI": "sqlite://", "RATELIMIT_ENABLED": False})
    # Rota apenas da instância de teste para exercitar o handler 500 real.
    @app.get("/test-internal-failure")
    def fail():
        raise RuntimeError("internal-sensitive-detail")

    with app.app_context():
        db.create_all()
        org = Organization(name="Empresa de teste")
        other = Organization(name="Outra organização")
        db.session.add_all([org, other])
        db.session.flush()
        for email, role, organization in [
            ("admin@example.test", "organization_admin", org),
            ("operator@example.test", "operator", org),
            ("physical@example.test", "access_user", org),
            ("platform@example.test", "platform_admin", None),
            ("other@example.test", "organization_admin", other),
        ]:
            db.session.add(User(email=email, password_hash=TEST_HASH, role=role, organization=organization))
        db.session.commit()
    yield app
    with app.app_context():
        db.session.remove()
        db.drop_all()
        db.engine.dispose()


@pytest.fixture
def client(app):
    return app.test_client()


def token_from(response):
    return re.search(r'name="csrf_token"[^>]*value="([^"]+)"', response.text).group(1)


@pytest.fixture
def login(client):
    def perform(email="admin@example.test", password=TEST_PASSWORD):
        token = token_from(client.get("/login"))
        return client.post("/login", data={"email": email, "password": password, "csrf_token": token})
    return perform
