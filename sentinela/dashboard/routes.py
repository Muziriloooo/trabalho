from flask import Blueprint, render_template, request

from ..core.permissions import console_required, visible_sites
from ..extensions import db
from ..models import Site
from ..reports.forms import FilterForm, SOURCES
from ..services import analytics
from ..services.events import EVENT_LABELS, SOURCE_LABELS

bp = Blueprint('dashboard',__name__)


@bp.get('/')
@console_required
def index():
    form=FilterForm(request.args if request.args else None,meta={'csrf':False})
    form.site_id.choices=[(0,'Todas no meu escopo')]+[(s.id,s.name) for s in db.session.scalars(visible_sites().order_by(Site.name)).all()]
    data=None
    if form.validate():
        try:data=analytics.build(analytics.Filters.from_form(form))
        except analytics.CapacityExceeded as error:form.end.errors=[str(error)]
    if data is None:
        return render_template('dashboard.html',title='Dashboard',active_slug=None,form=form,data=None,metrics=[],charts={}),422
    cameras=data['camera_totals'];alerts=data['alerts'];access=data['access']
    definitions=[('Câmeras cadastradas',cameras['total'],'No escopo e filtro de fonte','camera','blue'),
        ('Câmeras online',cameras.get('online',0),'Somente fonte real com verificação recente','video','green'),
        ('Câmeras offline',cameras.get('offline',0),'Somente fonte real com verificação recente','video-off','red'),
        ('Estado desconhecido',cameras.get('unknown',0),'Sem confirmação recente da fonte real','circle-help','amber'),
        ('Câmeras de demonstração',cameras.get('demo',0),'Fontes sintéticas ativas; não contam como online real','flask-conical','cyan'),
        ('Alertas pendentes',alerts['pending'],'Estado atual dos recebidos no período','bell','amber'),
        ('Eventos registrados',data['event_total'],'Origens separadas abaixo','activity','blue'),
        ('Alertas resolvidos',alerts['resolved'],'Recebidos no período selecionado','check','green'),
        ('Acessos simulados',access['total'],'Nenhum acionamento de hardware','scan-line','violet'),
        ('Permitidos / negados',f"{access['allowed']} / {access['denied']}",'Decisões agregadas, sem ranking pessoal','shield-check','cyan'),
        ('Falhas técnicas de acesso',access['technical'],'Validação ou infraestrutura indisponível','triangle-alert','red'),
        ('Unidades no escopo',len(data['sites']),'Permissões atuais aplicadas no servidor','building-2','violet')]
    metrics=[dict(label=label,value=value,detail=detail,icon=icon,tone=tone) for label,value,detail,icon,tone in definitions]
    charts={'activity':{'labels':[r['day'] for r in data['timeline']],'datasets':[
         {'label':'Eventos registrados','data':[r['events'] for r in data['timeline']]},
         {'label':'Tentativas de acesso simulado','data':[r['access'] for r in data['timeline']]}]},
        'sites':{'labels':list(data['site_counts']),'datasets':[{'label':'Eventos por unidade','data':list(data['site_counts'].values())}]},
        'availability':{'labels':[r['name'] for r in data['cameras'][:30]],'datasets':[{'label':'Disponibilidade observada (%)','data':[r['availability_pct'] for r in data['cameras'][:30]]}]},
        'types':{'labels':list(data['alert_types']),'datasets':[{'label':'Alertas por tipo','data':list(data['alert_types'].values())}]},
        'monthly':{'labels':list(data['monthly']),'datasets':[{'label':'Eventos nos meses do período','data':list(data['monthly'].values())}]}}
    return render_template('dashboard.html',title='Dashboard',active_slug=None,form=form,data=data,metrics=metrics,charts=charts,
                           labels=EVENT_LABELS,sources=SOURCE_LABELS)
