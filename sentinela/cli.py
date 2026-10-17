import click
from flask.cli import with_appcontext
from sqlalchemy import select

from .extensions import db
from .models import Organization, User


@click.command("setup-local")
@with_appcontext
def setup_local():
    """Cria o primeiro administrador local após aplicar as migrações."""
    if db.session.scalar(select(User.id).limit(1)) is not None:
        click.echo("Já existe usuário local. Nenhum cadastro foi alterado.")
        return
    email = click.prompt("E-mail do administrador").strip().lower()
    if len(email) > 254 or "@" not in email or len(email.split("@")) != 2 or not all(email.split("@")):
        raise click.ClickException("Informe um e-mail válido.")
    password = click.prompt("Senha (12 a 128 caracteres)", hide_input=True, confirmation_prompt=True)
    organization = Organization(name="Organização local")
    user = User(email=email, role="organization_admin", organization=organization)
    try:
        user.set_password(password)
    except ValueError as error:
        raise click.ClickException(str(error)) from error
    db.session.add_all([organization, user])
    db.session.commit()
    click.echo("Administrador local criado. Use suas credenciais na tela de login.")
