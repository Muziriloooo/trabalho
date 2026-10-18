import click
from datetime import timedelta
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


@click.command("process-analysis")
@click.option("--limit", type=click.IntRange(1, 50), default=10, show_default=True)
@click.option("--recover-stale", is_flag=True, help="Após parar workers antigos, recupera tarefas interrompidas há mais de 5 minutos.")
@with_appcontext
def process_analysis(limit, recover_stale):
    """Processa tarefas pendentes uma vez, em processo separado do servidor web."""
    from sqlalchemy import update
    from .models import AnalysisJob, utcnow
    from .services.analysis import run_job
    if recover_stale:
        db.session.execute(update(AnalysisJob).where(AnalysisJob.status == "running", AnalysisJob.started_at < utcnow() - timedelta(minutes=5))
                           .values(status="pending", reason_code="recovered_after_interruption"))
        db.session.commit()
    ids = list(db.session.scalars(select(AnalysisJob.id).where(AnalysisJob.status == "pending").order_by(AnalysisJob.id).limit(limit)))
    count = sum(int(run_job(job_id)) for job_id in ids)
    click.echo(f"Tarefas processadas: {count}. Consulte o resultado em Eventos.")


@click.command('purge-verification-tests')
@with_appcontext
def purge_verification_tests():
    """Exclui conteúdo artificial expirado/revogado e desafios antigos; não toca em imagens."""
    from sqlalchemy import delete
    from .models import VerificationChallenge, VerificationEnrollment, VerificationPolicy, utcnow
    from .services.verification import erase
    now=utcnow()
    rows=db.session.scalars(select(VerificationEnrollment).outerjoin(VerificationPolicy,
         VerificationPolicy.organization_id==VerificationEnrollment.organization_id).where(VerificationEnrollment.ciphertext.is_not(None),
         (VerificationEnrollment.expires_at<=now) | (VerificationEnrollment.revoked_at.is_not(None)) |
         (VerificationPolicy.id.is_(None)) | (VerificationPolicy.enabled.is_(False)) |
         (VerificationEnrollment.policy_version!=VerificationPolicy.version) |
         (VerificationEnrollment.model_version!=VerificationPolicy.model_version))).all()
    for row in rows:erase(row,now)
    db.session.execute(delete(VerificationChallenge).where(VerificationChallenge.expires_at < now-timedelta(days=1)))
    db.session.commit()
    click.echo(f'Referências sintéticas excluídas: {len(rows)}. Nenhum dado facial real é processado.')
