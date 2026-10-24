"""Painel de Implantações 2026 — servidor local sem dependências externas.
Execute: python app.py (Python 3.9+). Abra http://localhost:8765
Lê a planilha Excel .xlsx do diretório dados em cada alteração do arquivo.
"""
from __future__ import annotations

import math
import json
import hashlib
import time
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError
from urllib.parse import quote, parse_qs
import mimetypes
import os
import re
import sys
import threading
import webbrowser
import zipfile
from datetime import datetime, timedelta
from functools import lru_cache
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse, unquote
from xml.etree import ElementTree as ET

ROOT = Path(__file__).resolve().parent
STATIC = ROOT / 'static'
DATA_DIR = ROOT / 'dados'
EXCEL = DATA_DIR / 'IMPLANTAÇÕES 2026.xlsx'
CONFIG = ROOT / 'config_google.json'
GOOGLE_CACHE_SECONDS = 30
HOST = '127.0.0.1'
PORT = int(os.getenv('PORT', '8765'))
NS = '{http://schemas.openxmlformats.org/spreadsheetml/2006/main}'
_cache = {'key': None, 'value': None}
_lock = threading.Lock()

FILIAL_CORRECTIONS = {
    'SAO PAULO': 'SÃO PAULO', 'SAO JOSE DOS CAMPOS': 'SÃO JOSÉ DOS CAMPOS',
    'SAO JOSE DO RIO PRETO': 'SÃO JOSÉ DO RIO PRETO', 'PARANA': 'PARANÁ',
    'GOIAS': 'GOIÁS', 'CEARA': 'CEARÁ', 'MARANHAO': 'MARANHÃO',
    'ESPIRITO SANTO': 'ESPÍRITO SANTO', 'RIBEIRAO PRETO': 'RIBEIRÃO PRETO',
    'SANTA VATARINA': 'SANTA CATARINA', 'SSOROCABA': 'SOROCABA',
    'MATO GOSSO': 'MATO GROSSO', 'MATO GROSO': 'MATO GROSSO',
    'BRASILIA': 'BRASÍLIA', 'JUNDIAI': 'JUNDIAÍ',
}


def clean_text(v, default='Não informado'):
    s = str(v).strip() if v is not None else ''
    return re.sub(r'\s+', ' ', s) if s else default


def norm_branch(v):
    raw = clean_text(v)
    return FILIAL_CORRECTIONS.get(raw.upper(), raw.upper() if raw != 'Não informado' else raw)


def norm_segment(v):
    raw = clean_text(v)
    return {'FACILITES': 'FACILITIES'}.get(raw.upper(), raw.upper() if raw != 'Não informado' else raw)


def as_num(v):
    if isinstance(v, bool):
        return None
    try:
        if isinstance(v, str):
            v = v.strip().replace('R$', '').replace(' ', '')
            if ',' in v:
                v = v.replace('.', '').replace(',', '.')
        n = float(v)
        return n if math.isfinite(n) else None
    except (ValueError, TypeError):
        return None


def excel_date(v):
    if isinstance(v, (float, int)):
        try:
            return (datetime(1899, 12, 30) + timedelta(days=v)).strftime('%Y-%m-%d')
        except (ValueError, OverflowError):
            return None
    if isinstance(v, datetime):
        return v.date().isoformat()
    if isinstance(v, str):
        v = v.strip()
        if re.fullmatch(r'\d{4}-\d{2}-\d{2}', v):
            try:
                return datetime.strptime(v, '%Y-%m-%d').date().isoformat()
            except ValueError:
                return None
        for fmt in ('%d/%m/%Y', '%m/%d/%Y'):
            try:
                return datetime.strptime(v, fmt).date().isoformat()
            except ValueError:
                pass
    return None


