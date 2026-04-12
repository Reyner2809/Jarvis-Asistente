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

# --- Verificar Python (real, no el alias de Microsoft Store) ---
Write-Host "  Verificando Python..." -ForegroundColor Yellow
$pythonOK = $false
try {
    $pyVer = & python --version 2>&1
    if ($pyVer -match "Python \d+\.\d+") {
        Write-Host "  OK: $pyVer" -ForegroundColor Green
        $pythonOK = $true
    }
} catch {}

if (-not $pythonOK) {
    Write-Host "  Python no esta instalado. Instalando automaticamente..." -ForegroundColor Yellow
    Write-Host ""

    # Desactivar alias de Microsoft Store que interfiere
    try {
        $aliases = @("python.exe", "python3.exe")
        foreach ($a in $aliases) {
            $aliasPath = Join-Path $env:LOCALAPPDATA "Microsoft\WindowsApps\$a"
            if (Test-Path $aliasPath) {
                Remove-Item $aliasPath -Force -ErrorAction SilentlyContinue
            }
        }
    } catch {}

    # Intentar con winget primero
    $wingetOK = Get-Command winget -ErrorAction SilentlyContinue
    if ($wingetOK) {
        Write-Host "  Instalando Python con winget (esto puede tardar unos minutos)..." -ForegroundColor Cyan
        & winget install Python.Python.3.11 --accept-source-agreements --accept-package-agreements --silent --disable-interactivity 2>&1 | Out-Null

        # Actualizar PATH de esta sesion
        $userPath = [Environment]::GetEnvironmentVariable("Path", "User")
        $machinePath = [Environment]::GetEnvironmentVariable("Path", "Machine")
        $env:PATH = "$machinePath;$userPath"

        # Verificar de nuevo
        try {
            $pyVer = & python --version 2>&1
            if ($pyVer -match "Python \d+\.\d+") {
                Write-Host "  OK: $pyVer instalado correctamente" -ForegroundColor Green
                $pythonOK = $true
            }
        } catch {}
    }

    if (-not $pythonOK) {
        # Intentar descarga directa
        Write-Host "  Descargando Python desde python.org..." -ForegroundColor Cyan
        $pyInstaller = Join-Path $env:TEMP "python_installer.exe"
        try {
            Invoke-WebRequest -Uri "https://www.python.org/ftp/python/3.11.9/python-3.11.9-amd64.exe" -OutFile $pyInstaller -UseBasicParsing
            Write-Host "  Ejecutando instalador (esto tarda 1-2 minutos)..." -ForegroundColor Cyan
            & $pyInstaller /quiet InstallAllUsers=0 PrependPath=1 Include_test=0 2>&1 | Out-Null
            Start-Sleep -Seconds 5

            # Actualizar PATH
            $userPath = [Environment]::GetEnvironmentVariable("Path", "User")
            $machinePath = [Environment]::GetEnvironmentVariable("Path", "Machine")
            $env:PATH = "$machinePath;$userPath"

            try {
                $pyVer = & python --version 2>&1
                if ($pyVer -match "Python \d+\.\d+") {
                    Write-Host "  OK: $pyVer instalado correctamente" -ForegroundColor Green
                    $pythonOK = $true
                }
            } catch {}
        } catch {
            Write-Host "  Error descargando Python: $_" -ForegroundColor Red
        }
        Remove-Item $pyInstaller -Force -ErrorAction SilentlyContinue
    }

    if (-not $pythonOK) {
        Write-Host ""
        Write-Host "  No pude instalar Python automaticamente." -ForegroundColor Red
        Write-Host "  Instala Python manualmente desde https://www.python.org/downloads/" -ForegroundColor White
        Write-Host "  IMPORTANTE: Marca 'Add Python to PATH' en el instalador." -ForegroundColor Yellow
        Write-Host "  Despues cierra esta ventana y ejecuta el comando de nuevo." -ForegroundColor Cyan
        Write-Host ""
        Start-Process "https://www.python.org/downloads/"
        Read-Host "  Presiona Enter para cerrar"
        return
    }
}

# --- Verificar Git ---
Write-Host "  Verificando Git..." -ForegroundColor Yellow
$gitCmd = Get-Command git -ErrorAction SilentlyContinue
if ($gitCmd) {
    Write-Host "  OK: Git detectado" -ForegroundColor Green
} else {
    Write-Host "  Git no encontrado. Instalando con winget..." -ForegroundColor Yellow
    & winget install Git.Git --accept-source-agreements --accept-package-agreements --silent --disable-interactivity 2>&1 | Out-Null
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
