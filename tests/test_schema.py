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


def test_upgrade_preserves_phase1_rows_and_scopes_are_not_granted_implicitly(tmp_path, monkeypatch):
    from sqlalchemy import text
    monkeypatch.setenv("SENTINELA_ENV", "development")
    app = create_app({"TESTING": True, "SQLALCHEMY_DATABASE_URI": f"sqlite:///{tmp_path / 'legacy.db'}", "RATELIMIT_ENABLED": False})
    directory = str(Path(__file__).resolve().parents[1] / "migrations")
    with app.app_context():
        upgrade(directory=directory, revision="7af3da11c6ea")
        db.session.execute(text("INSERT INTO organization (id,name,status,created_at) VALUES (1,'Legacy','active',CURRENT_TIMESTAMP),(2,'Legacy 2','active',CURRENT_TIMESTAMP)"))
        db.session.execute(text("INSERT INTO site (id,organization_id,name,timezone,status) VALUES (1,1,'Existing site','America/Sao_Paulo','active')"))
        db.session.execute(text("INSERT INTO user (id,organization_id,email,password_hash,role,active,created_at) VALUES (1,1,'legacy@example.test',:hash,'operator',1,CURRENT_TIMESTAMP)"), {"hash": TEST_HASH})
        db.session.commit()
        upgrade(directory=directory)
        assert db.session.execute(text("SELECT name,identifier FROM organization WHERE id=1")).one() == ("Legacy", "org-1")
        assert db.session.execute(text("SELECT identifier FROM site WHERE id=1")).scalar() == "site-1"
        assert db.session.execute(text("SELECT password_hash FROM user WHERE id=1")).scalar() == TEST_HASH
        assert db.session.execute(text("SELECT COUNT(*) FROM role_assignment")).scalar() == 0
        db.session.commit()
        downgrade(directory=directory, revision="7af3da11c6ea")
        assert db.session.execute(text("SELECT name FROM site WHERE id=1")).scalar() == "Existing site"
        db.session.commit()
        upgrade(directory=directory)
        assert db.session.execute(text("SELECT name FROM organization WHERE id=2")).scalar() == "Legacy 2"
        db.session.remove()
        db.engine.dispose()


def test_phase7_upgrade_preserves_camera_and_existing_history(tmp_path, monkeypatch):
    from sentinela.models import Camera, CameraHealthEvent, Organization
    monkeypatch.setenv("SENTINELA_ENV", "development")
    app = create_app({"TESTING": True, "SQLALCHEMY_DATABASE_URI": f"sqlite:///{tmp_path / 'phase4.db'}", "RATELIMIT_ENABLED": False})
    directory = str(Path(__file__).resolve().parents[1] / "migrations")
    with app.app_context():
        upgrade(directory=directory, revision="78f63a927cf9")
        org = Organization(name="Existing organization")
        db.session.add(org); db.session.flush()
        user = User(email="existing@example.test", organization_id=org.id, role="organization_admin", password_hash=TEST_HASH)
        site = Site(name="Existing site", organization_id=org.id)
        db.session.add_all([user, site]); db.session.flush()
        camera = Camera(name="Existing camera", identifier="existing", organization_id=org.id, site_id=site.id, created_by=user.id)
        db.session.add(camera); db.session.flush()
        history = CameraHealthEvent(organization_id=org.id, camera_id=camera.id, event_type="demo", reason_code="synthetic_video")
        db.session.add(history); db.session.commit()
        camera_id, history_id = camera.id, history.id
        upgrade(directory=directory)
        assert db.session.get(Camera, camera_id).name == "Existing camera"
        assert db.session.get(CameraHealthEvent, history_id).event_type == "demo"
        assert {"analysis_job", "alert", "access_credential"} <= set(inspect(db.engine).get_table_names())
        downgrade(directory=directory, revision="78f63a927cf9")
        assert db.session.get(Camera, camera_id).name == "Existing camera"
        assert "alert" not in inspect(db.engine).get_table_names()
        upgrade(directory=directory)
        assert app.test_client().get("/health").status_code == 200
        db.session.remove(); db.engine.dispose()


def test_phase10_upgrade_and_downgrade_preserve_populated_phase7(tmp_path,monkeypatch):
    from datetime import date
    from sentinela.models import AccessCredential, AccessEvent, AccessPermission, AccessPoint, AccessSubject, Organization, ReportRun, VerificationPolicy
    from sentinela.services.access import issue
    from sentinela.services import verification
    from cryptography.fernet import Fernet
    from sqlalchemy import select
    monkeypatch.setenv('SENTINELA_ENV','development')
    app=create_app({'TESTING':True,'SQLALCHEMY_DATABASE_URI':f"sqlite:///{tmp_path / 'phase7.db'}",'RATELIMIT_ENABLED':False,'BIOMETRIC_TEST_KEY':Fernet.generate_key()})
    directory=str(Path(__file__).resolve().parents[1]/'migrations')
    with app.app_context():
        upgrade(directory=directory,revision='0e0fdb6387b6')
        org=Organization(name='Existing phase7');db.session.add(org);db.session.flush()
        user=User(email='phase7@example.test',organization_id=org.id,role='organization_admin',password_hash=TEST_HASH)
        site=Site(name='Existing site',organization_id=org.id)
        subject=AccessSubject(organization_id=org.id,display_name='Existing subject',external_reference='existing')
        db.session.add_all([user,site,subject]);db.session.flush()
        point=AccessPoint(organization_id=org.id,site_id=site.id,name='Existing point')
        permission=AccessPermission(organization_id=org.id,site_id=site.id,subject_id=subject.id)
        db.session.add_all([point,permission]);db.session.flush()
        credential,token=issue(subject,300)
        event=AccessEvent(organization_id=org.id,site_id=site.id,access_point_id=point.id,actor_id=user.id,decision='denied',reason_code='invalid')
        db.session.add(event);db.session.commit()
        event_id,credential_id=event.id,credential.id
        upgrade(directory=directory)
        policy=VerificationPolicy(organization_id=org.id,enabled=True,purpose='test',controller='test',legal_review='test',risk_review='test',necessity_review='test',workplace_review='test',alternative='token')
        db.session.add(policy);db.session.flush()
        verification.enroll(subject,policy,user.id,'test')
        challenge,result=verification.start(point,token,user.id)
        assert challenge and result is None
        assert verification.finish(challenge,point,user.id,'match').outcome=='approved'
        db.session.add(ReportRun(organization_id=org.id,generated_by=user.id,organization_name=org.name,generator_name=user.email,
            kind='access',purpose='test',start_date=date(2026,10,15),end_date=date(2026,10,15),source='all',site_ids=[site.id],payload={'rows':[]}))
        db.session.commit()
        downgrade(directory=directory,revision='0e0fdb6387b6')
        assert db.session.get(AccessEvent,event_id).decision=='denied'
        assert db.session.get(AccessCredential,credential_id).used_at
        assert 'report_run' not in inspect(db.engine).get_table_names()
        db.session.commit();upgrade(directory=directory)
        assert db.session.scalar(select(AccessSubject.display_name))=='Existing subject'
        assert app.test_client().get('/health').status_code==200
        db.session.remove();db.engine.dispose()
