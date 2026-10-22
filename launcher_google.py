# -*- coding: utf-8 -*-
"""Iniciador do Dashboard de Implantações 2026.
Cria um ambiente Python isolado para que instalação, teste e site
sempre usem as mesmas bibliotecas. Chaves do Google nunca são lidas aqui.
"""
from __future__ import annotations
import importlib.util
import os
import socket
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
ENV_DIR = ROOT / '.ambiente_dashboard'
PYTHON_ENV = ENV_DIR / ('Scripts/python.exe' if os.name == 'nt' else 'bin/python')
REQUIREMENTS = ROOT / 'requirements-google.txt'


def linha(*parts):
    print(*parts, flush=True)


def executar(cmd, **kwargs):
    linha('>', ' '.join(str(v) for v in cmd[:4]))
    return subprocess.run([str(v) for v in cmd], cwd=str(ROOT), check=False, **kwargs).returncode


def garantir_ambiente():
    if not PYTHON_ENV.exists():
        linha('Criando ambiente Python exclusivo do Dashboard...')
        if executar([sys.executable, '-m', 'venv', str(ENV_DIR)]):
            raise RuntimeError('Nao foi possivel criar o ambiente Python. Verifique a instalacao do Python e a permissao de gravacao na pasta.')
    if not PYTHON_ENV.exists():
        raise RuntimeError('Ambiente criado sem o executavel Python esperado: ' + str(PYTHON_ENV))
    return PYTHON_ENV


def google_importa(py):
    codigo = 'from google.oauth2 import service_account; from google.auth.transport.requests import Request; import requests'
    return subprocess.run([str(py), '-c', codigo], cwd=str(ROOT),
                          stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False).returncode == 0


def garantir_bibliotecas(py, instalar=False):
    if not instalar and google_importa(py):
        linha('Bibliotecas do Google encontradas no ambiente exclusivo do site.')
        return
    linha('Instalando Google Auth e Requests no MESMO Python utilizado pelo site...')
    if executar([py, '-m', 'pip', 'install', '--disable-pip-version-check', '-r', REQUIREMENTS]):
        raise RuntimeError('Falha ao instalar bibliotecas. Verifique a conexao com internet e as mensagens acima.')
    if not google_importa(py):
        raise RuntimeError('Instalacao concluiu mas as bibliotecas nao foram encontradas. Verifique o erro de pip acima.')
    linha('Bibliotecas Google OK.')


def porta_em_uso(porta=8765):
    with socket.socket() as sock:
        sock.settimeout(0.6)
        return sock.connect_ex(('127.0.0.1', porta)) == 0


def iniciar(modo):
    if sys.version_info < (3, 9):
        raise RuntimeError('Python 3.9 ou superior e necessario.')
    if modo == 'iniciar' and porta_em_uso(int(os.environ.get('PORT', '8765'))):
        raise RuntimeError('Ja existe um programa usando http://localhost:8765. Feche a JANELA PRETA do painel antigo (Ctrl+C), feche a aba antiga do navegador e tente novamente. Nao e necessario reiniciar o computador.')
    py = garantir_ambiente()
    linha('Python do dashboard:', py)
    garantir_bibliotecas(py, instalar=(modo == 'configurar'))
    if modo == 'configurar':
        linha('\nConfiguracao concluida. Agora abra TESTAR_CONEXAO_GOOGLE.bat.')
        return 0
    if modo == 'testar':
        linha('\nVerificando acesso a planilha privada...')
        return executar([py, ROOT / 'testar_google.py'])
    if modo == 'iniciar':
        linha('\nIniciando site em http://localhost:8765')
        return executar([py, ROOT / 'app.py'])
    raise RuntimeError('Acao desconhecida: ' + modo)


if __name__ == '__main__':
    try:
        modo = sys.argv[1] if len(sys.argv) > 1 else 'iniciar'
        sys.exit(iniciar(modo))
    except KeyboardInterrupt:
        linha('\nOperacao interrompida.')
        sys.exit(130)
    except Exception as exc:
        linha('\nERRO:', str(exc))
        sys.exit(1)
