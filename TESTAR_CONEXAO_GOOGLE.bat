@echo off
chcp 65001 >nul
cd /d "%~dp0"
title Implantacoes 2026 - TESTAR
set "PYTHON_CMD="
py -3 -c "import sys;sys.exit(0 if sys.version_info >= (3,9) else 1)" >nul 2>&1
if not errorlevel 1 set "PYTHON_CMD=py -3"
if not defined PYTHON_CMD (
  python -c "import sys;sys.exit(0 if sys.version_info >= (3,9) else 1)" >nul 2>&1
  if not errorlevel 1 set "PYTHON_CMD=python"
)
if not defined PYTHON_CMD (
  echo ERRO: Python 3.9 ou superior nao encontrado.
  echo Instale em https://www.python.org/downloads/windows/
  pause
  exit /b 1
)
%PYTHON_CMD% launcher_google.py testar
set "RESULTADO=%ERRORLEVEL%"
if not "%RESULTADO%"=="0" (
  echo.
  echo A operacao nao foi concluida. Confira a mensagem acima.
)
echo.
pause
exit /b %RESULTADO%
