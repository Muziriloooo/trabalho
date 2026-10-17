import os
import secrets
import sqlite3
from pathlib import Path

from dotenv import load_dotenv
from flask import Flask, render_template
from sqlalchemy import event
from sqlalchemy.engine import Engine

from config import environment_config
from .extensions import csrf, db, limiter, login_manager, migrate


@event.listens_for(Engine, "connect")
def sqlite_foreign_keys(connection, _):
    if isinstance(connection, sqlite3.Connection):
        connection.execute("PRAGMA foreign_keys=ON")


def create_app(test_config=None):
    load_dotenv(Path(__file__).resolve().parent.parent / ".env", override=False)
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_mapping(environment_config())
    if test_config:
        app.config.update(test_config)
    Path(app.instance_path).mkdir(parents=True, exist_ok=True)
    if not app.config["SECRET_KEY"]:
        if app.testing:
            app.config["SECRET_KEY"] = secrets.token_hex(32)
        else:
            key_path = Path(app.instance_path) / "dev-secret"
            try:
                descriptor = os.open(key_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            except FileExistsError:
                pass
            else:
                with os.fdopen(descriptor, "w") as stream:
                    stream.write(secrets.token_hex(32))
            app.config["SECRET_KEY"] = key_path.read_text().strip()
            if len(app.config["SECRET_KEY"]) < 32:
                raise ValueError("A chave local em instance/dev-secret é inválida.")
    db.init_app(app)
    migrate.init_app(app, db, render_as_batch=True)
    login_manager.init_app(app)
    login_manager.login_view = "auth.login"
    login_manager.login_message = "Entre para acessar o console."
    csrf.init_app(app)
    limiter.init_app(app)
    from .models import User

    @login_manager.user_loader
    def load_user(user_id):
        try:
            user = db.session.get(User, int(user_id))
        except (ValueError, TypeError):
            return None
        return user if user and user.active else None

    from .auth.routes import bp as auth_bp
    from .dashboard.routes import bp as dashboard_bp
    from .core.routes import bp as core_bp
    from .cli import setup_local
    app.register_blueprint(auth_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(core_bp)
    app.cli.add_command(setup_local)

    for code in (400, 403, 404, 413, 429, 500):
        def handle_error(error, status=code):
            if status == 500:
                db.session.rollback()
            return render_template("errors/error.html", code=status), status
        app.register_error_handler(code, handle_error)

    @app.after_request
    def secure_headers(response):
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; "
            "font-src 'self'; connect-src 'self'; object-src 'none'; base-uri 'self'; "
            "form-action 'self'; frame-ancestors 'none'"
        )
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "same-origin"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        response.headers["X-Frame-Options"] = "DENY"
        if app.config["ENVIRONMENT"] == "production":
            response.headers["Strict-Transport-Security"] = "max-age=31536000"
        if response.mimetype == "text/html":
            response.headers["Cache-Control"] = "no-store"
        return response

    return app
