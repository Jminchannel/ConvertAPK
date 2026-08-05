Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$backendDir = Join-Path $PSScriptRoot "..\apps\web\backend"
$distDir = Join-Path $PSScriptRoot "..\artifacts\backend"

Write-Host "=== Building Backend EXE ===" -ForegroundColor Cyan

# Install dependencies
Write-Host "[1/3] Installing Python dependencies..."
python -m pip install -r (Join-Path $backendDir "requirements.txt")
python -m pip install pyinstaller

# Build with PyInstaller
Write-Host "[2/3] Building EXE with PyInstaller..."
$specPath = Join-Path $PSScriptRoot "convertapk-backend.spec"
pyinstaller --noconfirm --clean `
  --distpath $distDir `
  --workpath (Join-Path $PSScriptRoot "..\artifacts\build\backend") `
  $specPath
if ($LASTEXITCODE -ne 0) {
    throw "PyInstaller failed with exit code $LASTEXITCODE"
}

# Electron 构建会从 artifacts/backend 自动打包后端程序。
Write-Host "[3/3] Backend artifact ready for Electron packaging."

Write-Host "=== Build Complete ===" -ForegroundColor Green
Write-Host "EXE location: $distDir\convertapk-backend.exe"



