from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import numpy as np
import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from sentinela.extensions import db
from sentinela.models import Alert, AlertActivity, AnalysisJob, AnalysisPolicy, Camera, SecurityEvent, User, utcnow
from sentinela.services import analysis, gateway, vision
from sentinela.services.events import emit_event
from sentinela.services.schedules import in_schedule
from test_inventory import inventory, post


@pytest.fixture
def policy(app, inventory):
    with app.app_context():
        row=AnalysisPolicy(organization_id=inventory['organization'],camera_id=inventory['cameras'][0],enabled=True)
        db.session.add(row);db.session.commit()
        return row.id


def test_actual_synthetic_video_produces_labeled_event_and_alert(app, inventory, policy):
    with app.app_context():
        for index in range(2):
            job=AnalysisJob(organization_id=inventory['organization'],camera_id=inventory['cameras'][0],requested_by=inventory['admin'])
            db.session.add(job);db.session.commit()
            assert analysis.run_job(job.id)
            db.session.refresh(job)
            assert job.status=='completed'
            assert job.event_count==(1 if index==0 else 0)
        events=db.session.scalars(select(SecurityEvent)).all()
        assert len(events)==1 and events[0].event_type=='motion' and events[0].source=='synthetic'
        assert db.session.scalar(select(func.count()).select_from(Alert))==1


def test_vision_static_obstruction_roi_and_insufficient_frames():
    policy=SimpleNamespace(roi_x=0,roi_y=0,roi_w=1,roi_h=1,motion_ratio=.03,motion_enabled=True,obstruction_enabled=True)
    uniform=np.full((180,320,3),255,dtype=np.uint8)
    assert vision.classify_frames([uniform]*4,policy)==['obstruction']
    rng=np.random.default_rng(3)
    static=rng.integers(0,255,(180,320,3),dtype=np.uint8)
    assert vision.classify_frames([static]*4,policy)==[]
    frames=[]
    for x in (160,190,220,250):
        frame=static.copy();frame[20:120,x:x+40]=255;frames.append(frame)
    policy.roi_w=.4
    assert vision.classify_frames(frames,policy)==[]
    with pytest.raises(vision.AnalysisFailure,match='insufficient_frames'):
        vision.classify_frames([static],policy)


def test_rolling_dedup_window_and_source_separation(app, inventory):
    with app.app_context():
        now=utcnow()
        args=dict(organization_id=inventory['organization'],site_id=inventory['sites'][0],event_type='motion',camera_id=inventory['cameras'][0],source='synthetic',cooldown=60)
        assert emit_event(**args,now=now)
        assert emit_event(**args,now=now+timedelta(seconds=59)) is None
        assert emit_event(**args,now=now+timedelta(seconds=60))
        db.session.commit()
        assert db.session.scalar(select(func.count()).select_from(Alert))==2


@pytest.mark.parametrize('condition,expected',[('disabled','disabled_or_revoked'),('inactive_site','disabled_or_revoked'),('inactive_actor','disabled_or_revoked'),('outside','outside_schedule')])
def test_jobs_honor_current_authorization_and_schedule(app, inventory, policy, monkeypatch, condition, expected):
    from sentinela.models import Site
    with app.app_context():
        row=db.session.get(AnalysisPolicy,policy)
        if condition=='disabled':row.enabled=False
        if condition=='inactive_site':db.session.get(Site,inventory['sites'][0]).status='inactive'
        if condition=='inactive_actor':db.session.get(User,inventory['admin']).active=False
        if condition=='outside':monkeypatch.setattr(analysis,'in_schedule',lambda *args:False)
        job=AnalysisJob(organization_id=inventory['organization'],camera_id=inventory['cameras'][0],requested_by=inventory['admin'])
        db.session.add(job);db.session.commit()
        assert analysis.run_job(job.id)
        assert job.status=='skipped' and job.reason_code==expected
        assert db.session.scalar(select(func.count()).select_from(SecurityEvent))==0


def test_worker_claims_once_and_processes_queue(app, inventory, policy):
    with app.app_context():
        job=AnalysisJob(organization_id=inventory['organization'],camera_id=inventory['cameras'][0],requested_by=inventory['admin'])
        db.session.add(job);db.session.commit();job_id=job.id
    result=app.test_cli_runner().invoke(args=['process-analysis','--limit','1'])
    assert result.exit_code==0,result.output
    assert 'processadas: 1' in result.output
    with app.app_context():
        assert not analysis.run_job(job_id)
        assert db.session.get(AnalysisJob,job_id).status=='completed'


def test_processing_failure_is_explicit_and_minimized(app, inventory, policy, monkeypatch):
    def fail(*args):raise RuntimeError('sensitive-internal-url')
    monkeypatch.setattr(analysis,'analyze_camera',fail)
    with app.app_context():
        job=AnalysisJob(organization_id=inventory['organization'],camera_id=inventory['cameras'][0],requested_by=inventory['admin'])
        db.session.add(job);db.session.commit();analysis.run_job(job.id)
        assert job.status=='failed' and job.reason_code=='internal_analysis_error'
        event=db.session.scalar(select(SecurityEvent))
        assert event.event_type=='processing_failure'
        assert 'sensitive' not in event.reason_code