def xlsx_rows(path):
    """Reader XLSX leve, apenas valores salvos (sem executar fórmulas)."""
    with zipfile.ZipFile(path) as z:
        entries = z.namelist()
        if 'xl/workbook.xml' not in entries:
            raise ValueError('O arquivo enviado não parece ser uma planilha Excel válida.')
        sst = []
        if 'xl/sharedStrings.xml' in entries:
            strings = ET.fromstring(z.read('xl/sharedStrings.xml'))
            for si in strings.findall(NS + 'si'):
                sst.append(''.join((t.text or '') for t in si.iter(NS + 't')))
        sheet_files = sorted((e for e in entries if re.fullmatch(r'xl/worksheets/sheet\d+\.xml', e)),
                             key=lambda p: int(re.search(r'sheet(\d+)', p).group(1)))
        if not sheet_files:
            raise ValueError('Nenhuma aba de dados encontrada no Excel.')
        sheet = ET.fromstring(z.read(sheet_files[0]))
        out = []
        for row in sheet.findall('.//' + NS + 'sheetData/' + NS + 'row'):
            vals = [None] * 13
            for cell in row.findall(NS + 'c'):
                ref = cell.get('r', '')
                m = re.match(r'([A-Z]+)', ref)
                if not m:
                    continue
                idx = 0
                for ch in m.group(1):
                    idx = idx * 26 + ord(ch) - 64
                idx -= 1
                if idx >= len(vals):
                    continue
                typ = cell.get('t')
                v = cell.find(NS + 'v')
                if typ == 'inlineStr':
                    node = cell.find(NS + 'is')
                    val = ''.join((t.text or '') for t in node.iter(NS + 't')) if node is not None else None
                elif v is None or v.text is None:
                    val = None
                elif typ == 's':
                    val = sst[int(v.text)]
                elif typ in ('str', 'e'):
                    val = v.text if typ == 'str' else None
                elif typ == 'b':
                    val = (v.text == '1')
                else:
                    try:
                        val = float(v.text)
                    except ValueError:
                        val = v.text
                vals[idx] = val
            out.append(vals)
        return out


def build_data(raw=None, source_name=None, source_version=None, source_updated=None):
    if raw is None:
        raw = xlsx_rows(EXCEL)
    if not raw or str(raw[0][1]).strip().upper() != 'CLIENTE':
        raise ValueError('A primeira aba deve ter CLIENTE na coluna B e as 13 colunas esperadas.')
    records = []
    issues = {'semMes': 0, 'semFilial': 0, 'semSegmento': 0, 'efetivoInvalido': 0, 'prazoNegativo': 0}
    for excel_row, r in enumerate(raw[1:], 2):
        r = list(r[:13]) + [None] * max(0, 13-len(r))
        cliente = clean_text(r[1], '')
        if not cliente:
            continue  # evita zeros provenientes de fórmulas em linhas vazias
        mes_date = excel_date(r[0])
        filial = norm_branch(r[2])
        seg = norm_segment(r[3])
        effective = as_num(r[11])
        prazo = as_num(r[9])
        if not mes_date: issues['semMes'] += 1
        if filial == 'Não informado': issues['semFilial'] += 1
        if seg == 'Não informado': issues['semSegmento'] += 1
        if r[11] not in (None, '') and effective is None: issues['efetivoInvalido'] += 1
        if prazo is not None and prazo < 0: issues['prazoNegativo'] += 1
        visit = clean_text(r[12], '').upper()
        visit = 'SIM' if visit == 'SIM' else ('NÃO' if visit in ('NÃO', 'NAO') else 'Não informado')
        records.append({
            'id': excel_row,
            'mes': mes_date[:7] if mes_date else '',
            'cliente': cliente,
            'filial': filial,
            'segmento': seg,
            'target': as_num(r[4]),
            'gasto': as_num(r[5]),
            'economia': as_num(r[6]),
            'notificacao': excel_date(r[7]),
            'implantacao': excel_date(r[8]),
            'diasUteis': prazo,
            'status': clean_text(r[10]),
            'efetivo': effective if effective is not None and effective >= 0 else None,
            'visita': visit,
        })
    return {
        'records': records,
        'meta': {
            'arquivo': source_name or EXCEL.name,
            'fonte': 'google' if source_name else 'excel',
            'versaoArquivo': source_version or EXCEL.stat().st_mtime_ns,
            'atualizadoEm': source_updated or datetime.fromtimestamp(EXCEL.stat().st_mtime).astimezone().isoformat(timespec='seconds'),
            'lidoEm': datetime.now().astimezone().isoformat(timespec='seconds'),
            'registros': len(records),
            'linhasDescartadas': len(raw) - 1 - len(records),
            'issues': issues,
        }
    }


