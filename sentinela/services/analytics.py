"""Indicadores compartilhados por dashboard e relatórios, sempre no escopo atual."""
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, time, timedelta, timezone
from statistics import mean

from flask import current_app
from flask_login import current_user
from sqlalchemy import func, select

from ..core.permissions import visible_cameras, visible_sites
from ..extensions import db
from ..models import AccessEvent, Alert, Camera, CameraHealthEvent, SecurityEvent, Site, utcnow
from .events import EVENT_LABELS, SOURCE_LABELS
from .schedules import as_utc

MAX_ROWS = 100000


class CapacityExceeded(Exception):
    pass


@dataclass(frozen=True)
class Filters:
    start: datetime
    end: datetime
    site_id: int = 0
    source: str = 'all'

    @classmethod
    def from_form(cls, form):
        return cls(datetime.combine(form.start.data,time.min,tzinfo=timezone.utc),
                   datetime.combine(form.end.data+timedelta(days=1),time.min,tzinfo=timezone.utc),form.site_id.data,form.source.data)


def sites_for(filters):
    query=visible_sites().order_by(Site.name)
    if filters.site_id:query=query.where(Site.id==filters.site_id)
    return db.session.scalars(query).all()


def bounded(rows):
    if len(rows)>MAX_ROWS:raise CapacityExceeded('Há registros demais para este período. Selecione menos dias ou uma unidade.')
    return rows


def event_query(filters, site_ids):
    query=select(SecurityEvent).where(SecurityEvent.organization_id==current_user.organization_id,
           SecurityEvent.site_id.in_(site_ids),SecurityEvent.occurred_at>=filters.start,SecurityEvent.occurred_at<filters.end)
    if filters.source!='all':query=query.where(SecurityEvent.source==filters.source)
    return query


def access_query(filters, site_ids):
    return select(AccessEvent).where(AccessEvent.organization_id==current_user.organization_id,
         AccessEvent.site_id.in_(site_ids),AccessEvent.occurred_at>=filters.start,AccessEvent.occurred_at<filters.end,
         filters.source in {'all','access_simulation'})


def camera_statistics(filters, site_ids, now):
    query=visible_cameras().where(Camera.site_id.in_(site_ids)).order_by(Camera.name)
    if filters.source=='gateway':query=query.where(Camera.protocol!='demo')
    elif filters.source=='synthetic':query=query.where(Camera.protocol=='demo')
    elif filters.source!='all':query=query.where(False)
    cameras=bounded(db.session.scalars(query.limit(MAX_ROWS+1)).all())
    real_ids=[c.id for c in cameras if c.protocol!='demo']
    ttl=current_app.config['CAMERA_STATUS_TTL']
    history=select(CameraHealthEvent.camera_id,CameraHealthEvent.event_type,CameraHealthEvent.occurred_at,CameraHealthEvent.id).where(
            CameraHealthEvent.organization_id==current_user.organization_id,CameraHealthEvent.camera_id.in_(real_ids),CameraHealthEvent.occurred_at<filters.end)
    previous=history.where(CameraHealthEvent.occurred_at<filters.start).add_columns(
        func.row_number().over(partition_by=CameraHealthEvent.camera_id,order_by=(CameraHealthEvent.occurred_at.desc(),CameraHealthEvent.id.desc())).label('rank')).subquery()
    rows=db.session.execute(select(previous.c.camera_id,previous.c.event_type,previous.c.occurred_at,previous.c.id).where(previous.c.rank==1)).all()
    rows+=bounded(db.session.execute(history.where(CameraHealthEvent.occurred_at>=filters.start).limit(MAX_ROWS+1)).all())
    by_camera=defaultdict(list)
    for camera_id,state,at,identifier in rows:by_camera[camera_id].append((as_utc(at),identifier,state))
    result=[];all_episodes=[]
    for camera in cameras:
        state='disabled' if not camera.enabled or camera.site.status!='active' else 'demo' if camera.protocol=='demo' else 'unknown'
        if state=='unknown' and camera.last_checked_at and 0<=(as_utc(now)-as_utc(camera.last_checked_at)).total_seconds()<=ttl:
            state=camera.connection_status if camera.connection_status in {'online','offline'} else 'unknown'
        observations=sorted(by_camera[camera.id])
        online=offline=0.;episodes=[];episode_start=episode_end=None
        failures=sum(s in {'offline','unknown'} and filters.start<=at<filters.end for at,_,s in observations)
        for i,(at,_,observed) in enumerate(observations):
            begin=max(at,filters.start)
            end=min(at+timedelta(seconds=ttl),filters.end,as_utc(now),observations[i+1][0] if i+1<len(observations) else filters.end)
            seconds=max(0.,(end-begin).total_seconds())
            if observed=='online':online+=seconds
            if observed=='offline' and seconds:
                offline+=seconds
                if episode_end is not None and begin<=episode_end:episode_end=max(episode_end,end)
                else:
                    if episode_start is not None:episodes.append((episode_end-episode_start).total_seconds())
                    episode_start,episode_end=begin,end
        if episode_start is not None:episodes.append((episode_end-episode_start).total_seconds())
        all_episodes+=episodes
        observed_seconds=online+offline
        denominator=max(0.,(min(filters.end,as_utc(now))-max(filters.start,as_utc(camera.created_at))).total_seconds())
        result.append({'id':camera.id,'name':camera.name,'site':camera.site.name,'site_id':camera.site_id,'source':'synthetic' if camera.protocol=='demo' else 'gateway',
            'state':state,'last_seen':as_utc(camera.last_seen_at).isoformat() if camera.last_seen_at else None,
            'online_seconds':round(online,2),'offline_seconds':round(offline,2),'observed_seconds':round(observed_seconds,2),
            'coverage_pct':round(100*observed_seconds/denominator,2) if denominator else 0,
            'availability_pct':round(100*online/observed_seconds,2) if observed_seconds else None,
            'mean_offline_seconds':round(mean(episodes),2) if episodes else None,'failure_checks':failures})
    online=sum(c['online_seconds'] for c in result);offline=sum(c['offline_seconds'] for c in result)
    return result,{'total':len(result),**dict(Counter(c['state'] for c in result)),
           'availability_pct':round(100*online/(online+offline),2) if online+offline else None,
           'mean_offline_seconds':round(mean(all_episodes),2) if all_episodes else None,'failure_checks':sum(c['failure_checks'] for c in result)}


