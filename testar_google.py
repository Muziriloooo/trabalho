# Diagnostico da conexao Google Sheets - Dashboard Implantacoes 2026
# Mostra somente conta de servico, projeto e motivo do erro retornado pela API.
# Nao imprime chave privada, senha, token ou conteudo confidencial da planilha.
import json
import sys
from pathlib import Path
from urllib.error import HTTPError

from app import ROOT, load_source_config, google_rows, build_data


def obter_causa_http(exc):
    atual = exc
    vistos = set()
    while atual is not None and id(atual) not in vistos:
        vistos.add(id(atual))
        if isinstance(atual, HTTPError):
            return atual
        atual = getattr(atual, '__cause__', None) or getattr(atual, '__context__', None)
    return None


def detalhes_google(http_error):
    print('HTTP retornado pelo Google:', http_error.code)
    try:
        corpo = json.loads(http_error.read(32768).decode('utf-8', errors='replace'))
        erro = corpo.get('error', {})
        if not isinstance(erro, dict):
            erro = {}
        status = str(erro.get('status', '')).strip()
        mensagem = str(erro.get('message', '')).strip().replace('\n', ' ')
        if status:
            print('Status da API:', status[:120])
        if mensagem:
            print('Mensagem da API:', mensagem[:700])
        motivos = []
        for info in erro.get('details', []) or []:
            if isinstance(info, dict) and info.get('reason'):
                motivos.append(str(info.get('reason')))
        for info in erro.get('errors', []) or []:
            if isinstance(info, dict) and info.get('reason'):
                motivos.append(str(info.get('reason')))
        if motivos:
            print('Motivo(s):', ', '.join(dict.fromkeys(motivos))[:220])
        texto = (mensagem + ' ' + ' '.join(motivos)).lower()
        if ('disabled' in texto or 'not been used' in texto or 'accessnotconfigured' in texto
                or 'service_disabled' in texto or 'api has not' in texto):
            print('\nPROXIMA ACAO: Ative Google Sheets API no projeto indicado em project_id.')
            print('https://console.cloud.google.com/apis/library/sheets.googleapis.com')
        elif ('scope' in texto or 'insufficientpermissions' in texto):
            print('\nPROXIMA ACAO: Verifique as permissoes OAuth de leitura e a configuracao da conta de servico.')
        elif http_error.code == 401:
            print('\nPROXIMA ACAO: Verifique se o JSON pertence a uma conta de servico valida e ativa.')
        elif http_error.code == 403:
            print('\nPROXIMA ACAO: Confira o compartilhamento da planilha com o client_email abaixo,')
            print('a Google Sheets API e eventuais restricoes de compartilhamento da empresa.')
        elif http_error.code == 400 and ('range' in texto or 'parse' in texto):
            print('\nPROXIMA ACAO: Verifique a guia ativa no Google Planilhas. O painel usa o gid do link automaticamente.')
        elif http_error.code == 404:
            print('\nPROXIMA ACAO: Confira o link e o nome da aba da planilha.')
    except Exception:
        print('Nao foi possivel interpretar a mensagem detalhada retornada pelo Google.')
        print('Confira o compartilhamento da planilha e a ativacao da API.')


def main():
    print('=' * 60)
    print(' DIAGNOSTICO GOOGLE PLANILHAS - IMPLANTACOES 2026')
    print('=' * 60)
    cfg = load_source_config()
    if cfg.get('fonte') != 'google':
        raise ValueError('Fonte precisa ser google em config_google.json.')
    print('Aba configurada:', cfg.get('aba') or '(primeira aba)')
    credencial = (ROOT / cfg.get('credenciais', 'segredos/google_service_account.json')).resolve()
    if not credencial.is_file():
        print('ARQUIVO JSON NAO ENCONTRADO:', str(credencial))
        print('Coloque a chave em segredos\\google_service_account.json')
        return 1
    with credencial.open('r', encoding='utf-8-sig') as arquivo:
        dados_credencial = json.load(arquivo)
    email = dados_credencial.get('client_email', '(ausente)')
    projeto = dados_credencial.get('project_id', '(ausente)')
    print('Conta utilizada (client_email):', email)
    print('Projeto vinculado ao JSON (project_id):', projeto)
    print('DICA: e esse client_email que precisa constar como LEITOR em Compartilhar.')
    print('\nConsultando Google Sheets API...')
    try:
        dados = build_data(google_rows(cfg), 'Google Planilhas', 'teste', 'diagnostico')
        print('\nCONEXAO OK - leitura somente')
        print('Implantacoes:', dados.get('meta', {}).get('registros', 'desconhecido'))
        print('Execute iniciar_windows.bat para abrir o site.')
        return 0
    except Exception as exc:
        print('\nNAO FOI POSSIVEL CONECTAR:', str(exc))
        erro_http = obter_causa_http(exc)
        if erro_http:
            detalhes_google(erro_http)
        else:
            print('Nao houve resposta HTTP disponivel para diagnostico.')
        print('\nNunca compartilhe o arquivo JSON ou a chave privada.')
        return 1


if __name__ == '__main__':
    try:
        sys.exit(main())
    except Exception as erro:
        print('ERRO LOCAL:', str(erro))
        sys.exit(1)
