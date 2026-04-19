$ErrorActionPreference = "Continue"
# $ROOT: raiz del proyecto (carpeta donde vive este script).
# $BUILD: directorio donde caen TODOS los outputs del build (PyInstaller,
#         bridge-dist, cache de electron-builder, release NSIS, TEMP).
# Por defecto usa D:\jarvis-build porque en C: normalmente no hay espacio.
# Sobrescribible via: $env:JARVIS_BUILD_DIR = "ruta\alternativa"
$ROOT = Split-Path -Parent $MyInvocation.MyCommand.Path
$BUILD = if ($env:JARVIS_BUILD_DIR) { $env:JARVIS_BUILD_DIR } else { "D:\jarvis-build" }

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  JARVIS - Build (salida -> D:)" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# ---------------------------------------------------------------------------
# Cleanup de artefactos parciales en C:
# ---------------------------------------------------------------------------
Write-Host "[0/4] Limpiando artefactos parciales en C:..." -ForegroundColor Yellow
foreach ($p in @("$ROOT\dist", "$ROOT\build", "$ROOT\desktop\bridge-dist", "$ROOT\desktop\release")) {
    if (Test-Path $p) {
        $item = Get-Item $p -Force
        if ($item.Attributes -match "ReparsePoint") {
            cmd /c rmdir "$p" 2>$null | Out-Null
        } else {
            Remove-Item $p -Recurse -Force -ErrorAction SilentlyContinue
        }
    }
}

# ---------------------------------------------------------------------------
# Preparar carpetas destino en D:
# ---------------------------------------------------------------------------
Write-Host "[0/4] Preparando carpetas en $BUILD ..." -ForegroundColor Yellow
New-Item -ItemType Directory -Force "$BUILD\dist"            | Out-Null
New-Item -ItemType Directory -Force "$BUILD\build-py"        | Out-Null
New-Item -ItemType Directory -Force "$BUILD\bridge-dist"     | Out-Null
New-Item -ItemType Directory -Force "$BUILD\release"         | Out-Null
New-Item -ItemType Directory -Force "$BUILD\cache-eb"        | Out-Null
New-Item -ItemType Directory -Force "$BUILD\cache-electron"  | Out-Null
New-Item -ItemType Directory -Force "$BUILD\tmp"             | Out-Null

# Redirigir cachés y TEMP a D:
$env:ELECTRON_BUILDER_CACHE = "$BUILD\cache-eb"
$env:ELECTRON_CACHE         = "$BUILD\cache-electron"
$env:TEMP                   = "$BUILD\tmp"
$env:TMP                    = "$BUILD\tmp"
$env:PYTHONDONTWRITEBYTECODE = "1"

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
} else { Write-Host "  PyInstaller: $piCheck" -ForegroundColor Green }

$nodeVer = node --version 2>&1
if ($LASTEXITCODE -ne 0) { Write-Host "  ERROR: Node.js no encontrado" -ForegroundColor Red; exit 1 }
Write-Host "  Node.js: $nodeVer" -ForegroundColor Green
Write-Host ""

# ---------------------------------------------------------------------------
# 2. Build Python bridge (PyInstaller) -> D:\jarvis-build\dist
# ---------------------------------------------------------------------------
Write-Host "[2/4] Construyendo jarvis-bridge.exe en D: ..." -ForegroundColor Yellow

Push-Location $ROOT
python -m PyInstaller jarvis-bridge.spec --noconfirm --clean --distpath "$BUILD\dist" --workpath "$BUILD\build-py" 2>&1 | Out-Null
Pop-Location

if (-Not (Test-Path "$BUILD\dist\jarvis-bridge\jarvis-bridge.exe")) {
    Write-Host "  ERROR: jarvis-bridge.exe no se genero" -ForegroundColor Red
    exit 1
}
$bridgeSize = [math]::Round((Get-Item "$BUILD\dist\jarvis-bridge\jarvis-bridge.exe").Length / 1MB, 1)
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
# 4. Copiar bridge a D:, junction en desktop\bridge-dist, y empaquetar NSIS
# ---------------------------------------------------------------------------
Write-Host "[4/4] Empaquetando instalador NSIS (salida en D:)..." -ForegroundColor Yellow

