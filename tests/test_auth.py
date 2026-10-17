from sqlalchemy import select

from sentinela import create_app
from sentinela.extensions import db
from sentinela.models import User
from conftest import TEST_PASSWORD, token_from


def test_successful_login_and_no_external_redirect(client, login):
    response = login(" ADMIN@EXAMPLE.TEST ")
    assert response.status_code == 302
    assert response.location == "/"
    with client.session_transaction() as session:
        assert "_user_id" in session
        assert session.permanent
    assert client.get("/login?next=https://untrusted.example").location == "/"


def test_login_ignores_untrusted_next(client):
    token = token_from(client.get("/login?next=https://untrusted.example"))
    response = client.post("/login?next=https://untrusted.example", data={
        "email": "admin@example.test", "password": TEST_PASSWORD, "csrf_token": token})
    assert response.location == "/"


def test_wrong_and_unknown_credentials_share_error(client, login):
    for email in ("admin@example.test", "unknown@example.test"):
        response = login(email, "wrong-password")
        assert response.status_code == 401
        assert "E-mail ou senha inválidos." in response.text
        assert client.get("/").status_code == 302


def test_csrf_on_login(client):
    response = client.post("/login", data={"email": "admin@example.test", "password": TEST_PASSWORD})
    assert response.status_code == 400
    assert client.get("/").status_code == 302


def test_inactive_account_and_existing_session(app, client, login):
    login()
    with app.app_context():
        user = db.session.scalar(select(User).where(User.email == "admin@example.test"))
        user.active = False
        db.session.commit()
    assert client.get("/").status_code == 302
    assert login().status_code == 401


def test_password_hashing_and_policy():
    user = User()
    user.set_password(TEST_PASSWORD)
    assert user.password_hash != TEST_PASSWORD
    assert user.password_hash.startswith("scrypt:")
    assert user.check_password(TEST_PASSWORD)
    assert not user.check_password("wrong")
    for password in ("short", "a" * 129):
        try:
            user.set_password(password)
        except ValueError:
            pass
        else:
            raise AssertionError("Password policy not enforced")


def test_login_rate_limit(monkeypatch):
    monkeypatch.setenv("SENTINELA_ENV", "development")
    app = create_app({"TESTING": True, "SECRET_KEY": "test-rate-limiter", "SQLALCHEMY_DATABASE_URI": "sqlite://"})
    with app.app_context():
        db.create_all()
        client = app.test_client()
        for _ in range(5):
            token = token_from(client.get("/login"))
            response = client.post("/login", data={"email": "absent@example.test", "password": TEST_PASSWORD, "csrf_token": token})
            assert response.status_code == 401
        token = token_from(client.get("/login"))
        response = client.post("/login", data={"email": "absent@example.test", "password": TEST_PASSWORD, "csrf_token": token})
        assert response.status_code == 429
        assert "Muitas tentativas" in response.text
        assert "Retry-After" in response.headers
        db.session.remove()
        db.drop_all()


def test_setup_local_is_repeatable(app):
    runner = app.test_cli_runner()
    result = runner.invoke(args=["setup-local"])
    assert result.exit_code == 0
    assert "Já existe usuário" in result.output
