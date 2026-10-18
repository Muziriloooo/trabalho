# Executar no PowerShell: .\scripts\start-windows.ps1
$ErrorActionPreference = 'Stop'
Set-Location (Split-Path $PSScriptRoot -Parent)

function Invoke-Checked {
    param([string]$Program, [string[]]$Arguments)
    & $Program @Arguments
    if ($LASTEXITCODE -ne 0) { throw "Falha ao executar $Program (codigo $LASTEXITCODE)." }
}

if (-not (Test-Path '.venv\Scripts\python.exe')) {
    Invoke-Checked -Program 'py' -Arguments @('-3.12', '-m', 'venv', '.venv')
}
$Python = Join-Path (Get-Location) '.venv\Scripts\python.exe'
Invoke-Checked -Program $Python -Arguments @('scripts/check_python.py')
Invoke-Checked -Program $Python -Arguments @('-m', 'pip', 'install', '--only-binary=:all:', '-r', 'requirements.lock.txt')
Invoke-Checked -Program $Python -Arguments @('-m', 'pip', 'check')
Invoke-Checked -Program $Python -Arguments @('-m', 'flask', '--app', 'app', 'db', 'upgrade')
Invoke-Checked -Program $Python -Arguments @('-m', 'flask', '--app', 'app', 'setup-local')
Write-Host 'Console local na porta 5000. Abra o navegador apos o servidor iniciar. Ctrl+C encerra.'
Invoke-Checked -Program '.venv\Scripts\waitress-serve.exe' -Arguments @('--listen=127.0.0.1:5000', 'app:app')
