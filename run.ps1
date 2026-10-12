# Andon Assistant - one-command launcher (Windows PowerShell).
# Starts the backend + frontend in their own windows and opens the dashboard.
# First time on a machine? Run .\setup.ps1 once before this.
$root = $PSScriptRoot
Write-Host "Starting Andon Assistant..." -ForegroundColor Cyan

# Backend - FastAPI on http://localhost:8080
Start-Process powershell -ArgumentList @(
  "-NoExit","-Command",
  "cd '$root\backend'; `$env:APP_CORS_ORIGINS='*'; .\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8080"
)

# Frontend - Next.js dashboard on http://localhost:3000
Start-Process powershell -ArgumentList @(
  "-NoExit","-Command",
  "cd '$root\frontend'; npm run dev"
)

Write-Host "Waiting for the dashboard to come up..." -ForegroundColor Cyan
Start-Sleep -Seconds 7
Start-Process "http://localhost:3000"
Write-Host "Opened http://localhost:3000 - click 'Keys', paste your API key, and start chatting." -ForegroundColor Green
Write-Host "To stop: close the two PowerShell windows this opened." -ForegroundColor DarkGray
