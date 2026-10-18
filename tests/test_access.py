from datetime import timedelta
import re

import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from sentinela.extensions import db
from sentinela.models import AccessCredential, AccessEvent, AccessPermission, AccessPoint, AccessSubject, Alert, Site, utcnow
from sentinela.services import access as service
from test_inventory import inventory, post


@pytest.fixture
def access_case(app,inventory):
    with app.app_context():
        subject=AccessSubject(organization_id=inventory['organization'],display_name='Participante de teste',external_reference='teste-1')
        other=AccessSubject(organization_id=inventory['other_org'],display_name='Outro cliente',external_reference='teste-1')
        points=[AccessPoint(organization_id=inventory['organization'],site_id=inventory['sites'][i],name=f'Ponto-{i}') for i in range(2)]
        foreign=AccessPoint(organization_id=inventory['other_org'],site_id=inventory['sites'][2],name='Ponto de outro cliente')
        db.session.add_all([subject,other,*points,foreign]);db.session.flush()
        permission=AccessPermission(organization_id=inventory['organization'],subject_id=subject.id,site_id=inventory['sites'][0])
        db.session.add(permission)
        credential,token=service.issue(subject,300)
        foreign_credential,foreign_token=service.issue(other,300)
        db.session.commit()
        return {'subject':subject.id,'other_subject':other.id,'point':points[0].id,'other_point':points[1].id,'foreign_point':foreign.id,
                'permission':permission.id,'credential':credential.id,'token':token,'foreign_token':foreign_token,'foreign_credential':foreign_credential.id}


def test_valid_single_use_and_replay(app,client,login,inventory,access_case):
    login()
    fields={'point_id':access_case['point'],'token':access_case['token'],'confirm':'y'}
    first=post(client,'/access',fields)
    assert first.status_code==200 and 'ACESSO SIMULADO PERMITIDO' in first.text
    second=post(client,'/access',fields)
    assert second.status_code==200 and 'ACESSO SIMULADO NEGADO' in second.text
    assert 'Credencial já utilizada' in second.text
    assert access_case['token'] not in first.text and access_case['token'] not in second.text
    with app.app_context():
        credential=db.session.get(AccessCredential,access_case['credential'])
        assert credential.used_at and credential.token_hash!=access_case['token']
        rows=db.session.scalars(select(AccessEvent).order_by(AccessEvent.id)).all()
        assert [r.decision for r in rows]==['allowed','denied']


@pytest.mark.parametrize('condition,reason',[('revoked','revoked'),('expired','expired'),('used','used'),('inactive','subject_inactive'),
                                           ('point','point_inactive'),('site','point_inactive'),('permission','no_permission'),('schedule','outside_schedule')])
def test_fail_closed_conditions(app,client,login,inventory,access_case,monkeypatch,condition,reason):
    with app.app_context():
        credential=db.session.get(AccessCredential,access_case['credential'])
        if condition=='revoked':credential.revoked_at=utcnow()
        if condition=='expired':credential.expires_at=utcnow()-timedelta(seconds=1)
        if condition=='used':credential.used_at=utcnow()
        if condition=='inactive':db.session.get(AccessSubject,access_case['subject']).active=False
        if condition=='point':db.session.get(AccessPoint,access_case['point']).enabled=False
        if condition=='site':db.session.get(Site,inventory['sites'][0]).status='inactive'
        if condition=='permission':db.session.delete(db.session.get(AccessPermission,access_case['permission']))
        db.session.commit()
    if condition=='schedule':monkeypatch.setattr(service,'in_schedule',lambda *args:False)
    login()
    response=post(client,'/access',{'point_id':access_case['point'],'token':access_case['token'],'confirm':'y'})
    assert response.status_code==200
    with app.app_context():
        event=db.session.scalar(select(AccessEvent))
        assert event.decision=='denied' and event.reason_code==reason


def test_unknown_and_cross_tenant_tokens_do_not_reveal_identity(app,client,login,inventory,access_case):
    login()
    for token in ['Participante de teste',access_case['foreign_token'],'invalid-random-code']:
        response=post(client,'/access',{'point_id':access_case['point'],'token':token,'confirm':'y'})
        assert response.status_code==200 and 'ACESSO SIMULADO NEGADO' in response.text
        assert 'Outro cliente' not in response.text
    with app.app_context():
        assert db.session.scalar(select(func.count()).select_from(Alert))==1
        assert all(row.subject_id is None for row in db.session.scalars(select(AccessEvent)))
        assert db.session.get(AccessCredential,access_case['foreign_credential']).used_at is None


def test_permission_failure_does_not_consume_token(app,client,login,inventory,access_case):
    login()
    assert post(client,'/access',{'point_id':access_case['other_point'],'token':access_case['token'],'confirm':'y'}).status_code==200
    with app.app_context():assert db.session.get(AccessCredential,access_case['credential']).used_at is None
    response=post(client,'/access',{'point_id':access_case['point'],'token':access_case['token'],'confirm':'y'})
    assert 'ACESSO SIMULADO PERMITIDO' in response.text


def test_operator_point_scope_and_people_privacy(client,login,inventory,access_case):
    login('operator@example.test')
    response=client.get('/access')
    assert 'Ponto-0' in response.text and 'Ponto-1' not in response.text
    assert 'Ponto de outro cliente' not in response.text
    assert client.get('/access/people').status_code==403
    assert client.get('/access/credentials/new').status_code==403
    assert post(client,'/access',{'point_id':access_case['other_point'],'token':access_case['token'],'confirm':'y'}).status_code==422
    assert post(client,'/access',{'point_id':access_case['point'],'token':access_case['token'],'confirm':'y'}).status_code==200


