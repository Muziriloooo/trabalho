from flask import Blueprint, flash, redirect, render_template, session, url_for
from flask_login import current_user, login_required, login_user, logout_user
from flask_wtf import FlaskForm
from sqlalchemy import select
from werkzeug.security import check_password_hash, generate_password_hash
from wtforms import PasswordField, StringField, SubmitField
from wtforms.validators import DataRequired, Length

from ..extensions import db, limiter
from ..models import User

bp = Blueprint("auth", __name__)
# Equaliza o custo da verificação quando o e-mail não existe.
DUMMY_HASH = generate_password_hash("sentinela-dummy-not-a-login", method="scrypt")


class LoginForm(FlaskForm):
    email = StringField("E-mail", validators=[DataRequired(), Length(max=254)])
    password = PasswordField("Senha", validators=[DataRequired(), Length(max=128)])
    submit = SubmitField("Entrar no console")


@bp.route("/login", methods=["GET", "POST"])
@limiter.limit("5 per minute", methods=["POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("organizations.index" if current_user.role == "platform_admin" else "dashboard.index"))
    form = LoginForm()
    if form.validate_on_submit():
        email = form.email.data.strip().lower()
        user = db.session.scalar(select(User).where(User.email == email))
        valid = check_password_hash(user.password_hash if user else DUMMY_HASH, form.password.data)
        if user and valid and user.active:
            session.clear()
            login_user(user, remember=False, fresh=True)
            session.permanent = True
            return redirect(url_for("organizations.index" if current_user.role == "platform_admin" else "dashboard.index"))
        flash("E-mail ou senha inválidos.", "error")
        return render_template("auth/login.html", form=form), 401
    return render_template("auth/login.html", form=form), 400 if form.is_submitted() else 200


@bp.post("/logout")
@login_required
def logout():
    logout_user()
    session.clear()
    return redirect(url_for("auth.login"))
