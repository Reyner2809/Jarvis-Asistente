# ============================================================================
# JARVIS - Instalador automatico
# ============================================================================

[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$ErrorActionPreference = "Continue"

Clear-Host
Write-Host ""
Write-Host "       JARVIS - Asistente de IA Personal" -ForegroundColor Cyan
Write-Host "       =================================" -ForegroundColor Cyan
Write-Host "       Instalador automatico" -ForegroundColor White
Write-Host ""
Write-Host "  ==================================================" -ForegroundColor Cyan
Write-Host ""

# --- Verificar Python ---
Write-Host "  Verificando Python..." -ForegroundColor Yellow
$pyCmd = Get-Command python -ErrorAction SilentlyContinue
if ($pyCmd) {
    $pyVer = & python --version 2>&1
    Write-Host "  OK: $pyVer" -ForegroundColor Green
} else {
    Write-Host "  Python no esta instalado." -ForegroundColor Red
    Write-Host ""
    Write-Host "  Para instalar Python:" -ForegroundColor White
    Write-Host "  1. Ve a https://www.python.org/downloads/" -ForegroundColor Cyan
    Write-Host "  2. Descarga Python 3.10 o superior" -ForegroundColor Cyan
    Write-Host "  3. IMPORTANTE: Marca 'Add Python to PATH'" -ForegroundColor Cyan
    Write-Host "  4. Instala y vuelve a ejecutar este script" -ForegroundColor Cyan
    Write-Host ""
    Start-Process "https://www.python.org/downloads/"
    Read-Host "  Presiona Enter para cerrar"
    return
}

# --- Verificar Git ---
Write-Host "  Verificando Git..." -ForegroundColor Yellow
$gitCmd = Get-Command git -ErrorAction SilentlyContinue
if ($gitCmd) {
    Write-Host "  OK: Git detectado" -ForegroundColor Green
} else {
    Write-Host "  Git no encontrado. Instalando con winget..." -ForegroundColor Yellow
    & winget install Git.Git --accept-source-agreements --accept-package-agreements 2>&1 | Out-Null
    $env:PATH += ";C:\Program Files\Git\cmd"
    $gitCmd2 = Get-Command git -ErrorAction SilentlyContinue
    if ($gitCmd2) {
        Write-Host "  OK: Git instalado" -ForegroundColor Green
    } else {
        Write-Host "  No pude instalar Git." -ForegroundColor Red
        Write-Host "  Descarga de: https://git-scm.com/download/win" -ForegroundColor White
        Read-Host "  Presiona Enter para cerrar"
        return
    }
}

# --- Clonar repositorio ---
Write-Host ""
Write-Host "  ==================================================" -ForegroundColor Cyan
Write-Host "  Descargando JARVIS..." -ForegroundColor White
Write-Host "  ==================================================" -ForegroundColor Cyan
Write-Host ""

$installDir = Join-Path $env:USERPROFILE "Jarvis-Asistente"

if (Test-Path $installDir) {
    Write-Host "  Jarvis ya existe en $installDir" -ForegroundColor Yellow
    $update = Read-Host "  Actualizar? (S/n)"
    if ($update -eq "" -or $update -match "^[sS]") {
        Set-Location $installDir
        & git pull origin main 2>&1 | Out-Null
        Write-Host "  OK: Actualizado" -ForegroundColor Green
    }
} else {
    Write-Host "  Clonando repositorio..." -ForegroundColor Gray
    & git clone "https://github.com/Reyner2809/Jarvis-Asistente.git" "$installDir" 2>&1 | Out-Null
    if (Test-Path (Join-Path $installDir "main.py")) {
        Write-Host "  OK: Descargado en $installDir" -ForegroundColor Green
    } else {
        Write-Host "  Error descargando. Verifica tu internet." -ForegroundColor Red
        Read-Host "  Presiona Enter para cerrar"
        return
    }
}

# --- Ejecutar wizard ---
Write-Host ""
Write-Host "  ==================================================" -ForegroundColor Cyan
Write-Host "  Iniciando configuracion..." -ForegroundColor White
Write-Host "  ==================================================" -ForegroundColor Cyan
Write-Host ""

Set-Location $installDir
& python setup.py

Read-Host "  Presiona Enter para cerrar"
