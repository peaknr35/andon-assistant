# Andon Assistant - one-time setup (Windows PowerShell). Run once per machine.
# Creates the Python venv, installs backend + frontend deps, makes a .env, seeds demo data.
$ErrorActionPreference = "Stop"
$root = $PSScriptRoot

Write-Host "== 1/4  Backend: Python virtual env + dependencies ==" -ForegroundColor Cyan
Set-Location "$root\backend"
if (-not (Test-Path ".venv")) { python -m venv .venv }
.\.venv\Scripts\python.exe -m pip install --upgrade pip | Out-Null
.\.venv\Scripts\python.exe -m pip install -r requirements.txt

Write-Host "== 2/4  Config: backend\.env ==" -ForegroundColor Cyan
if (-not (Test-Path ".env")) {
  Copy-Item ".env.example" ".env"
  Write-Host "   Created backend\.env - open it and paste your API key into APP_API_KEY." -ForegroundColor Yellow
} else {
  Write-Host "   backend\.env already exists - leaving it as is." -ForegroundColor DarkGray
}

Write-Host "== 3/4  Frontend: npm install ==" -ForegroundColor Cyan
Set-Location "$root\frontend"
npm install

Write-Host "== 4/4  Seed demo memory (optional sample fixes + PM events) ==" -ForegroundColor Cyan
Set-Location "$root\backend"
$env:PYTHONPATH = "."
.\.venv\Scripts\python.exe scripts\seed_demo.py

Set-Location $root
Write-Host ""
Write-Host "Setup complete. Add your key to backend\.env (or paste it in the browser), then run:  .\run.ps1" -ForegroundColor Green