def test_policy_validation_and_analysis_routes(client, login, inventory):
    login()
    path=f"/events/cameras/{inventory['cameras'][0]}"
    fields=dict(enabled='y',motion_enabled='y',obstruction_enabled='y',motion_ratio='.03',roi_x='0',roi_y='0',roi_w='1',roi_h='1',cooldown_seconds='60',start_time='00:00',end_time='00:00',weekdays='0,1,2,3,4,5,6',authorized='y')
    assert post(client,path+'/policy',{**fields,'roi_x':'.9','roi_w':'.5'}).status_code==422
    assert post(client,path+'/policy',{**fields,'motion_ratio':'nan'}).status_code==422
    assert post(client,path+'/policy',{**fields,'weekdays':'0,0'}).status_code==422
    assert post(client,path+'/policy',fields).status_code==302
    assert post(client,path+'/analyze',{'confirm':'y','mode':'now'}).status_code==302
    response=client.get('/events')
    assert 'Movimento em área autorizada' in response.text
    assert 'Análise de vídeo sintético' in response.text
    assert client.get('/alerts/summary').json['pending']==1


def make_alert(app, inventory, site_index=0):
    with app.app_context():
        event=emit_event(organization_id=inventory['organization'] if site_index<2 else inventory['other_org'],site_id=inventory['sites'][site_index],event_type='processing_failure',source='synthetic')
        db.session.commit()
        return db.session.scalar(select(Alert.id).where(Alert.event_id==event.id))


def test_alert_lifecycle_history_and_validation(app,client,login,inventory):
    alert_id=make_alert(app,inventory)
    login();path=f'/alerts/{alert_id}'
    assert post(client,path,{'status':'resolved','assigned_to':inventory['admin'],'note':'done'}).status_code==422
    assert post(client,path,{'status':'acknowledged','assigned_to':inventory['admin'],'note':'Assumida'}).status_code==302
    assert post(client,path,{'status':'in_review','assigned_to':inventory['admin'],'note':'Em revisão'}).status_code==302
    assert post(client,path,{'status':'resolved','assigned_to':inventory['admin'],'note':''}).status_code==422
    assert post(client,path,{'status':'resolved','assigned_to':inventory['admin'],'note':'Falha técnica revisada'}).status_code==302
    assert client.get('/alerts/summary').json['pending']==0
    with app.app_context():
        alert=db.session.get(Alert,alert_id)
        assert alert.acknowledged_at and alert.resolved_at and alert.version==3
        assert len(db.session.scalars(select(AlertActivity).where(AlertActivity.alert_id==alert_id)).all())==3
    assert post(client,path,{'status':'new','assigned_to':0,'note':'reopen'}).status_code==422


def test_alert_discard_requires_reason(client,login,app,inventory):
    alert_id=make_alert(app,inventory);login()
    assert post(client,f'/alerts/{alert_id}',{'status':'discarded','assigned_to':0,'note':''}).status_code==422
    assert post(client,f'/alerts/{alert_id}',{'status':'discarded','assigned_to':0,'note':'Teste descartado com justificativa'}).status_code==302


@pytest.mark.parametrize('email,index,status',[('admin@example.test',2,404),('operator@example.test',1,404),('platform@example.test',0,403),('physical@example.test',0,403)])
def test_event_alert_and_analysis_scopes(client,login,app,inventory,email,index,status):
    alert_id=make_alert(app,inventory,index);login(email)
    assert client.get(f'/alerts/{alert_id}').status_code==status
    camera=inventory['cameras'][index]
    if email=='admin@example.test':
        assert client.get(f'/events/cameras/{camera}/policy').status_code==404
    else:
        assert client.get(f'/events/cameras/{camera}/policy').status_code==403
    if email=='operator@example.test':
        assert client.get('/alerts/summary').json['pending']==0


def test_youtube_observation_is_manual_and_can_create_alert(app,client,login,inventory):
    login()
    fields={'site_id':inventory['sites'][0],'result':'youtube_playback_error','confirm':'y'}
    assert post(client,'/events/youtube-observation',fields).status_code==302
    assert post(client,'/events/youtube-observation',fields).status_code==302
    with app.app_context():
        events=db.session.scalars(select(SecurityEvent)).all()
        assert len(events)==1 and events[0].source=='youtube_client'
        assert events[0].event_type=='youtube_playback_error'
    assert client.get('/alerts/summary').json['pending']==1
    assert post(client,'/events/youtube-observation',{**fields,'site_id':inventory['sites'][2]}).status_code==422


