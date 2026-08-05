Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$rootDir = Resolve-Path (Join-Path $PSScriptRoot "..")
$backendDir = Join-Path $rootDir "apps\web\backend"
$desktopDir = Join-Path $rootDir "apps\desktop-electron"

Write-Host "=== Starting local dev ===" -ForegroundColor Cyan
Write-Host "[1/2] Backend: uvicorn app.main:app" -ForegroundColor Yellow
Start-Process powershell -ArgumentList @(
    "-NoExit",
    "-Command",
    "Set-Location `"$backendDir`"; python -m uvicorn app.main:app --reload --port 8000"
)

Write-Host "[2/2] Desktop: npm run dev" -ForegroundColor Yellow
Start-Process powershell -ArgumentList @(
    "-NoExit",
    "-Command",
    "Set-Location `"$desktopDir`"; npm run dev"
)

Write-Host "=== Dev servers launched ===" -ForegroundColor Green
