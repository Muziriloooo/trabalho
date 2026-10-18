import pytest
from sqlalchemy import select

from sentinela.core.navigation import NAVIGATION
from sentinela.extensions import db
from sentinela.models import Organization, User
from conftest import token_from


def test_database_health(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json == {"status": "ok", "version": "0.10.0", "phase": 10}


@pytest.mark.parametrize("path", ["/", *[f"/modules/{item[3]}" for item in NAVIGATION if item[3]]])
def test_console_requires_authentication(client, path):
    response = client.get(path)
    assert response.status_code == 302
    assert "/login" in response.location


def test_dashboard_and_org_context(client, login):
    assert login().status_code == 302
    response = client.get("/")
    assert response.status_code == 200
    assert "Empresa de teste" in response.text
    assert "Outra organização" not in response.text
    assert "Indicadores operacionais" in response.text
    assert "Nenhum evento no período" in response.text
    assert "DADOS DE EXEMPLO" not in response.text
    assert "activity-chart" in response.text
    assert "Últimos 20 eventos do período" in response.text
    assert response.text.count('class="metric-card"') == 12
    assert response.headers["Cache-Control"] == "no-store"


@pytest.mark.parametrize("slug", [item[3] for item in NAVIGATION if item[0] == "core.module"])
def test_future_pages_are_explicit(client, login, slug):
    login()
    response = client.get(f"/modules/{slug}")
    assert response.status_code == 200
    assert "AINDA NÃO IMPLEMENTADO" in response.text
    assert "somente navegação" in response.text
    assert 'aria-current="page"' in response.text
    assert "&lt;Macro" not in response.text


@pytest.mark.parametrize("email", ["physical@example.test", "platform@example.test"])
def test_sensitive_console_is_not_implicitly_granted(client, login, email):
    login(email)
    assert client.get("/").status_code == 403
    assert client.get("/modules/cameras").status_code == 403


def test_operator_can_view_foundation(client, login):
    login("operator@example.test")
    assert client.get("/").status_code == 200


def test_other_organization_sees_own_context(client, login):
    login("other@example.test")
    response = client.get("/")
    assert "Outra organização" in response.text
    assert "Empresa de teste" not in response.text


def test_inactive_organization_denied(app, client, login):
    login()
    with app.app_context():
        org = db.session.scalar(select(Organization).where(Organization.name == "Empresa de teste"))
        org.status = "inactive"
        db.session.commit()
    assert client.get("/").status_code == 403


def test_404(client):
    response = client.get("/does-not-exist")
    assert response.status_code == 404
    assert "Página não encontrada" in response.text


def test_unknown_module(client, login):
    login()
    assert client.get("/modules/unknown").status_code == 404


def test_500_is_safe(app, client):
    app.config["PROPAGATE_EXCEPTIONS"] = False
    response = client.get("/test-internal-failure")
    assert response.status_code == 500
    assert "Não foi possível concluir" in response.text
    assert "internal-sensitive-detail" not in response.text


def test_security_headers(client):
    response = client.get("/login")
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["X-Frame-Options"] == "DENY"
    assert "frame-ancestors 'none'" in response.headers["Content-Security-Policy"]
    assert "'unsafe-inline'" not in response.headers["Content-Security-Policy"]
    assert "camera=()" in response.headers["Permissions-Policy"]


def test_html_autoescape(app, client, login):
    with app.app_context():
        user = db.session.scalar(select(User).where(User.email == "admin@example.test"))
        user.organization.name = '<script>alert("xss")</script>'
        db.session.commit()
    login()
    response = client.get("/")
    assert '<script>alert("xss")</script>' not in response.text
    assert "&lt;script&gt;" in response.text


@pytest.mark.parametrize("path", ["css/app.css", "js/app.js", "js/dashboard.js", "vendor/chart.umd.js", "vendor/lucide.min.js", "img/mark.svg"])
def test_local_assets(client, path):
    response = client.get(f"/static/{path}")
    assert response.status_code == 200
    assert len(response.data) > 100


def test_logout_requires_post_and_csrf(client, login):
    login()
    assert client.get("/logout").status_code == 405
    assert client.post("/logout").status_code == 400
    token = token_from(client.get("/"))
    response = client.post("/logout", data={"csrf_token": token})
    assert response.status_code == 302
    assert client.get("/").status_code == 302
