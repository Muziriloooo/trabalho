@echo off
setlocal
title SENTINELA AI
cd /d "%~dp0"
if errorlevel 1 goto erro_pasta

echo ========================================
echo          SENTINELA AI - INICIAR
echo ========================================
echo.

if not exist "app.py" goto erro_pasta
if not exist "requirements.lock.txt" goto erro_pasta
if not exist "scripts\start_local.py" goto erro_pasta

if exist ".venv\Scripts\python.exe" goto instalar
echo Criando o ambiente Python 3.12...
where py >nul 2>nul
if errorlevel 1 goto erro_python
py -3.12 -m venv ".venv"
if errorlevel 1 goto erro_python

:instalar
echo Conferindo e instalando dependencias...
".venv\Scripts\python.exe" -m pip install -r "requirements.lock.txt"
if errorlevel 1 goto erro
".venv\Scripts\python.exe" -m pip check
if errorlevel 1 goto erro

echo Atualizando o banco sem apagar seus cadastros...
".venv\Scripts\python.exe" -m flask --app app db upgrade
if errorlevel 1 goto erro

echo.
echo Primeiro acesso: informe e-mail e senha se forem solicitados.
echo A senha fica invisivel enquanto voce digita. Confirme com Enter.
".venv\Scripts\python.exe" -m flask --app app setup-local
if errorlevel 1 goto erro

echo.
".venv\Scripts\python.exe" "scripts\start_local.py"
if errorlevel 1 goto erro
echo.
echo Servidor encerrado.
pause
exit /b 0

:erro_python
echo.
echo Nao foi possivel criar o ambiente Python.
echo Instale o Python 3.12 com o launcher py e tente novamente.
goto erro

:erro_pasta
echo.
echo Coloque iniciar.bat na raiz do projeto, junto de app.py,
echo requirements.lock.txt e da pasta scripts completa.
goto erro

:erro
echo.
echo A inicializacao foi interrompida. Seus cadastros foram preservados.
echo Copie a mensagem de erro acima para solicitar ajuda.
pause
exit /b 1
