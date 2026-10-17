from flask import Blueprint, render_template

from ..core.permissions import console_required

bp = Blueprint("dashboard", __name__)


@bp.get("/")
@console_required
def index():
    # Fixtures de apresentação. Não representam recursos ou eventos reais do banco.
    metrics = [
        {"label": "Câmeras cadastradas", "value": "24", "detail": "Em 3 unidades de exemplo", "icon": "camera", "tone": "blue"},
        {"label": "Câmeras online", "value": "21", "detail": "87,5% de disponibilidade simulada", "icon": "video", "tone": "green"},
        {"label": "Câmeras offline", "value": "03", "detail": "Indisponibilidade simulada", "icon": "video-off", "tone": "red"},
        {"label": "Alertas pendentes", "value": "05", "detail": "Exemplos de alertas técnicos", "icon": "bell", "tone": "amber"},
        {"label": "Eventos do dia", "value": "148", "detail": "Dados fixos para apresentação", "icon": "activity", "tone": "cyan"},
        {"label": "Unidades monitoradas", "value": "03", "detail": "Nenhuma conexão real ativa", "icon": "building-2", "tone": "violet"},
    ]
    events = [
        {"time": "14:42", "title": "Câmera indisponível", "detail": "CAM-018 · Acesso lateral", "site": "Unidade Centro", "status": "Pendente", "tone": "red", "icon": "video-off"},
        {"time": "14:36", "title": "Conexão restabelecida", "detail": "CAM-007 · Estacionamento", "site": "Unidade Norte", "status": "Exemplo resolvido", "tone": "green", "icon": "wifi"},
        {"time": "14:28", "title": "Movimento em área autorizada", "detail": "CAM-012 · Área de carga", "site": "Unidade Sul", "status": "Exemplo informativo", "tone": "blue", "icon": "activity"},
        {"time": "14:15", "title": "Falha de leitura do vídeo", "detail": "CAM-021 · Entrada de serviço", "site": "Unidade Centro", "status": "Pendente", "tone": "amber", "icon": "triangle-alert"},
    ]
    return render_template("dashboard.html", title="Dashboard", active_slug=None, metrics=metrics, events=events)