def load_source_config():
    if not CONFIG.exists():
        return {'fonte': 'excel'}
    try:
        cfg = json.loads(CONFIG.read_text(encoding='utf-8-sig'))
        if not isinstance(cfg, dict):
            raise ValueError('A configuração deve ser um objeto JSON.')
        source = str(cfg.get('fonte', 'excel')).lower().strip()
        if source not in ('google', 'excel'):
            raise ValueError('Fonte inválida. Use "google" ou "excel".')
        cfg['fonte'] = source
        return cfg
    except (ValueError, OSError) as exc:
        raise ValueError('Erro em config_google.json: ' + str(exc)) from exc


def google_spreadsheet_id(value):
    value = str(value or '').strip()
    match = re.search(r'/spreadsheets/d/([A-Za-z0-9_-]+)', value)
    if match:
        return match.group(1)
    if re.fullmatch(r'[A-Za-z0-9_-]{20,}', value):
        return value
    raise ValueError('Informe o link completo do Google Planilhas em config_google.json.')


def google_resolve_tab(cfg, spreadsheet_id, bearer_token):
    """Resolve a aba de forma segura com os metadados do Google Sheets.

    Prioriza o nome exato configurado; se nao existir, usa o gid do link;
    se houver apenas uma guia, usa-a. Nao baixa conteudo de outras guias.
    """
    meta_url = (f'https://sheets.googleapis.com/v4/spreadsheets/'
                f'{quote(spreadsheet_id, safe="")}'
                '?fields=sheets(properties(sheetId,title,index))')
    request = Request(meta_url, headers={
        'Authorization': 'Bearer ' + bearer_token,
        'Accept': 'application/json'
    })
    with urlopen(request, timeout=20) as response:
        payload = json.loads(response.read().decode('utf-8'))
    tabs = [s.get('properties', {}) for s in payload.get('sheets', []) or []
            if s.get('properties', {}).get('title') is not None]
    if not tabs:
        raise ValueError('A planilha nao possui guias disponiveis.')
    configured = str(cfg.get('aba', '')).strip()
    exact = next((str(t['title']) for t in tabs if str(t['title']) == configured), None)
    if exact is not None:
        return exact
    link = str(cfg.get('planilha_url', ''))
    parsed = urlparse(link)
    gid_str = (parse_qs(parsed.query).get('gid') or
               parse_qs(parsed.fragment).get('gid') or [None])[0]
    if gid_str is not None:
        by_id = next((str(t['title']) for t in tabs
                      if str(t.get('sheetId')) == str(gid_str)), None)
        if by_id is not None:
            return by_id
    if len(tabs) == 1:
        return str(tabs[0]['title'])
    names = ', '.join(repr(str(t['title'])) for t in tabs[:15])
    raise ValueError('A aba configurada ' + repr(configured) +
                     ' nao existe nessa planilha. Abas encontradas: ' + names +
                     '. Corrija o campo "aba" em config_google.json ou abra a guia correta e copie seu link com gid.')


