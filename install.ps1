# ============================================================================
# JARVIS — Instalador automatico
# Uso: irm https://raw.githubusercontent.com/Reyner2809/Jarvis-Asistente/main/install.ps1 | iex
# ============================================================================

$ErrorActionPreference = "Stop"

function Write-Color($color, $text) {
    Write-Host $text -ForegroundColor $color
}

function Write-Banner {
    Write-Host ""
    Write-Color Cyan "       ██╗ █████╗ ██████╗ ██╗   ██╗██╗███████╗"
    Write-Color Cyan "       ██║██╔══██╗██╔══██╗██║   ██║██║██╔════╝"
    Write-Color Cyan "       ██║███████║██████╔╝██║   ██║██║███████╗"
    Write-Color Cyan "  ██   ██║██╔══██║██╔══██╗╚██╗ ██╔╝██║╚════██║"
    Write-Color Cyan "  ╚█████╔╝██║  ██║██║  ██║ ╚████╔╝ ██║███████║"
    Write-Color Cyan "   ╚════╝ ╚═╝  ╚═╝╚═╝  ╚═╝  ╚═══╝  ╚═╝╚══════╝"
    Write-Host ""
    Write-Color White "       Asistente de IA Personal — Instalador"
    Write-Host ""
}

function Test-Command($cmd) {
    try { Get-Command $cmd -ErrorAction SilentlyContinue | Out-Null; return $true }
    catch { return $false }
}

# --- INICIO ---
Clear-Host
Write-Banner

Write-Color White "  Bienvenido! Este script instalara JARVIS en tu PC."
Write-Color Gray "  Solo necesitas seguir las instrucciones."
Write-Host ""
Write-Color Cyan "  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
Write-Host ""

# --- Verificar Python ---
Write-Color Yellow "  Verificando Python..."
if (Test-Command "python") {
    $pyVer = python --version 2>&1
    Write-Color Green "  ✅ $pyVer detectado"
} else {
    Write-Color Red "  ❌ Python no esta instalado."
    Write-Host ""
    Write-Color White "  Para instalar Python:"
    Write-Color Cyan "  1. Ve a https://www.python.org/downloads/"
    Write-Color Cyan "  2. Descarga Python 3.10 o superior"
    Write-Color Cyan "  3. IMPORTANTE: Marca la casilla 'Add Python to PATH'"
    Write-Color Cyan "  4. Instala y vuelve a ejecutar este script"
    Write-Host ""
    Write-Color Yellow "  Presiona Enter para abrir la pagina de descarga..."
    Read-Host
    Start-Process "https://www.python.org/downloads/"
    exit 1
}

# --- Verificar Git ---
Write-Color Yellow "  Verificando Git..."
if (Test-Command "git") {
    Write-Color Green "  ✅ Git detectado"
} else {
    Write-Color Yellow "  ⚠️  Git no esta instalado. Instalando..."
    try {
        winget install Git.Git --accept-source-agreements --accept-package-agreements 2>&1 | Out-Null
        $env:PATH += ";C:\Program Files\Git\cmd"
        Write-Color Green "  ✅ Git instalado"
    } catch {
        Write-Color Red "  ❌ No pude instalar Git automaticamente."
        Write-Color White "  Descarga Git de: https://git-scm.com/download/win"
        Write-Color Yellow "  Despues de instalar, ejecuta este script de nuevo."
        exit 1
    }
}

# --- Clonar repositorio ---
Write-Host ""
Write-Color Cyan "  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
Write-Color White "  Descargando JARVIS..."
Write-Color Cyan "  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
Write-Host ""

$installDir = "$env:USERPROFILE\Jarvis-Asistente"

if (Test-Path $installDir) {
    Write-Color Yellow "  Jarvis ya existe en $installDir"
    $update = Read-Host "  ¿Actualizar? (S/n)"
    if ($update -eq "" -or $update -match "^[sS]") {
        Set-Location $installDir
        $env:GIT_REDIRECT_STDERR = '2>&1'
        git pull origin main 2>$null
        Write-Color Green "  ✅ Actualizado"
    }
} else {
    $env:GIT_REDIRECT_STDERR = '2>&1'
    git clone https://github.com/Reyner2809/Jarvis-Asistente.git $installDir 2>$null
    if (Test-Path "$installDir\main.py") {
        Write-Color Green "  ✅ Descargado en $installDir"
    } else {
        Write-Color Red "  ❌ Error descargando. Verifica tu conexion a internet."
        exit 1
    }
}

# --- Ejecutar wizard ---
Write-Host ""
Write-Color Cyan "  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
Write-Color White "  Iniciando configuracion..."
Write-Color Cyan "  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
Write-Host ""

Set-Location $installDir
python setup.py