def build(filters, now=None):
    now=as_utc(now or utcnow())
    sites=sites_for(filters);site_ids=[s.id for s in sites];site_names={s.id:s.name for s in sites}
    cameras,camera_totals=camera_statistics(filters,site_ids,now)
    events=event_query(filters,site_ids).subquery()
    grouped=db.session.execute(select(events.c.site_id,events.c.event_type,events.c.source,func.count()).group_by(
                              events.c.site_id,events.c.event_type,events.c.source)).all()
    event_rows=[{'site':site_names[site_id],'kind':kind,'type':EVENT_LABELS.get(kind,kind),'source':SOURCE_LABELS[source],'count':count}
                for site_id,kind,source,count in grouped]
    sources=Counter();types=Counter();site_counts=Counter()
    for site_id,kind,source,count in grouped:
        sources[source]+=count;types[EVENT_LABELS.get(kind,kind)]+=count;site_counts[site_names[site_id]]+=count
    daily=dict(db.session.execute(select(func.date(events.c.occurred_at),func.count()).group_by(func.date(events.c.occurred_at))).all())
    alert_query=select(Alert,SecurityEvent.event_type,SecurityEvent.source).join(SecurityEvent,Alert.event_id==SecurityEvent.id).where(
         Alert.organization_id==current_user.organization_id,Alert.site_id.in_(site_ids),Alert.created_at>=filters.start,Alert.created_at<filters.end)
    if filters.source!='all':alert_query=alert_query.where(SecurityEvent.source==filters.source)
    alerts=bounded(db.session.execute(alert_query.order_by(Alert.id).limit(MAX_ROWS+1)).all())
    acknowledgement=[];resolution=[];alert_types=Counter();alert_rows=[]
    pending=resolved=discarded=0
    for alert,kind,source in alerts:
        pending+=alert.status in {'new','acknowledged','in_review'};resolved+=alert.status=='resolved';discarded+=alert.status=='discarded'
        ack=max(0,(as_utc(alert.acknowledged_at)-as_utc(alert.created_at)).total_seconds()) if alert.acknowledged_at else None
        duration=max(0,(as_utc(alert.resolved_at)-as_utc(alert.created_at)).total_seconds()) if alert.resolved_at and alert.status=='resolved' else None
        if ack is not None:acknowledgement.append(ack)
        if duration is not None:resolution.append(duration)
        alert_types[EVENT_LABELS.get(kind,kind)]+=1
        alert_rows.append({'id':alert.id,'site':site_names[alert.site_id],'type':EVENT_LABELS.get(kind,kind),'source':SOURCE_LABELS[source],
                           'status':alert.status,'created_at':as_utc(alert.created_at).isoformat(),'ack_seconds':ack,'resolution_seconds':duration})
    access=access_query(filters,site_ids).subquery()
    access_groups=db.session.execute(select(access.c.site_id,access.c.access_point_id,access.c.decision,access.c.reason_code,access.c.method,func.count()).group_by(
         access.c.site_id,access.c.access_point_id,access.c.decision,access.c.reason_code,access.c.method)).all()
    from .access import REASONS
    access_rows=[{'site':site_names[site_id],'point_id':point_id,'decision':decision,'reason':REASONS.get(reason,reason),'reason_code':reason,'method':method,'count':count}
                 for site_id,point_id,decision,reason,method,count in access_groups]
    allowed=sum(r['count'] for r in access_rows if r['decision']=='allowed')
    denied=sum(r['count'] for r in access_rows if r['decision']=='denied')
    technical=sum(count for _,_,_,reason,_,count in access_groups if reason in {'policy_unavailable','verification_unavailable','verification_retry','state_changed'})
    access_daily=dict(db.session.execute(select(func.date(access.c.occurred_at),func.count()).group_by(func.date(access.c.occurred_at))).all())
    timeline=[]
    day=filters.start.date()
    while day<filters.end.date():
        key=day.isoformat();timeline.append({'day':key,'events':daily.get(key,daily.get(day,0)),'access':access_daily.get(key,access_daily.get(day,0))});day+=timedelta(days=1)
    monthly=Counter()
    for row in timeline:monthly[row['day'][:7]]+=row['events']
    recent=db.session.scalars(event_query(filters,site_ids).order_by(SecurityEvent.id.desc()).limit(20)).all()
    return {'sites':sites,'site_ids':site_ids,'cameras':cameras,'camera_totals':camera_totals,'events':event_rows,
            'source_counts':dict(sources),'event_total':sum(sources.values()),'site_counts':dict(site_counts),'types':dict(types),
            'alert_rows':alert_rows,'alert_types':dict(alert_types),'alerts':{'received':len(alerts),'pending':pending,'resolved':resolved,'discarded':discarded,
            'ack_seconds':round(mean(acknowledgement),2) if acknowledgement else None,'resolution_seconds':round(mean(resolution),2) if resolution else None},
            'access_rows':access_rows,'access':{'total':allowed+denied,'allowed':allowed,'denied':denied,'technical':technical},
            'timeline':timeline,'monthly':dict(monthly),'recent':recent,'site_names':site_names}