def google_rows(cfg):
    """Lê uma planilha privada com conta de serviço; nenhuma chave é enviada ao navegador."""
    try:
        from google.oauth2 import service_account
        from google.auth.transport.requests import Request as GoogleRequest
    except ImportError as exc:
        raise RuntimeError('Bibliotecas Google indisponiveis no Python do servidor (' + str(exc) + '). Feche a janela do painel e execute iniciar_windows.bat atualizado. Ele prepara o ambiente automaticamente.') from exc

    spreadsheet_id = google_spreadsheet_id(cfg.get('planilha_url'))
    credential_path = str(cfg.get('credenciais', 'segredos/google_service_account.json'))
    credential_file = (ROOT / credential_path).resolve()
    if ROOT.resolve() not in credential_file.parents:
        raise ValueError('Guarde as credenciais somente dentro da pasta do painel.')
    if not credential_file.is_file():
        raise FileNotFoundError('Não encontrei segredos/google_service_account.json. Consulte LEIA-ME-GOOGLE.txt.')
    # Somente o escopo de leitura. Jamais use chaves no HTML/JavaScript.
    credentials = service_account.Credentials.from_service_account_file(
        str(credential_file), scopes=['https://www.googleapis.com/auth/spreadsheets.readonly']
    )
    credentials.refresh(GoogleRequest())
    real_tab = google_resolve_tab(cfg, spreadsheet_id, credentials.token)
    tab = "'" + real_tab.replace("'", "''") + "'!A:M"
    endpoint = (f'https://sheets.googleapis.com/v4/spreadsheets/{quote(spreadsheet_id, safe="")}/'
                f'values/{quote(tab, safe="")}'
                '?valueRenderOption=UNFORMATTED_VALUE&dateTimeRenderOption=SERIAL_NUMBER')
    request = Request(endpoint, headers={'Authorization': 'Bearer ' + credentials.token,
                                         'Accept': 'application/json'})
    try:
        with urlopen(request, timeout=20) as response:
            payload = json.loads(response.read().decode('utf-8'))
    except HTTPError as exc:
        if exc.code in (401, 403):
            raise PermissionError('Sem permissão para ler a planilha. Compartilhe com o e-mail da conta de serviço como Leitor e confirme que a API Google Sheets está ativa.') from exc
        if exc.code == 404:
            raise FileNotFoundError('Planilha/aba não encontrada. Confira o link e o nome da aba na configuração.') from exc
        raise RuntimeError(f'Google Sheets API retornou HTTP {exc.code}.') from exc
    except (TimeoutError, URLError) as exc:
        raise ConnectionError('Não foi possível consultar o Google Planilhas. Verifique a conexão com a internet.') from exc
    rows = payload.get('values', [])
    if not isinstance(rows, list):
        raise ValueError('Resposta inesperada do Google Planilhas.')
    # A API omite as últimas colunas vazias; o parser usa A até M.
    rows = [(list(r[:13]) + [None] * (13-len(r))) for r in rows]
    return rows


