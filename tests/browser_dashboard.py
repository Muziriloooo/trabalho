import os
from playwright.sync_api import sync_playwright
rows=[dict(id=i,mes=f'2026-{(i%6)+1:02}',cliente=f'Cliente teste {i:02}',filial=['SÃO PAULO','RIO DE JANEIRO','PARANÁ'][i%3],segmento=['PATRIMONIAL','FACILITIES'][i%2],target=10000,gasto=8000,economia=2000,efetivo=10,diasUteis=None if i%2 else 4,visita='SIM' if i%2 else 'NÃO',notificacao='2026-01-01',implantacao='2026-01-10',status='Concluído') for i in range(60)]
payload={'records':rows,'meta':{'registros':60,'fonte':'google','versaoArquivo':'fixture','lidoEm':'2026-10-24T10:00:00Z','issues':{}}}
with sync_playwright() as p:
 b=p.chromium.launch(headless=True,executable_path='/usr/bin/chromium',args=['--no-sandbox'])
 page=b.new_page(viewport={'width':1440,'height':1000}); errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
 page.route('**/api/data',lambda r:r.fulfill(json=payload))
 page.goto(os.getenv('DASHBOARD_TEST_URL','http://127.0.0.1:8765'));page.wait_for_selector('.kpi-card')
 assert page.locator('.kpi-card').count()==4
 assert page.locator('.kpi-value').first.inner_text()=='60'
 assert page.locator('.kpi-change').count()==0
 page.select_option('#filter-month','2026-02');assert 'Sem variação mensal' in page.locator('.kpi-card').first.inner_text()
 page.select_option('#filter-month','2026-01');assert 'Sem mês anterior comparável' in page.locator('.kpi-card').first.inner_text()
 page.select_option('#filter-month','')
 assert '4,0 dias úteis' in page.locator('#executive-context').inner_text()
 page.locator('.kpi-card').first.click();assert page.locator('#page-dados').is_visible();assert page.locator('#table-records-count').inner_text()=='(60)'
 page.locator('.nav-item[data-page="overview"]').click();page.locator('#monthly-chart [data-month]').first.click();assert page.locator('#page-dados').is_visible();assert page.locator('#filter-month').input_value()=='2026-01';assert page.locator('#table-records-count').inner_text()=='(10)'
 page.locator('#clear-filters').click();page.locator('.nav-item[data-page="financeiro"]').click();page.locator('.financial-branch-row').first.click();assert page.locator('#page-dados').is_visible();assert page.locator('#filter-filial').input_value()
 page.locator('#clear-filters').click();page.locator('.nav-item[data-page="overview"]').click()
 page.screenshot(path='/tmp/executive-overview.png',full_page=True)
 for view in ['financeiro','segmentos','mapa','dados']:
  page.locator(f'.nav-item[data-page="{view}"]').click();page.wait_for_timeout(120)
  assert page.locator(f'#page-{view}').is_visible()
  page.screenshot(path=f'/tmp/executive-{view}.png',full_page=True)
 assert page.locator('#records-table th').count()==13
 page.locator('#table-next').click();assert '2 /' in page.locator('#table-page-number').inner_text()
 with page.expect_download() as dl:page.locator('#export-csv').click()
 assert dl.value.suggested_filename.endswith('.csv')
 page.select_option('#filter-filial','SÃO PAULO');page.locator('.nav-item[data-page="overview"]').click();assert page.locator('.kpi-value').first.inner_text()=='20'
 page.locator('#filter-client').fill('inexistente');assert page.locator('.kpi-value').first.inner_text()=='0'
 page.locator('#clear-filters').click();assert page.locator('.kpi-value').first.inner_text()=='60'
 page.route('**/api/data',lambda r:r.fulfill(status=503,json={'error':'Teste de indisponibilidade'}))
 page.locator('#refresh-button').click();page.wait_for_selector('#error-panel');assert page.locator('#page-overview').is_visible();assert 'desatualizados' in page.locator('#error-message').inner_text()
 page.unroute('**/api/data');page.route('**/api/data',lambda r:r.fulfill(json=payload));page.locator('#retry-button').click();page.wait_for_selector('#error-panel',state='hidden')
 page.locator('#presentation-button').click();assert 'presenting' in page.locator('body').get_attribute('class');page.keyboard.press('Escape');page.wait_for_timeout(200);assert 'presenting' not in (page.locator('body').get_attribute('class') or '')
 for width in (1920,1366,768,390):
  page.set_viewport_size({'width':width,'height':900});page.wait_for_timeout(100)
  assert page.evaluate('document.documentElement.scrollWidth<=innerWidth'),f'overflow {width}'
  page.screenshot(path=f'/tmp/executive-{width}.png',full_page=True)
 page.set_viewport_size({'width':1440,'height':1000})
 page.locator('.nav-item[data-page="mapa"]').click()
 page.locator('[data-geo-sort="cliente"]').click()
 page.locator('#geo-next').click();assert '2 /' in page.locator('#geo-table-page').inner_text()
 page.locator('#geo-zoom-in').click();page.locator('#geo-reset').click()
 page.locator('[data-geo-base]').first.click();assert page.locator('#filter-filial').input_value()
 page.locator('#clear-filters').click()
 payload['records']=[dict(rows[i%60],id=i,cliente=f'Teste {i}') for i in range(5000)]
 payload['meta'].update(versaoArquivo='large',registros=5000)
 page.locator('#refresh-button').click();page.wait_for_function("document.querySelector('.kpi-value').textContent==='5.000'")
 page.locator('.nav-item[data-page="dados"]').click();assert page.locator('#records-body tr').count()==12
 payload['records']=[];payload['meta'].update(versaoArquivo='empty',registros=0)
 page.locator('#refresh-button').click();page.wait_for_function("document.querySelector('#records-body').textContent.includes('Nenhum registro')")
 assert not errors,errors
 print('Browser: five pages, 13 columns, pagination, CSV, filters, empty results, outage/recovery, presentation, four viewport sizes: PASS')
 b.close()
