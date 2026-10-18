from io import BytesIO
import csv

import pytest
from PIL import Image
from sqlalchemy import select

from sentinela.extensions import db
from sentinela.models import AuditLog, ReportRun, RoleAssignment
from sentinela.services.reports import safe_cell
from test_analytics import analytics_data
from test_inventory import inventory, post


def create_report(client,kind='events',**overrides):
    response=post(client,'/reports',{'kind':kind,'start':'2026-10-15','end':'2026-10-15','site_id':'0','source':'all','purpose':'Validação operacional agregada',**overrides})
    assert response.status_code==302,response.text[:200]
    return response.location


@pytest.mark.parametrize('kind',['availability','failures','alerts','events','resolution','access','audit'])
def test_report_generation_and_exports_are_persisted_and_audited(app,client,login,analytics_data,kind):
    login();path=create_report(client,kind)
    page=client.get(path)
    assert page.status_code==200 and 'Exportar CSV' in page.text and 'Exportar PDF' in page.text
    csv_response=post(client,path+'/export/csv',{})
    assert csv_response.status_code==200 and csv_response.data.startswith(b'\xef\xbb\xbf')
    assert 'attachment;' in csv_response.headers['Content-Disposition'] and csv_response.headers['Cache-Control']=='no-store'
    text=csv_response.data.decode('utf-8-sig')
    assert 'Responsável,admin@example.test' in text and 'Unidade de outro cliente' not in text
    pdf=post(client,path+'/export/pdf',{})
    assert pdf.status_code==200 and pdf.data.startswith(b'%PDF-') and pdf.data.rstrip().endswith(b'%%EOF')
    assert pdf.headers['Cache-Control']=='no-store'
    with app.app_context():
        report=db.session.scalar(select(ReportRun))
        assert report.identifier and report.payload['totals']['Eventos registrados']==4
        actions=db.session.scalars(select(AuditLog.action).where(AuditLog.resource_type=='ReportRun')).all()
        assert actions==['report.generated','report.exported_csv','report.exported_pdf']


def test_access_report_is_aggregated_and_contains_no_subject_or_token_fields(app,client,login,analytics_data):
    login();path=create_report(client,'access')
    with app.app_context():
        report=db.session.scalar(select(ReportRun))
        assert report.payload['columns']==['Unidade','Ponto simulado','Decisão','Motivo','Método de teste','Quantidade']
        assert sum(r[-1] for r in report.payload['rows'])==3
        assert all('subject' not in c.lower() and 'token' not in c.lower() for c in report.payload['columns'])


def test_report_is_snapshot_and_scope_is_rechecked_on_view_and_export(app,client,login,analytics_data):
    login('operator@example.test');path=create_report(client)
    assert client.get(path).status_code==200
    with app.app_context():
        db.session.delete(db.session.get(RoleAssignment,analytics_data['assignment']));db.session.commit()
    assert client.get(path).status_code==404
    assert post(client,path+'/export/csv',{}).status_code==404


def test_cross_tenant_and_privileged_audit_report_access_denied(client,login,analytics_data):
    login();path=create_report(client,'audit')
    post(client,'/logout',{});login('other@example.test');assert client.get(path).status_code==404
    post(client,'/logout',{});login('operator@example.test')
    assert post(client,'/reports',{'kind':'audit','start':'2026-10-15','end':'2026-10-15','site_id':'0','source':'all','purpose':'Teste'}).status_code==422
    assert client.get(path).status_code==404


def test_report_filters_no_foreign_scope_or_unscoped_fallback(client,login,analytics_data):
    login()
    fields={'kind':'events','start':'2026-10-15','end':'2026-10-15','site_id':'0','source':'all','purpose':'Teste de filtros'}
    for change in [{'site_id':analytics_data['sites'][2]},{'source':'other'},{'start':'invalid'},{'purpose':''},{'start':'2025-01-01'}]:
        assert post(client,'/reports',{**fields,**change}).status_code==422
    path=create_report(client,source='gateway')
    assert 'Fonte de câmera indisponível' in client.get(path).text
    assert 'Movimento em área autorizada' not in client.get(path).text


@pytest.mark.parametrize('value',['=HYPERLINK("x")','+SUM(1,2)','-cmd','@SUM(1)','  =1+2','\t=1','\r=1','\ufeff=1','\u200b=1'])
def test_csv_neutralizes_formula_cells(value):
    assert safe_cell(value).startswith("'")


def test_csv_escaping_through_real_export(app,client,login,analytics_data):
    from sentinela.models import Site
    with app.app_context():
        db.session.get(Site,analytics_data['sites'][0]).name='=malicious()';db.session.commit()
    login();path=create_report(client)
    response=post(client,path+'/export/csv',{})
    rows=list(csv.reader(BytesIO(response.data).read().decode('utf-8-sig').splitlines()))
    assert any("'=malicious()" in row for row in rows)


def test_logo_upload_normalized_and_snapshotted(app,client,login,analytics_data):
    login();image=BytesIO();Image.new('RGB',(100,40),(0,80,160)).save(image,format='PNG');image.seek(0)
    response=post(client,'/reports/branding',{'logo':(image,'logo.png')})
    assert response.status_code==302
    assert client.get('/reports/logo').mimetype=='image/png'
    path=create_report(client)
    with app.app_context():assert db.session.scalar(select(ReportRun)).logo_png.startswith(b'\x89PNG')
    assert post(client,'/reports/branding',{'remove':'y'}).status_code==302
    assert client.get('/reports/logo').status_code==404
    assert client.get(path+'/logo').mimetype=='image/png'
    assert post(client,path+'/export/pdf',{}).data.startswith(b'%PDF-')


@pytest.mark.parametrize('data,filename',[(b'<svg/>','logo.svg'),(b'not-png','logo.png'),(b'x'*50000,'logo.png')])
def test_invalid_logo_rejected(client,login,data,filename):
    login();assert post(client,'/reports/branding',{'logo':(BytesIO(data),filename)}).status_code==422


def test_exports_require_post_csrf_and_current_console_role(client,login,analytics_data):
    login();path=create_report(client)
    assert client.get(path+'/export/csv').status_code==405
    assert client.post(path+'/export/pdf',data={}).status_code==400
    post(client,'/logout',{});login('physical@example.test');assert client.get('/reports').status_code==403
    post(client,'/logout',{});login('platform@example.test');assert client.get('/reports').status_code==403
