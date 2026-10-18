"""Snapshots agregados e exportação local; nenhum acesso individual ou template facial."""
import csv
from html import escape
from io import BytesIO, StringIO

from PIL import Image, UnidentifiedImageError
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.utils import ImageReader
from reportlab.lib.pagesizes import A4, landscape
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from sqlalchemy import select

from ..extensions import db
from ..models import AuditLog, utcnow
from ..alerts.forms import STATUSES
from .schedules import as_utc

NOTES = [
    'Período em UTC, data final inclusiva. Origens sintéticas, gateway, relatos manuais e acesso simulado permanecem identificadas.',
    'Disponibilidade estima somente intervalos observados: cada verificação vale até a próxima ou por 90 segundos. Lacunas são desconhecidas; fontes demo não contam como disponibilidade real.',
    'Alertas são selecionados pela criação no período. Status e tempos refletem o estado na geração; encerramentos podem ocorrer depois do período.',
    'Acesso é agregado, exclusivamente simulado. Não inclui nomes, matrículas, credenciais, capturas ou templates.'
]


def payload(kind, data, filters, organization_id):
    columns=[];rows=[]
    if kind=='availability':
        columns=['Câmera','Unidade','Fonte','Estado atual','Disponibilidade observada (%)','Cobertura observada (%)','Indisponibilidade média observada (s)','Última comunicação UTC']
        states={'online':'Online','offline':'Offline','unknown':'Desconhecido','demo':'Demonstração','disabled':'Desativada'}
        rows=[[r['name'],r['site'],r['source'],states[r['state']],r['availability_pct'],r['coverage_pct'],r['mean_offline_seconds'],r['last_seen']] for r in data['cameras']]
    elif kind=='failures':
        columns=['Unidade','Tipo','Fonte','Quantidade']
        failures={'processing_failure','integration_failure','camera_offline'}
        rows=[[r['site'],r['type'],r['source'],r['count']] for r in data['events'] if r['kind'] in failures]
        rows += [[r['site'],r['reason'],'Acesso simulado',r['count']] for r in data['access_rows'] if r['reason_code'] in {'policy_unavailable','verification_unavailable','verification_retry','state_changed'}]
    elif kind in {'alerts','resolution'}:
        columns=['Alerta','Unidade','Tipo','Fonte','Status atual','Criação UTC','Até reconhecimento (s)','Até resolução (s)']
        rows=[[r['id'],r['site'],r['type'],r['source'],STATUSES[r['status']],r['created_at'],r['ack_seconds'],r['resolution_seconds']] for r in data['alert_rows']]
    elif kind=='events':
        columns=['Unidade','Tipo de evento','Fonte','Quantidade']
        rows=[[r['site'],r['type'],r['source'],r['count']] for r in data['events']]
    elif kind=='access':
        columns=['Unidade','Ponto simulado','Decisão','Motivo','Método de teste','Quantidade']
        rows=[[r['site'],r['point_id'],'Permitido' if r['decision']=='allowed' else 'Negado',r['reason'],r['method'],r['count']] for r in data['access_rows']]
    elif kind=='audit':
        columns=['Registro','Data UTC','Autor interno','Ação','Entidade','Registro da entidade']
        logs=db.session.scalars(select(AuditLog).where(AuditLog.organization_id==organization_id,AuditLog.occurred_at>=filters.start,
              AuditLog.occurred_at<filters.end).order_by(AuditLog.id).limit(5001)).all()
        rows=[[r.id,as_utc(r.occurred_at).isoformat(),r.actor_id,r.action,r.resource_type,r.resource_id] for r in logs]
    else:raise ValueError('Tipo de relatório inválido.')
    notes=list(NOTES)
    if len(rows)>5000:notes.append('A tabela foi limitada a 5000 linhas. Reduza o período para detalhar os demais registros; totais abaixo abrangem todo o escopo selecionado.')
    totals={'Eventos registrados':data['event_total'],'Alertas recebidos':data['alerts']['received'],
            'Pendentes agora (recebidos no período)':data['alerts']['pending'],'Resolvidos (recebidos no período)':data['alerts']['resolved'],
            'Acesso simulado: tentativas':data['access']['total'],'Acesso simulado: permitidas':data['access']['allowed'],
            'Acesso simulado: negadas':data['access']['denied'],'Disponibilidade nos intervalos observados (%)':data['camera_totals']['availability_pct']}
    return {'columns':columns,'rows':rows[:5000],'totals':totals,'source_counts':data['source_counts'],'notes':notes}


def safe_cell(value):
    if value is None:return 'Sem dados'
    value=str(value)
    # Planilhas podem executar fórmulas mesmo após espaços ou caracteres de controle.
    if value.lstrip(' \t\r\n\v\f\ufeff\u200b').startswith(('=','+','-','@')) or value.startswith(('\t','\r','\n')):value="'"+value
    return value


