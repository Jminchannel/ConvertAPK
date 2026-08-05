Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$rootDir = Resolve-Path (Join-Path $PSScriptRoot "..")
$backendDir = Join-Path $rootDir "apps\web\backend"
$desktopDir = Join-Path $rootDir "apps\desktop-electron"

Write-Host "=== Starting local dev ===" -ForegroundColor Cyan
Write-Host "[1/2] Backend: python main.py" -ForegroundColor Yellow
Start-Process powershell -ArgumentList @(
    "-NoExit",
    "-Command",
    "Set-Location `"$backendDir`"; python main.py"
)

Write-Host "[2/2] Desktop: npm run dev" -ForegroundColor Yellow
Start-Process powershell -ArgumentList @(
    "-NoExit",
    "-Command",
    "Set-Location `"$desktopDir`"; npm run dev"
)

Write-Host "=== Dev servers launched ===" -ForegroundColor Green
