Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

Write-Host "[0/3] Prepare build environment (developer machine)"

function Stop-AppProcess {
  param(
    [Parameter(Mandatory = $true)]
    [string[]]$Names
  )
  foreach ($name in $Names) {
    $procs = Get-Process -Name $name -ErrorAction SilentlyContinue
    if ($procs) {
      Write-Host "Stopping running process: $name"
      $procs | Stop-Process -Force
      Start-Sleep -Milliseconds 500
    }
  }
}

function Ensure-EmptyDir {
  param(
    [Parameter(Mandatory = $true)]
    [string]$Path
  )
  if (-not (Test-Path $Path)) {
    return
  }
  $retries = 5
  for ($i = 1; $i -le $retries; $i++) {
    try {
      Remove-Item -Recurse -Force -ErrorAction Stop $Path
      return
    } catch {
      if ($i -eq $retries) {
        throw
      }
      Write-Host "Retrying remove $Path ($i/$retries) ..."
      Start-Sleep -Milliseconds 800
    }
  }
}

Write-Host "[1/3] Build frontend"
Push-Location (Join-Path $PSScriptRoot "..\\apps\\web\\frontend")
if (-not (Test-Path "node_modules")) { npm install }
npm run build
Pop-Location

Write-Host "[2/3] Build backend exe"
$backendDir = Join-Path $PSScriptRoot "..\\apps\\web\\backend"
python -m pip install -r (Join-Path $PSScriptRoot "..\\apps\\web\\backend\\requirements.txt")
python -m pip install pyinstaller
$specPath = Join-Path $PSScriptRoot "convertapk-backend.spec"
pyinstaller --noconfirm --clean `
  --distpath (Join-Path $PSScriptRoot "..\\artifacts\\backend") `
  --workpath (Join-Path $PSScriptRoot "..\\artifacts\\build\\backend") `
  $specPath
if ($LASTEXITCODE -ne 0) {
    throw "PyInstaller failed with exit code $LASTEXITCODE"
}

Write-Host "[3/3] Build Electron installer"
Push-Location (Join-Path $PSScriptRoot "..\\apps\\desktop-electron")
if (-not (Test-Path "node_modules")) { npm install }
Stop-AppProcess -Names @("ConvertAPK", "convertapk")
Ensure-EmptyDir -Path (Join-Path (Get-Location) "dist\\win-unpacked")
npm run dist
Pop-Location