def csv_bytes(report):
    output=StringIO(newline='');writer=csv.writer(output,lineterminator='\r\n')
    metadata=[['SENTINELA AI','Relatório '+report.identifier],['Organização',report.organization_name],
              ['Gerado em UTC',as_utc(report.generated_at).isoformat()],['Responsável',report.generator_name],
              ['Finalidade',report.purpose],['Período UTC',f'{report.start_date} a {report.end_date}'],['Filtro de fonte',report.source]]
    for row in metadata:writer.writerow([safe_cell(v) for v in row])
    writer.writerow([])
    for label,value in report.payload['totals'].items():writer.writerow([safe_cell(label),safe_cell(value)])
    writer.writerow([]);writer.writerow([safe_cell(v) for v in report.payload['columns']])
    for row in report.payload['rows']:writer.writerow([safe_cell(v) for v in row])
    writer.writerow([])
    for note in report.payload['notes']:writer.writerow(['Observação',safe_cell(note)])
    return output.getvalue().encode('utf-8-sig')


def pdf_bytes(report, title):
    output=BytesIO();styles=getSampleStyleSheet()
    styles['BodyText'].fontSize=8;styles['BodyText'].leading=11
    doc=SimpleDocTemplate(output,pagesize=landscape(A4),rightMargin=28,leftMargin=28,topMargin=65,bottomMargin=32,
                          title=title,author=report.generator_name)
    def paragraph(value,style='BodyText'):
        return Paragraph(escape('Sem dados' if value is None else str(value)),styles[style])
    story=[paragraph(title,'Title'),paragraph(report.organization_name,'Heading2'),
           paragraph(f'Identificador: {report.identifier} | Fonte: {report.source}'),
           paragraph(f'Período UTC: {report.start_date} a {report.end_date} | Gerado: {as_utc(report.generated_at).isoformat()}'),
           paragraph(f'Responsável: {report.generator_name} | Finalidade: {report.purpose}'),Spacer(1,12)]
    for label,value in report.payload['totals'].items():story.append(paragraph(f'{label}: {value if value is not None else "Sem dados"}'))
    story.append(Spacer(1,12))
    table_rows=[[paragraph(v) for v in report.payload['columns']]]+[[paragraph(v) for v in row] for row in report.payload['rows']]
    if len(table_rows)==1:table_rows.append([paragraph('Nenhum registro no período')]+[paragraph('') for _ in table_rows[0][1:]])
    table=Table(table_rows,repeatRows=1,colWidths=[doc.width/len(table_rows[0])]*len(table_rows[0]),hAlign='LEFT')
    table.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),colors.HexColor('#dce8f4')),('GRID',(0,0),(-1,-1),.25,colors.HexColor('#bbc6d0')),
                              ('VALIGN',(0,0),(-1,-1),'TOP'),('BOTTOMPADDING',(0,0),(-1,-1),6)]))
    story.extend([table,Spacer(1,12)])
    for note in report.payload['notes']:story.append(paragraph(note))
    def page(canvas,document):
        canvas.saveState();canvas.setFont('Helvetica',9)
        if report.logo_png:
            canvas.drawImage(ImageReader(BytesIO(report.logo_png)),28,document.pagesize[1]-54,width=100,height=35,preserveAspectRatio=True,mask='auto')
        else:canvas.drawString(28,document.pagesize[1]-35,'SENTINELA AI | '+report.organization_name[:90])
        canvas.drawRightString(document.pagesize[0]-28,18,f'{report.identifier} | Página {document.page}')
        canvas.restoreState()
    doc.build(story,onFirstPage=page,onLaterPages=page)
    return output.getvalue()


def normalize_logo(upload):
    data=upload.stream.read(48*1024+1)
    if not data or len(data)>48*1024:raise ValueError('Use logo PNG/JPEG de até 48 KiB.')
    try:
        with Image.open(BytesIO(data)) as image:
            if image.format not in {'PNG','JPEG'} or not 1<=image.width<=512 or not 1<=image.height<=512 or getattr(image,'n_frames',1)!=1:
                raise ValueError('Use PNG/JPEG não animado de até 512 × 512 pixels.')
            image.load();output=BytesIO();clean=image.convert('RGBA');clean.info.clear();clean.save(output,format='PNG')
            normalized=output.getvalue()
            if len(normalized)>256*1024:raise ValueError('Logo normalizado excede o limite. Simplifique a imagem.')
            return normalized
    except (UnidentifiedImageError,OSError,Image.DecompressionBombError):
        raise ValueError('Arquivo de imagem inválido.') from None
