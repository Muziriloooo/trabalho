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


@click.command("create-account")
@click.option("--platform", is_flag=True, help="Administrador de metadados da plataforma, sem acesso a câmeras.")
@click.option("--organization", "identifier", help="Identificador de uma organização existente para seu administrador.")
@with_appcontext
def create_account(platform, identifier):
    """Provisionamento local de administradores pelo operador da instalação."""
    if platform == bool(identifier):
        raise click.ClickException("Escolha --platform OU --organization IDENTIFICADOR.")
    organization = None
    if identifier:
        organization = db.session.scalar(select(Organization).where(Organization.identifier == identifier))
        if not organization:
            raise click.ClickException("Organização não encontrada.")
    email = click.prompt("E-mail").strip().lower()
    if len(email) > 254 or len(email.split("@")) != 2 or not all(email.split("@")) or any(c.isspace() for c in email):
        raise click.ClickException("E-mail inválido.")
    if db.session.scalar(select(User.id).where(User.email == email)):
        raise click.ClickException("E-mail indisponível.")
    password = click.prompt("Senha (12 a 128 caracteres)", hide_input=True, confirmation_prompt=True)
    user = User(email=email, role="platform_admin" if platform else "organization_admin", organization=organization)
    try:
        user.set_password(password)
    except ValueError as error:
        raise click.ClickException(str(error)) from error
    db.session.add(user)
    db.session.commit()
    click.echo("Conta criada sem alterar usuários existentes.")
