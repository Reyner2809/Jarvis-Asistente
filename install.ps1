# ============================================================================
# JARVIS - Instalador automatico
# Uso: irm https://raw.githubusercontent.com/Reyner2809/Jarvis-Asistente/main/install.ps1 | iex
# ============================================================================

try {

[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

function Write-Color($color, $text) {
    Write-Host $text -ForegroundColor $color
}

function Write-Banner {
    Write-Host ""
    Write-Color Cyan "       JARVIS - Asistente de IA Personal"
    Write-Color Cyan "       ================================="
    Write-Host ""
    Write-Color White "       Instalador automatico"
    Write-Host ""
}

function Test-Cmd($name) {
    $null -ne (Get-Command $name -ErrorAction SilentlyContinue)
}

# --- INICIO ---
Clear-Host
Write-Banner

Write-Color White "  Bienvenido! Este script instalara JARVIS en tu PC."
Write-Color Gray "  Solo necesitas seguir las instrucciones."
Write-Host ""
Write-Color Cyan "  =================================================="
Write-Host ""

# --- Verificar Python ---
Write-Color Yellow "  Verificando Python..."
if (Test-Cmd "python") {
    $pyVer = & python --version 2>&1
    Write-Color Green "  OK: $pyVer detectado"
} else {
    Write-Color Red "  ERROR: Python no esta instalado."
    Write-Host ""
    Write-Color White "  Para instalar Python:"
    Write-Color Cyan "  1. Ve a https://www.python.org/downloads/"
    Write-Color Cyan "  2. Descarga Python 3.10 o superior"
    Write-Color Cyan "  3. IMPORTANTE: Marca la casilla 'Add Python to PATH'"
    Write-Color Cyan "  4. Instala y vuelve a ejecutar este script"
    Write-Host ""
    Start-Process "https://www.python.org/downloads/"
    Write-Host ""
    Read-Host "  Presiona Enter para cerrar"
    return
}

# --- Verificar Git ---
Write-Color Yellow "  Verificando Git..."
if (Test-Cmd "git") {
    Write-Color Green "  OK: Git detectado"
} else {
    Write-Color Yellow "  Git no esta instalado. Intentando instalar con winget..."
    & winget install Git.Git --accept-source-agreements --accept-package-agreements 2>&1 | Out-Null
    # Agregar al PATH de esta sesion
    $env:PATH += ";C:\Program Files\Git\cmd"
    if (Test-Cmd "git") {
        Write-Color Green "  OK: Git instalado"
    } else {
        Write-Color Red "  ERROR: No pude instalar Git."
        Write-Color White "  Descarga Git de: https://git-scm.com/download/win"
        Write-Color Yellow "  Despues de instalar, ejecuta este script de nuevo."
        Write-Host ""
        Read-Host "  Presiona Enter para cerrar"
        return
    }
}

# --- Clonar repositorio ---
Write-Host ""
Write-Color Cyan "  =================================================="
Write-Color White "  Descargando JARVIS..."
Write-Color Cyan "  =================================================="
Write-Host ""

$installDir = "$env:USERPROFILE\Jarvis-Asistente"

if (Test-Path $installDir) {
    Write-Color Yellow "  Jarvis ya existe en $installDir"
    $update = Read-Host "  Actualizar? (S/n)"
    if ($update -eq "" -or $update -match "^[sS]") {
        Set-Location $installDir
        & git pull origin main 2>&1 | Out-Null
        Write-Color Green "  OK: Actualizado"
    }
} else {
    Write-Color Gray "  Clonando repositorio..."
    & git clone "https://github.com/Reyner2809/Jarvis-Asistente.git" "$installDir" 2>&1 | Out-Null
    if (Test-Path "$installDir\main.py") {
        Write-Color Green "  OK: Descargado en $installDir"
    } else {
        Write-Color Red "  ERROR: No se pudo descargar. Verifica tu conexion a internet."
        Write-Host ""
        Read-Host "  Presiona Enter para cerrar"
        return
    }
}

# --- Ejecutar wizard ---
Write-Host ""
Write-Color Cyan "  =================================================="
Write-Color White "  Iniciando configuracion..."
Write-Color Cyan "  =================================================="
Write-Host ""

Set-Location $installDir
& python setup.py

} catch {
    Write-Host ""
    Write-Color Red "  ERROR: $_"
    Write-Host ""
    Read-Host "  Presiona Enter para cerrar"
}