def test_foreign_subject_and_credential_hidden(client,login,inventory,access_case):
    login()
    assert client.get(f"/access/people/{access_case['other_subject']}/edit").status_code==404
    assert client.get(f"/access/credentials/{access_case['foreign_credential']}/revoke").status_code==404
    assert post(client,f"/access/credentials/{access_case['foreign_credential']}/revoke",{'confirm':'y'}).status_code==404
    assert post(client,'/access/credentials/new',{'subject_id':access_case['other_subject'],'ttl':'300'}).status_code==422


def test_create_people_permissions_points_and_issue_ui(app,client,login,inventory):
    login()
    assert post(client,'/access/people/new',{'display_name':'Teste UI','external_reference':'ui-1','active':'y'}).status_code==302
    with app.app_context():subject_id=db.session.scalar(select(AccessSubject.id))
    assert post(client,'/access/points/new',{'name':'Portaria de teste','site_id':inventory['sites'][0],'enabled':'y'}).status_code==302
    assert post(client,'/access/permissions/new',{'subject_id':subject_id,'site_id':inventory['sites'][0],'start_time':'00:00','end_time':'00:00','weekdays':'0,1,2,3,4,5,6'}).status_code==302
    response=post(client,'/access/credentials/new',{'subject_id':subject_id,'ttl':'300'})
    assert response.status_code==200 and response.headers['Cache-Control']=='no-store'
    token=re.search(r'id="issued-token"[^>]*value="([^"]+)"',response.text).group(1)
    assert len(token)>=40
    assert token not in client.get('/access/people').text
    assert token not in client.get('/access').text
    with app.app_context():
        assert db.session.scalar(select(AccessCredential)).token_hash!=token


def test_revoke_credential_and_permission_routes(app,client,login,inventory,access_case):
    login()
    assert post(client,f"/access/credentials/{access_case['credential']}/revoke",{'confirm':'y'}).status_code==302
    assert post(client,f"/access/permissions/{access_case['permission']}/revoke",{'confirm':'y'}).status_code==302
    with app.app_context():
        assert db.session.get(AccessCredential,access_case['credential']).revoked_at
        assert db.session.get(AccessPermission,access_case['permission']) is None


def test_invalid_schedule_is_logged_as_denial(app,client,login,inventory,access_case,monkeypatch):
    def fail(*args):raise ValueError('unavailable schedule')
    monkeypatch.setattr(service,'in_schedule',fail)
    login()
    response=post(client,'/access',{'point_id':access_case['point'],'token':access_case['token'],'confirm':'y'})
    assert response.status_code==200
    with app.app_context():
        event=db.session.scalar(select(AccessEvent))
        assert event.reason_code=='policy_unavailable' and event.decision=='denied'
        assert db.session.get(AccessCredential,access_case['credential']).used_at is None


def test_cross_tenant_relations_rejected_by_database(app,inventory,access_case):
    with app.app_context():
        db.session.add(AccessPermission(organization_id=inventory['organization'],subject_id=access_case['subject'],site_id=inventory['sites'][2]))
        with pytest.raises(IntegrityError):db.session.commit()
        db.session.rollback()
        db.session.add(AccessCredential(organization_id=inventory['organization'],subject_id=access_case['other_subject'],token_hash='a'*64,expires_at=utcnow()))
        with pytest.raises(IntegrityError):db.session.commit()
        db.session.rollback()


def test_point_deactivation_and_subject_edit(client,login,inventory,access_case):
    login()
    assert post(client,f"/access/points/{access_case['point']}/state",{'confirm':'y'}).status_code==302
    assert post(client,f"/access/people/{access_case['subject']}/edit",{'display_name':'Desativado','external_reference':'teste-1'}).status_code==302
    assert 'Inativa' in client.get('/access/people').text


def test_access_confirmation_is_required(client,login,inventory,access_case):
    login()
    response=post(client,'/access',{'point_id':access_case['point'],'token':access_case['token']})
    assert response.status_code==422


def test_concurrent_attempts_consume_credential_only_once(tmp_path):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier
    from sentinela import create_app
    from sentinela.models import Organization, Site, User
    from conftest import TEST_HASH
    app = create_app({'TESTING': True, 'SQLALCHEMY_DATABASE_URI': f"sqlite:///{tmp_path / 'concurrent.db'}", 'RATELIMIT_ENABLED': False})
    with app.app_context():
        db.create_all()
        org=Organization(name='Concurrency');db.session.add(org);db.session.flush()
        site=Site(name='Site',organization_id=org.id)
        actor=User(email='concurrent@example.test',role='organization_admin',organization_id=org.id,password_hash=TEST_HASH)
        subject=AccessSubject(display_name='Test',external_reference='test',organization_id=org.id)
        db.session.add_all([site,actor,subject]);db.session.flush()
        point=AccessPoint(name='Point',organization_id=org.id,site_id=site.id)
        permission=AccessPermission(organization_id=org.id,subject_id=subject.id,site_id=site.id)
        db.session.add_all([point,permission]);db.session.flush()
        _,token=service.issue(subject,300);db.session.commit()
        point_id,actor_id=point.id,actor.id
    barrier=Barrier(2)
    def attempt(_):
        with app.app_context():
            point=db.session.get(AccessPoint,point_id)
            barrier.wait(timeout=5)
            result=service.decide(point=point,token=token,actor_id=actor_id)
            decision=result.decision;db.session.commit()
            return decision
    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(attempt,range(2)))==['allowed','denied']
    with app.app_context():
        assert db.session.scalar(select(func.count()).select_from(AccessEvent))==2
        db.session.remove();db.engine.dispose()
