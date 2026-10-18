from datetime import timedelta

import pytest
from cryptography.fernet import Fernet
from sqlalchemy import func, select

from sentinela.extensions import db
from sentinela.models import AccessCredential, AccessEvent, AccessPoint, AccessSubject, VerificationEnrollment, VerificationPolicy, VerificationRecord, utcnow
from sentinela.services import verification as service
from sentinela.services.access import decide
from test_access import access_case
from test_inventory import inventory, post


@pytest.fixture
def verification_case(app,inventory,access_case):
    app.config['BIOMETRIC_TEST_KEY']=Fernet.generate_key()
    with app.app_context():
        policy=VerificationPolicy(organization_id=inventory['organization'],enabled=True,purpose='Teste artificial autorizado',controller='Equipe de teste',
            legal_review='Referência teste',risk_review='Referência teste',necessity_review='Referência teste',workplace_review='Referência teste',alternative='Credencial não biométrica')
        db.session.add(policy);db.session.flush()
        row=service.enroll(db.session.get(AccessSubject,access_case['subject']),policy,inventory['admin'],'autorizacao-teste')
        db.session.commit()
        return {**access_case,'enrollment':row.id,'policy':policy.id}


def begin(app,inventory,case):
    point=db.session.get(AccessPoint,case['point'])
    challenge,result=service.start(point,case['token'],inventory['admin'])
    assert challenge and result is None
    db.session.commit()
    return point,challenge


def test_one_to_one_encrypted_reference_and_single_use(app,inventory,verification_case):
    with app.app_context():
        case=verification_case
        row=db.session.get(VerificationEnrollment,case['enrollment'])
        assert b'vector' not in row.ciphertext and b'synthetic-vector-v1' not in row.ciphertext
        point,challenge=begin(app,inventory,case)
        result=service.finish(challenge,point,inventory['admin'],'match');db.session.commit()
        assert result.outcome=='approved'
        event=db.session.get(AccessEvent,result.access_event_id)
        assert event.decision=='allowed' and event.method=='synthetic_1to1'
        assert db.session.get(AccessCredential,case['credential']).used_at
        with pytest.raises(service.VerificationUnavailable):service.finish(challenge,point,inventory['admin'],'match')
        db.session.rollback()
        _,invalid=service.start(point,case['token'],inventory['admin'])
        assert invalid.outcome=='invalid'


@pytest.mark.parametrize('scenario,outcome',[('mismatch','not_approved'),('quality','quality'),('retry','retry')])
def test_failure_does_not_consume_token_or_block_nonbiometric_alternative(app,inventory,verification_case,scenario,outcome):
    with app.app_context():
        case=verification_case;point,challenge=begin(app,inventory,case)
        result=service.finish(challenge,point,inventory['admin'],scenario);db.session.commit()
        assert result.outcome==outcome
        assert db.session.get(AccessCredential,case['credential']).used_at is None
        event=decide(point=point,token=case['token'],actor_id=inventory['admin']);db.session.commit()
        assert event.decision=='allowed'


@pytest.mark.parametrize('change',['revoked','expired','policy','model','key','production','credential'])
def test_current_authorization_model_key_and_environment_fail_closed(app,inventory,verification_case,change):
    with app.app_context():
        case=verification_case;point,challenge=begin(app,inventory,case)
        row=db.session.get(VerificationEnrollment,case['enrollment'])
        if change=='revoked':service.erase(row)
        if change=='expired':row.expires_at=utcnow()-timedelta(seconds=1)
        if change=='policy':db.session.get(VerificationPolicy,case['policy']).version+=1
        if change=='model':row.model_version='unvalidated-model'
        if change=='key':app.config['BIOMETRIC_TEST_KEY']=Fernet.generate_key()
        if change=='production':app.config['ENVIRONMENT']='production'
        if change=='credential':db.session.get(AccessCredential,case['credential']).revoked_at=utcnow()
        db.session.commit()
        result=service.finish(challenge,point,inventory['admin'],'match');db.session.commit()
        assert result.outcome==('invalid' if change=='credential' else 'unavailable')
        assert db.session.get(AccessEvent,result.access_event_id).decision=='denied'
        assert db.session.get(AccessCredential,case['credential']).used_at is None


def test_attempt_limit_is_temporary_and_alternative_stays_available(app,inventory,verification_case):
    with app.app_context():
        case=verification_case
        for _ in range(3):
            point,challenge=begin(app,inventory,case)
            assert service.finish(challenge,point,inventory['admin'],'mismatch').outcome=='not_approved'
            db.session.commit()
        _,result=service.start(point,case['token'],inventory['admin']);db.session.commit()
        assert result.outcome=='limited'
        assert decide(point=point,token=case['token'],actor_id=inventory['admin']).decision=='allowed'


