from sqlalchemy import select, update

from ..extensions import db
from ..models import AnalysisJob, AnalysisPolicy, Camera, Organization, Site, User, utcnow
from .events import emit_event
from .gateway import GatewayError
from .schedules import in_schedule
from .vision import AnalysisFailure, analyze_camera


def run_job(job_id):
    now = utcnow()
    claimed = db.session.execute(update(AnalysisJob).where(AnalysisJob.id == job_id, AnalysisJob.status == "pending")
                                 .values(status="running", started_at=now).returning(AnalysisJob.id)).scalar()
    db.session.commit()
    if not claimed:
        return False
    job = db.session.get(AnalysisJob, job_id)
    camera = db.session.get(Camera, job.camera_id)
    policy = db.session.scalar(select(AnalysisPolicy).where(AnalysisPolicy.camera_id == job.camera_id, AnalysisPolicy.organization_id == job.organization_id))
    actor = db.session.get(User, job.requested_by)
    site = db.session.get(Site, camera.site_id) if camera else None
    org = db.session.get(Organization, job.organization_id)
    allowed = (camera and camera.organization_id == job.organization_id and camera.enabled and site.status == "active" and
               org and org.status == "active" and actor and actor.active and actor.organization_id == job.organization_id and
               actor.role == "organization_admin" and policy and policy.enabled)
    if not allowed:
        job.status, job.reason_code = "skipped", "disabled_or_revoked"
    elif not in_schedule(now, site.timezone, policy.start_time, policy.end_time, policy.weekdays):
        job.status, job.reason_code = "skipped", "outside_schedule"
    else:
        source = "synthetic" if camera.protocol == "demo" else "gateway"
        try:
            result = analyze_camera(camera, policy)
            job.event_count = 0
            for kind in result:
                event = emit_event(organization_id=job.organization_id, site_id=site.id, camera_id=camera.id, event_type=kind,
                                   source=source, cooldown=policy.cooldown_seconds)
                job.event_count += int(event is not None)
            job.status, job.reason_code = "completed", "sample_analyzed"
        except (AnalysisFailure, GatewayError) as error:
            job.status, job.reason_code = "failed", str(error)[:48]
            emit_event(organization_id=job.organization_id, site_id=site.id, camera_id=camera.id, event_type="processing_failure",
                       source=source, reason_code=job.reason_code, cooldown=policy.cooldown_seconds)
        except Exception as error:
            # Erros inesperados também falham explicitamente, sem incluir URLs,
            # exceções de decodificador ou credenciais na interface.
            db.session.rollback()
            job = db.session.get(AnalysisJob, job_id)
            job.status, job.reason_code = "failed", "internal_analysis_error"
            from flask import current_app
            current_app.logger.error("Analysis job %s failed (%s)", job_id, type(error).__name__)
            emit_event(organization_id=job.organization_id, site_id=site.id, camera_id=camera.id, event_type="processing_failure",
                       source=source, reason_code=job.reason_code, cooldown=policy.cooldown_seconds)
    job.finished_at = utcnow()
    db.session.commit()
    return True
