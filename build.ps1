<#
.SYNOPSIS
    Build completo de Jarvis: Python bridge + Electron UI + Instalador NSIS.
.USAGE
    powershell -ExecutionPolicy Bypass -File build.ps1
#>

$ErrorActionPreference = "Continue"
$ROOT = Split-Path -Parent $MyInvocation.MyCommand.Path

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  JARVIS - Build" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# ---------------------------------------------------------------------------
# 1. Verificar dependencias
# ---------------------------------------------------------------------------
Write-Host "[1/4] Verificando dependencias..." -ForegroundColor Yellow

$pyVer = python --version 2>&1
if ($LASTEXITCODE -ne 0) { Write-Host "  ERROR: Python no encontrado" -ForegroundColor Red; exit 1 }
Write-Host "  Python: $pyVer" -ForegroundColor Green

$piCheck = python -c "import PyInstaller; print(PyInstaller.__version__)" 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host "  Instalando PyInstaller..." -ForegroundColor Yellow
    pip install pyinstaller 2>&1 | Out-Null
}
else { Write-Host "  PyInstaller: $piCheck" -ForegroundColor Green }

$nodeVer = node --version 2>&1
if ($LASTEXITCODE -ne 0) { Write-Host "  ERROR: Node.js no encontrado" -ForegroundColor Red; exit 1 }
Write-Host "  Node.js: $nodeVer" -ForegroundColor Green
Write-Host ""

# ---------------------------------------------------------------------------
# 2. Build Python bridge (PyInstaller)
# ---------------------------------------------------------------------------
Write-Host "[2/4] Construyendo jarvis-bridge.exe..." -ForegroundColor Yellow

Push-Location $ROOT
$env:PYTHONDONTWRITEBYTECODE = "1"
python -m PyInstaller jarvis-bridge.spec --noconfirm --clean 2>&1 | Out-Null
Pop-Location

if (-Not (Test-Path "$ROOT\dist\jarvis-bridge\jarvis-bridge.exe")) {
    Write-Host "  ERROR: jarvis-bridge.exe no se genero" -ForegroundColor Red
    exit 1
}
$bridgeSize = [math]::Round((Get-Item "$ROOT\dist\jarvis-bridge\jarvis-bridge.exe").Length / 1MB, 1)
Write-Host "  jarvis-bridge.exe OK ($bridgeSize MB)" -ForegroundColor Green
Write-Host ""

# ---------------------------------------------------------------------------
# 3. Build UI (Vite + React)
# ---------------------------------------------------------------------------
Write-Host "[3/4] Construyendo UI..." -ForegroundColor Yellow

Push-Location "$ROOT\desktop"
if (-Not (Test-Path "node_modules")) {
    Write-Host "  npm install..." -ForegroundColor DarkGray
    npm install --silent 2>&1 | Out-Null
}
npm run build 2>&1 | Out-Null
Pop-Location

if (-Not (Test-Path "$ROOT\desktop\dist\index.html")) {
    Write-Host "  ERROR: UI build fallo" -ForegroundColor Red
    exit 1
}
Write-Host "  UI build OK" -ForegroundColor Green
Write-Host ""

# ---------------------------------------------------------------------------
# 4. Copiar bridge y empaquetar NSIS
# ---------------------------------------------------------------------------
Write-Host "[4/4] Empaquetando instalador NSIS..." -ForegroundColor Yellow

$bridgeDest = "$ROOT\desktop\bridge-dist"
if (Test-Path $bridgeDest) { Remove-Item $bridgeDest -Recurse -Force }
Copy-Item "$ROOT\dist\jarvis-bridge" $bridgeDest -Recurse
Write-Host "  Bridge copiado a bridge-dist/" -ForegroundColor DarkGray

if (Test-Path "$ROOT\.env") { Copy-Item "$ROOT\.env" "$bridgeDest\.env" }
if (Test-Path "$ROOT\setup.py") { Copy-Item "$ROOT\setup.py" "$bridgeDest\setup.py" }
if (Test-Path "$ROOT\config.py") { Copy-Item "$ROOT\config.py" "$bridgeDest\config.py" }

Push-Location "$ROOT\desktop"
npx electron-builder --win 2>&1 | Out-Null
Pop-Location

$installer = Get-ChildItem "$ROOT\desktop\release\*.exe" -ErrorAction SilentlyContinue | Select-Object -First 1
if ($installer) {
    $installerSize = [math]::Round($installer.Length / 1MB, 1)
    Write-Host ""
    Write-Host "========================================" -ForegroundColor Green
    Write-Host "  BUILD COMPLETO" -ForegroundColor Green
    Write-Host "  $($installer.Name)" -ForegroundColor Green
    Write-Host "  Tamano: $installerSize MB" -ForegroundColor Green
    Write-Host "  Ruta: $($installer.FullName)" -ForegroundColor Green
    Write-Host "========================================" -ForegroundColor Green
} else {
    Write-Host "  ERROR: Instalador no generado. Revisa desktop/release/" -ForegroundColor Red
    exit 1
}
Write-Host ""