def test_challenge_expires_and_is_bound_to_actor(app,inventory,verification_case):
    with app.app_context():
        point,challenge=begin(app,inventory,verification_case)
        with pytest.raises(service.VerificationUnavailable):service.finish(challenge,point,inventory['operator'],'match')
        with pytest.raises(service.VerificationUnavailable):service.finish(challenge,point,inventory['admin'],'match',now=utcnow()+timedelta(minutes=3))
        db.session.rollback()


def test_erasure_and_retention_cleanup_remove_content(app,inventory,verification_case):
    with app.app_context():
        row=db.session.get(VerificationEnrollment,verification_case['enrollment']);row.expires_at=utcnow()-timedelta(days=1);db.session.commit()
    result=app.test_cli_runner().invoke(args=['purge-verification-tests'])
    assert result.exit_code==0,result.output
    assert 'excluídas: 1' in result.output
    with app.app_context():
        row=db.session.get(VerificationEnrollment,verification_case['enrollment'])
        assert row.ciphertext is None and row.authorization_reference=='' and row.revoked_at


def test_web_flow_revalidates_scopes_and_hides_sensitive_material(app,client,login,inventory,verification_case):
    case=verification_case;login()
    response=post(client,'/verification',{'point_id':case['point'],'token':case['token'],'confirm':'y'})
    assert response.status_code==302 and '/verification/capture/' in response.location
    challenge_path=response.location
    response=post(client,challenge_path,{'scenario':'match','confirm':'y'})
    assert response.status_code==302
    page=client.get('/verification')
    assert 'Verificação simulada aprovada' in page.text
    assert case['token'] not in page.text and 'similarity' not in page.text and 'ciphertext' not in page.text
    assert page.headers['Cache-Control']=='no-store'
    post(client,'/logout',{});login('other@example.test');assert client.get(challenge_path).status_code==404
    post(client,'/logout',{});login('operator@example.test');assert client.get('/verification/enrollments').status_code==403
    assert client.get('/verification/policy').status_code==403
    assert post(client,'/verification',{'point_id':case['other_point'],'token':case['token'],'confirm':'y'}).status_code==422


def test_policy_and_enrollment_forms_require_documentation(client,login,inventory,access_case):
    login()
    assert post(client,'/verification/policy',{'enabled':'y','confirm':'y'}).status_code==422
    fields={key:'Referência do teste artificial' for key in ['purpose','controller','legal_review','necessity_review','risk_review','workplace_review','alternative']}
    fields.update(enabled='y',confirm='y',retention_days='7',threshold='.95')
    assert post(client,'/verification/policy',{**fields,'threshold':'nan'}).status_code==422
    assert post(client,'/verification/policy',fields).status_code==302
    assert post(client,'/verification/enrollments/new',{'subject_id':access_case['other_subject'],'authorization_reference':'test','confirm':'y'}).status_code==422
    assert post(client,'/verification/enrollments/new',{'subject_id':access_case['subject'],'authorization_reference':'test','confirm':'y'}).status_code==302


@pytest.mark.parametrize('path',['/verification','/verification/policy','/verification/enrollments/new'])
def test_verification_requires_csrf(client,login,path):
    login();assert client.post(path,data={}).status_code==400


def test_revocation_during_comparison_is_rechecked_atomically(app,inventory,verification_case,monkeypatch):
    from sqlalchemy import update
    with app.app_context():
        point,challenge=begin(app,inventory,verification_case)
        def compare(*args):
            db.session.execute(update(VerificationEnrollment).where(VerificationEnrollment.id==verification_case['enrollment']).values(revoked_at=utcnow()).execution_options(synchronize_session=False))
            return 'approved'
        monkeypatch.setattr(service,'synthetic_compare',compare)
        result=service.finish(challenge,point,inventory['admin'],'match');db.session.commit()
        assert result.outcome=='invalid'
        assert db.session.get(AccessEvent,result.access_event_id).decision=='denied'
        assert db.session.get(AccessCredential,verification_case['credential']).used_at is None


def test_policy_change_erases_previous_reference_immediately(app,client,login,verification_case):
    login()
    fields={key:'Registro do teste artificial' for key in ['purpose','controller','legal_review','necessity_review','risk_review','workplace_review','alternative']}
    fields.update(enabled='y',confirm='y',retention_days='1',threshold='.95')
    assert post(client,'/verification/policy',fields).status_code==302
    with app.app_context():
        row=db.session.get(VerificationEnrollment,verification_case['enrollment'])
        assert row.ciphertext is None and row.authorization_reference=='' and row.revoked_at