def get_data():
    cfg = load_source_config()
    if cfg['fonte'] == 'google':
        # Reconsulta o Google no máximo uma vez a cada 30 segundos por processo.
        cfg_sig = hashlib.sha256(json.dumps(cfg, sort_keys=True).encode('utf-8')).hexdigest()
        key = ('google', cfg_sig, int(time.monotonic() // GOOGLE_CACHE_SECONDS))
        with _lock:
            if _cache['key'] != key:
                raw = google_rows(cfg)
                signature = hashlib.sha256(json.dumps(raw, ensure_ascii=False, default=str).encode('utf-8')).hexdigest()[:20]
                label = 'Google Planilhas' + (' · ' + str(cfg.get('aba')) if cfg.get('aba') else '')
                _cache['value'] = build_data(raw, label, signature, datetime.now().astimezone().isoformat(timespec='seconds'))
                _cache['key'] = key
            return _cache['value']

    stat = EXCEL.stat()
    key = ('excel', stat.st_mtime_ns, stat.st_size)
    with _lock:
        if _cache['key'] != key:
            _cache['value'] = build_data()
            _cache['key'] = key
        return _cache['value']


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        print('[%s]' % self.log_date_time_string(), fmt % args)

    def send_bytes(self, data, content_type, status=200, extra_headers=None):
        self.send_response(status)
        self.send_header('Content-Type', content_type)
        self.send_header('Content-Length', str(len(data)))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        for name, val in (extra_headers or {}).items():
            self.send_header(name, val)
        self.end_headers()
        self.wfile.write(data)

    def send_json(self, payload, status=200):
        self.send_bytes(json.dumps(payload, ensure_ascii=False, separators=(',', ':')).encode('utf-8'),
                        'application/json; charset=utf-8', status)

    def do_GET(self):
        path = unquote(urlparse(self.path).path)
        if path == '/api/data':
            try:
                self.send_json(get_data())
            except Exception as exc:
                self.send_json({'error': str(exc)}, 500)
            return
        if path == '/api/download':
            if load_source_config()['fonte'] == 'google':
                self.send_json({'error': 'Fonte Google: baixe a planilha diretamente no Google Planilhas.'}, 409)
                return
            if not EXCEL.exists():
                self.send_json({'error': 'Arquivo não encontrado'}, 404)
                return
            self.send_bytes(EXCEL.read_bytes(), 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                            extra_headers={'Content-Disposition': 'attachment; filename="implantacoes_2026.xlsx"'})
            return
        if path in ('/', '/index.html'):
            file = STATIC / 'index.html'
        else:
            file = (STATIC / path.lstrip('/')).resolve()
            if STATIC.resolve() not in file.parents:
                self.send_json({'error': 'Caminho inválido'}, 403)
                return
        if not file.exists() or not file.is_file():
            self.send_json({'error': 'Não encontrado'}, 404)
            return
        typ = mimetypes.guess_type(file.name)[0] or 'application/octet-stream'
        if typ.startswith('text/') or typ == 'application/javascript':
            typ += '; charset=utf-8'
        self.send_bytes(file.read_bytes(), typ)

    def do_PUT(self):
        if urlparse(self.path).path != '/api/upload':
            self.send_json({'error': 'Não encontrado'}, 404)
            return
        if load_source_config()['fonte'] == 'google':
            self.send_json({'error': 'Fonte Google: faça alterações diretamente no Google Planilhas.'}, 409)
            return
        try:
            length = int(self.headers.get('Content-Length', '0'))
            if not 100 < length < 30 * 1024 * 1024:
                raise ValueError('Selecione uma planilha .xlsx de até 30 MB.')
            data = self.rfile.read(length)
            import io
            if not zipfile.is_zipfile(io.BytesIO(data)):
                raise ValueError('Envie um Excel .xlsx válido.')
            temp = DATA_DIR / 'nova_planilha.tmp'
            DATA_DIR.mkdir(exist_ok=True)
            temp.write_bytes(data)
            try:
                rows = xlsx_rows(temp)
                if not rows or str(rows[0][1]).strip().upper() != 'CLIENTE':
                    raise ValueError('Estrutura incompatível. A coluna B precisa ser CLIENTE.')
            except Exception:
                temp.unlink(missing_ok=True)
                raise
            os.replace(temp, EXCEL)
            with _lock:
                _cache['key'] = None
            self.send_json({'ok': True, 'meta': get_data()['meta']})
        except Exception as exc:
            self.send_json({'error': str(exc)}, 400)


def main():
    if load_source_config()['fonte'] == 'excel' and not EXCEL.exists():
        print('Não encontrado:', EXCEL)
        print('Coloque IMPLANTAÇÕES 2026.xlsx dentro da pasta dados.')
        sys.exit(1)
    http = ThreadingHTTPServer((HOST, PORT), Handler)
    print('\n' + '=' * 62)
    print('  PAINEL DE IMPLANTAÇÕES 2026')
    print('  Abra: http://localhost:%s' % PORT)
    cfg = load_source_config()
    print('  Fonte de dados: ' + ('Google Planilhas (privado)' if cfg['fonte'] == 'google' else str(EXCEL)))
    print('  Atualização de dados verificada a cada 30 s no navegador.')
    print('  Para sair, pressione Ctrl+C.\n' + '=' * 62 + '\n')
    if '--no-browser' not in sys.argv:
        threading.Timer(1.0, lambda: webbrowser.open('http://localhost:%s' % PORT)).start()
    try:
        http.serve_forever()
    except KeyboardInterrupt:
        print('\nServidor encerrado.')
    finally:
        http.server_close()


if __name__ == '__main__':
    main()
