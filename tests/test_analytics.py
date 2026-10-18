from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select

from sentinela.extensions import db
from sentinela.models import AccessEvent, AccessPoint, Alert, Camera, CameraHealthEvent, SecurityEvent, utcnow
from sentinela.services.analytics import Filters, build
from sentinela.services.events import emit_event
from test_inventory import inventory


@pytest.fixture
def analytics_data(app,inventory):
    t=datetime(2026,10,15,12,tzinfo=timezone.utc)
    with app.app_context():
        cameras=[db.session.get(Camera,i) for i in inventory['cameras']]
        for camera in cameras:camera.created_at=t-timedelta(days=10)
        cameras[0].protocol='rtsp';cameras[0].gateway_path='observed';cameras[0].connection_status='online';cameras[0].last_checked_at=utcnow();cameras[0].last_seen_at=utcnow()
        for offset,state in [(-30,'online'),(30,'offline'),(60,'offline'),(120,'online')]:
            db.session.add(CameraHealthEvent(organization_id=inventory['organization'],camera_id=cameras[0].id,event_type=state,reason_code='test',occurred_at=t+timedelta(seconds=offset)))
        for index,site,org,source,kind in [
            (0,0,'organization','gateway','camera_offline'),(1,0,'organization','synthetic','motion'),
            (2,0,'organization','youtube_client','youtube_playback_observed'),(3,1,'organization','synthetic','motion'),
            (4,2,'other_org','gateway','processing_failure')]:
            event=emit_event(organization_id=inventory[org],site_id=inventory['sites'][site],event_type=kind,source=source,
                             severity='info' if index==2 else 'attention',now=t+timedelta(minutes=index))
            db.session.flush()
            alert=db.session.scalar(select(Alert).where(Alert.event_id==event.id))
            if alert:
                alert.created_at=t+timedelta(minutes=index)
                if index==0:
                    alert.status='resolved';alert.acknowledged_at=t+timedelta(seconds=20);alert.resolved_at=t+timedelta(seconds=200)
        point=AccessPoint(organization_id=inventory['organization'],site_id=inventory['sites'][0],name='Entrada analítica')
        db.session.add(point);db.session.flush()
        for decision in ['allowed','allowed','denied']:
            db.session.add(AccessEvent(organization_id=inventory['organization'],site_id=inventory['sites'][0],access_point_id=point.id,
                                      actor_id=inventory['admin'],decision=decision,reason_code='allowed' if decision=='allowed' else 'invalid',occurred_at=t))
        db.session.commit()
    return {'t':t,'filters':Filters(t.replace(hour=0),t.replace(hour=0)+timedelta(days=1)),**inventory}


def test_backend_metrics_observed_availability_and_alert_times(app,client,login,analytics_data):
    login()
    with client:
        client.get('/')
        data=build(analytics_data['filters'])
        assert data['camera_totals']['total']==2
        assert data['camera_totals']['online']==1 and data['camera_totals']['demo']==1
        real=next(c for c in data['cameras'] if c['source']=='gateway')
        assert real['online_seconds']==150 and real['offline_seconds']==90
        assert real['availability_pct']==62.5 and real['mean_offline_seconds']==90
        assert real['coverage_pct']==.28 and real['failure_checks']==2
        assert data['event_total']==4 and data['alerts']['received']==3
        assert data['alerts']['pending']==2 and data['alerts']['resolved']==1
        assert data['alerts']['ack_seconds']==20 and data['alerts']['resolution_seconds']==200
        assert data['access']=={'total':3,'allowed':2,'denied':1,'technical':0}
        assert data['timeline'][0]['events']==4 and data['monthly']=={'2026-10':4}


def test_scope_and_source_filters_apply_to_all_metrics(client,login,analytics_data):
    login('operator@example.test')
    f=analytics_data['filters']
    with client:
        client.get('/')
        data=build(f)
        assert len(data['site_ids'])==1 and data['event_total']==3 and data['alerts']['received']==2
        assert data['camera_totals']['total']==1
        gateway=build(Filters(f.start,f.end,source='gateway'))
        assert gateway['event_total']==1 and gateway['alerts']['received']==1 and gateway['access']['total']==0
        synthetic=build(Filters(f.start,f.end,source='synthetic'))
        assert synthetic['event_total']==1 and synthetic['camera_totals']['total']==0
        access=build(Filters(f.start,f.end,source='access_simulation'))
        assert access['access']['total']==3 and access['event_total']==0


def test_stale_camera_state_is_unknown_and_gaps_are_not_assumed_online(app,client,login,analytics_data):
    with app.app_context():
        camera=db.session.get(Camera,analytics_data['cameras'][0]);camera.last_checked_at=utcnow()-timedelta(minutes=5);db.session.commit()
    login()
    with client:
        client.get('/')
        data=build(analytics_data['filters'])
        assert data['camera_totals']['unknown']==1 and data['camera_totals'].get('online',0)==0
        assert data['cameras'][0]['observed_seconds']==240


@pytest.mark.parametrize('query',['start=bad','site_id=99999','source=invalid','start=2026-01-01&end=2026-10-15','start=2026-10-16&end=2026-10-15','end=2099-01-01'])
def test_dashboard_rejects_invalid_or_foreign_filters(client,login,query):
    login();assert client.get('/?'+query).status_code==422


def test_dashboard_has_actual_data_and_no_fixtures(client,login,analytics_data):
    login();response=client.get('/?start=2026-10-15&end=2026-10-15')
    assert response.status_code==200
    assert '62.5%' in response.text and 'DADOS DE EXEMPLO' not in response.text
    assert 'Dados fixos' not in response.text and 'Centro' in response.text
    assert 'Outra organização' not in response.text and 'Unidade de outro cliente' not in response.text
    assert 'data-charts=' in response.text
