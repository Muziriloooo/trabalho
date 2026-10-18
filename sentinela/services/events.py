import hashlib
from datetime import timedelta

from sqlalchemy import update
from sqlalchemy.exc import IntegrityError

from ..extensions import db
from ..models import Alert, EventGate, SecurityEvent, utcnow

EVENT_LABELS = {
    "motion": "Movimento em área autorizada",
    "obstruction": "Possível obstrução ou alteração da imagem",
    "camera_offline": "Fonte de câmera indisponível",
    "camera_reconnected": "Fonte de câmera reconectada",
    "processing_failure": "Falha na análise de vídeo",
    "integration_failure": "Falha de integração de câmera",
    "access_denied_repeated": "Tentativas repetidas de acesso negado (simulação)",
    "youtube_playback_observed": "Reprodução do YouTube confirmada pelo operador",
    "youtube_playback_error": "Erro do player YouTube informado pelo operador",
    "youtube_test_ended": "Teste do YouTube encerrado pelo operador",
}
SOURCE_LABELS = {"synthetic": "Análise de vídeo sintético", "gateway": "Fonte autorizada via gateway",
                 "youtube_client": "Observação manual do player YouTube", "access_simulation": "Simulação de acesso — sem hardware"}


def emit_event(*, organization_id, site_id, event_type, source, camera_id=None, severity="attention", reason_code="", cooldown=60, gate_suffix="", now=None):
    """Gate atômico: uma transação vence por intervalo, sem conteúdo de vídeo."""
    if event_type not in EVENT_LABELS or source not in SOURCE_LABELS:
        raise ValueError("Tipo ou origem de evento inválidos.")
    now = now or utcnow()
    gate_id = hashlib.sha256(f"{organization_id}:{site_id}:{camera_id}:{event_type}:{source}:{gate_suffix}".encode()).hexdigest()
    if not db.session.get(EventGate, gate_id):
        try:
            with db.session.begin_nested():
                db.session.add(EventGate(id=gate_id, next_allowed_at=now))
                db.session.flush()
        except IntegrityError:
            pass
    claimed = db.session.execute(update(EventGate).where(EventGate.id == gate_id, EventGate.next_allowed_at <= now)
                                 .values(next_allowed_at=now + timedelta(seconds=cooldown)).returning(EventGate.id)).scalar()
    if not claimed:
        return None
    event = SecurityEvent(organization_id=organization_id, site_id=site_id, camera_id=camera_id, event_type=event_type,
                          source=source, severity=severity, reason_code=reason_code[:64], occurred_at=now)
    db.session.add(event)
    db.session.flush()
    if severity != "info":
        db.session.add(Alert(organization_id=organization_id, site_id=site_id, event_id=event.id))
    return event