# Limpiar contenido previo de D:\jarvis-build\bridge-dist
Get-ChildItem "$BUILD\bridge-dist" -Force -ErrorAction SilentlyContinue | Remove-Item -Recurse -Force -ErrorAction SilentlyContinue

# Copiar bridge al destino en D:
Copy-Item "$BUILD\dist\jarvis-bridge\*" "$BUILD\bridge-dist" -Recurse -Force
Write-Host "  Bridge copiado a $BUILD\bridge-dist" -ForegroundColor DarkGray

# NO copiar .env al bundle (contiene credenciales del dev).
# El Setup Wizard lo genera por usuario en %APPDATA%\Jarvis\.env al instalar.
if (Test-Path "$ROOT\setup.py")  { Copy-Item "$ROOT\setup.py"  "$BUILD\bridge-dist\setup.py" }
if (Test-Path "$ROOT\config.py") { Copy-Item "$ROOT\config.py" "$BUILD\bridge-dist\config.py" }

# Junction desktop\bridge-dist -> D:\jarvis-build\bridge-dist
# (electron-builder usa la ruta relativa "bridge-dist" en package.json)
if (Test-Path "$ROOT\desktop\bridge-dist") {
    $item = Get-Item "$ROOT\desktop\bridge-dist" -Force
    if ($item.Attributes -match "ReparsePoint") {
        cmd /c rmdir "$ROOT\desktop\bridge-dist" 2>$null | Out-Null
    } else {
        Remove-Item "$ROOT\desktop\bridge-dist" -Recurse -Force
    }
}
cmd /c mklink /J "$ROOT\desktop\bridge-dist" "$BUILD\bridge-dist" | Out-Null
Write-Host "  Junction desktop\bridge-dist -> $BUILD\bridge-dist" -ForegroundColor DarkGray

Push-Location "$ROOT\desktop"
npx electron-builder --win --config.directories.output="$BUILD\release" 2>&1 | Out-Null

# electron-builder ignora nuestro icon.ico multi-tamano y deja el default de Electron
# (solo 4 frames). Parcheamos Jarvis.exe con rcedit e insertamos los 10 frames reales.
# NOTA: NO aplicar rcedit a jarvis-bridge.exe (rompe el bundle PyInstaller).
$rcedit = "$ROOT\desktop\node_modules\rcedit\bin\rcedit-x64.exe"
$iconSrc = "$ROOT\desktop\assets\icon.ico"
$jarvisExe = "$BUILD\release\win-unpacked\Jarvis.exe"
if ((Test-Path $rcedit) -and (Test-Path $jarvisExe)) {
    & $rcedit $jarvisExe --set-icon $iconSrc 2>&1 | Out-Null
    Write-Host "  Icono aplicado a Jarvis.exe con rcedit" -ForegroundColor DarkGray
} else {
    Write-Host "  [warn] rcedit no disponible; instalandolo..." -ForegroundColor Yellow
    npm install --no-save --silent rcedit 2>&1 | Out-Null
    if (Test-Path $rcedit) {
        & $rcedit $jarvisExe --set-icon $iconSrc 2>&1 | Out-Null
        Write-Host "  Icono aplicado a Jarvis.exe (post-install rcedit)" -ForegroundColor DarkGray
    }
}

# Regenerar NSIS desde el win-unpacked ya parcheado (el .exe del installer anterior
# trae el Jarvis.exe con ícono default — hay que rehacer el NSIS para que use
# nuestro Jarvis.exe con los 10 frames correctos).
Get-ChildItem "$BUILD\release" -Filter "*.exe" -File | Where-Object { $_.Name -notlike "*Uninstall*" } | Remove-Item -Force
Get-ChildItem "$BUILD\release" -Filter "*.blockmap" -File | Remove-Item -Force
npx electron-builder --win --prepackaged "$BUILD\release\win-unpacked" --config.directories.output="$BUILD\release" 2>&1 | Out-Null
Pop-Location

$installer = Get-ChildItem "$BUILD\release\*.exe" -ErrorAction SilentlyContinue | Where-Object { $_.Name -notlike "*Uninstall*" } | Select-Object -First 1
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
    Write-Host "  ERROR: Instalador no generado. Revisa $BUILD\release\" -ForegroundColor Red
    exit 1
}
Write-Host ""