def test_overnight_schedules_use_previous_day():
    # Sexta 23h UTC / sábado 03h UTC pertencem à janela da sexta.
    assert in_schedule(datetime(2026,10,16,23,tzinfo=timezone.utc),'UTC','22:00','06:00','4')
    assert in_schedule(datetime(2026,10,17,3,tzinfo=timezone.utc),'UTC','22:00','06:00','4')
    assert not in_schedule(datetime(2026,10,17,8,tzinfo=timezone.utc),'UTC','22:00','06:00','4')


def test_jobs_unique_active_and_recovery(app,inventory,policy):
    with app.app_context():
        job=AnalysisJob(organization_id=inventory['organization'],camera_id=inventory['cameras'][0],requested_by=inventory['admin'],status='running',started_at=utcnow()-timedelta(minutes=10))
        db.session.add(job);db.session.commit();job_id=job.id
        db.session.add(AnalysisJob(organization_id=inventory['organization'],camera_id=inventory['cameras'][0],requested_by=inventory['admin']))
        with pytest.raises(IntegrityError):db.session.commit()
        db.session.rollback()
    result=app.test_cli_runner().invoke(args=['process-analysis','--recover-stale','--limit','1'])
    assert result.exit_code==0,result.output
    with app.app_context():assert db.session.get(AnalysisJob,job_id).status=='completed'


def test_gateway_sample_never_accepts_external_asset(app,inventory,monkeypatch):
    monkeypatch.setattr(gateway,'fetch',lambda *args:b'#EXTM3U\nhttps://evil.example/segment.ts\n')
    with app.app_context():
        camera=db.session.get(Camera,inventory['cameras'][0]);camera.gateway_path='authorized'
        with pytest.raises(vision.AnalysisFailure,match='unsafe_manifest'):vision.sample_gateway(camera)


def test_camera_delete_preserves_alert_history(app,client,login,inventory,policy):
    with app.app_context():
        event=emit_event(organization_id=inventory['organization'],site_id=inventory['sites'][0],camera_id=inventory['cameras'][0],event_type='motion',source='synthetic')
        db.session.commit();event_id=event.id
    login()
    assert post(client,f"/cameras/{inventory['cameras'][0]}/delete",{'identifier':'cam-0'}).status_code==302
    with app.app_context():
        assert db.session.get(SecurityEvent,event_id).camera_id is None
        assert db.session.scalar(select(Alert.id).where(Alert.event_id==event_id))


@pytest.mark.parametrize('path',['/events/youtube-observation','/access','/access/people/new','/access/points/new','/access/credentials/new','/access/permissions/new'])
def test_new_mutations_require_csrf(client,login,path):
    login();assert client.post(path,data={}).status_code==400


def test_real_sample_is_decoded_and_temporary_file_removed(app,inventory,policy,monkeypatch,tmp_path):
    from pathlib import Path
    camera_id=inventory['cameras'][0]
    media=Path(__file__).resolve().parents[1]/'sentinela'/'media'/'demo.mp4'
    monkeypatch.setattr(vision,'sample_gateway',lambda camera:media.read_bytes())
    monkeypatch.setattr(vision.tempfile,'tempdir',str(tmp_path))
    with app.app_context():
        camera=db.session.get(Camera,camera_id);camera.protocol='rtsp'
        assert vision.analyze_camera(camera,db.session.get(AnalysisPolicy,policy))==['motion']
        assert not list(tmp_path.iterdir())


def test_decoder_rejects_playlist_masquerading_as_media(app,inventory,policy,monkeypatch):
    monkeypatch.setattr(vision,'sample_gateway',lambda camera:b'#EXTM3U\nhttps://forbidden.example/stream\n')
    with app.app_context():
        camera=db.session.get(Camera,inventory['cameras'][0]);camera.protocol='rtsp'
        with pytest.raises(vision.AnalysisFailure,match='unsupported_container'):
            vision.analyze_camera(camera,db.session.get(AnalysisPolicy,policy))


def test_real_camera_checks_emit_offline_reconnected_and_integration_alerts(app,client,login,inventory,monkeypatch):
    login()
    camera_id=inventory['cameras'][0]
    with app.app_context():
        camera=db.session.get(Camera,camera_id);camera.protocol='rtsp';camera.gateway_path='test'
        db.session.commit()
    outcomes=iter([False,True,gateway.GatewayError('authentication_failed')])
    def probe(camera):
        result=next(outcomes)
        if isinstance(result,Exception):raise result
        return result
    monkeypatch.setattr(gateway,'probe',probe)
    for _ in range(3):
        with app.app_context():
            db.session.get(Camera,camera_id).last_checked_at=utcnow()-timedelta(seconds=11)
            db.session.commit()
        assert post(client,f'/cameras/{camera_id}/check',{}).status_code==302
    with app.app_context():
        events=db.session.scalars(select(SecurityEvent).order_by(SecurityEvent.id)).all()
        assert [e.event_type for e in events]==['camera_offline','camera_reconnected','integration_failure']
        assert all(e.source=='gateway' for e in events)
        assert db.session.scalar(select(func.count()).select_from(Alert))==3
