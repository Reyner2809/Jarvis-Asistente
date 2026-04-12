#!/usr/bin/env python3
"""
JARVIS — Asistente de IA Personal
Wizard de instalacion y configuracion.

Uso: python setup.py
"""

import os
import sys
import subprocess
import shutil
import time
import json

# ---------------------------------------------------------------------------
# Colores y utilidades de terminal
# ---------------------------------------------------------------------------

class Colors:
    CYAN = "\033[96m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    RED = "\033[91m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    RESET = "\033[0m"
    MAGENTA = "\033[95m"
    WHITE = "\033[97m"

C = Colors

def clear():
    os.system("cls" if os.name == "nt" else "clear")

def print_banner():
    banner = f"""
{C.CYAN}{C.BOLD}
       ██╗ █████╗ ██████╗ ██╗   ██╗██╗███████╗
       ██║██╔══██╗██╔══██╗██║   ██║██║██╔════╝
       ██║███████║██████╔╝██║   ██║██║███████╗
  ██   ██║██╔══██║██╔══██╗╚██╗ ██╔╝██║╚════██║
  ╚█████╔╝██║  ██║██║  ██║ ╚████╔╝ ██║███████║
   ╚════╝ ╚═╝  ╚═╝╚═╝  ╚═╝  ╚═══╝  ╚═╝╚══════╝
{C.RESET}
{C.WHITE}       Asistente de IA Personal — Instalador{C.RESET}
"""
    print(banner)

def print_step(step, total, title):
    print(f"\n{C.CYAN}{'━' * 60}{C.RESET}")
    print(f"{C.BOLD}{C.WHITE}  PASO {step} de {total}: {title}{C.RESET}")
    print(f"{C.CYAN}{'━' * 60}{C.RESET}\n")

def print_ok(msg):
    print(f"  {C.GREEN}✅ {msg}{C.RESET}")

def print_warn(msg):
    print(f"  {C.YELLOW}⚠️  {msg}{C.RESET}")

def print_err(msg):
    print(f"  {C.RED}❌ {msg}{C.RESET}")

def print_info(msg):
    print(f"  {C.DIM}{msg}{C.RESET}")

def print_highlight(msg):
    print(f"  {C.MAGENTA}{C.BOLD}{msg}{C.RESET}")

def ask(prompt, default=""):
    suffix = f" [{default}]" if default else ""
    try:
        val = input(f"  {C.CYAN}>{C.RESET} {prompt}{suffix}: ").strip()
        return val if val else default
    except (EOFError, KeyboardInterrupt):
        print("\n\n  Instalacion cancelada.")
        sys.exit(0)

def ask_yes_no(prompt, default=True):
    hint = "S/n" if default else "s/N"
    try:
        val = input(f"  {C.CYAN}>{C.RESET} {prompt} [{hint}]: ").strip().lower()
        if not val:
            return default
        return val in ("s", "si", "sí", "y", "yes")
    except (EOFError, KeyboardInterrupt):
        print("\n\n  Instalacion cancelada.")
        sys.exit(0)

def ask_choice(prompt, options):
    print(f"  {prompt}\n")
    for i, (label, desc) in enumerate(options, 1):
        if i == 1:
            print(f"  {C.GREEN}{C.BOLD}  [{i}] {label}{C.RESET}  {C.GREEN}<- RECOMENDADO{C.RESET}")
        else:
            print(f"  {C.WHITE}  [{i}] {label}{C.RESET}")
        if desc:
            print(f"  {C.DIM}      {desc}{C.RESET}")
    print()
    while True:
        try:
            val = input(f"  {C.CYAN}>{C.RESET} Elige una opcion (1-{len(options)}): ").strip()
            idx = int(val) - 1
            if 0 <= idx < len(options):
                return idx
        except (ValueError, EOFError, KeyboardInterrupt):
            pass
        print(f"  {C.RED}Opcion no valida.{C.RESET}")

def run_cmd(cmd, desc="", show_output=False, timeout=300):
    if desc:
        print(f"  {C.DIM}⏳ {desc}...{C.RESET}", end="", flush=True)
    try:
        kwargs = {"capture_output": not show_output, "text": True, "timeout": timeout}
        if os.name == "nt" and not show_output:
            kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW
        result = subprocess.run(cmd, shell=True, **kwargs)
        if desc:
            if result.returncode == 0:
                print(f" {C.GREEN}OK{C.RESET}")
            else:
                print(f" {C.RED}FALLO{C.RESET}")
        return result.returncode == 0
    except subprocess.TimeoutExpired:
        if desc:
            print(f" {C.YELLOW}TIMEOUT{C.RESET}")
        return False
    except Exception as e:
        if desc:
            print(f" {C.RED}ERROR: {e}{C.RESET}")
        return False


# ---------------------------------------------------------------------------
# Deteccion de hardware y software
# ---------------------------------------------------------------------------

def detect_gpu():
    """Detecta GPU disponible. Retorna dict con info."""
    info = {"has_nvidia": False, "has_amd": False, "name": "", "vram_gb": 0}
    try:
        r = subprocess.run(
            ["wmic", "path", "win32_videocontroller", "get", "name,AdapterRAM"],
            capture_output=True, text=True, timeout=10,
        )
        for line in r.stdout.strip().split("\n")[1:]:
            line = line.strip()
            if not line:
                continue
            if "NVIDIA" in line.upper():
                info["has_nvidia"] = True
                info["name"] = line.split("  ")[0].strip() if "  " in line else line
            elif "RX" in line.upper() or ("AMD" in line.upper() and "RADEON" in line.upper() and "GRAPHICS" not in line.upper()):
                info["has_amd"] = True
                info["name"] = line.split("  ")[0].strip() if "  " in line else line
    except Exception:
        pass
    return info

def check_ollama():
    """Verifica si Ollama esta instalado."""
    return shutil.which("ollama") is not None

def check_ffmpeg():
    """Verifica si FFmpeg esta instalado."""
    return shutil.which("ffmpeg") is not None

def check_scoop():
    """Verifica si scoop esta instalado."""
    return shutil.which("scoop") is not None

def ollama_has_model(model):
    """Verifica si un modelo de Ollama esta descargado."""
    try:
        r = subprocess.run(["ollama", "list"], capture_output=True, text=True, timeout=10)
        return model in r.stdout
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Pasos del wizard
# ---------------------------------------------------------------------------

def step_provider(config):
    """Paso 1: Elegir proveedor de IA."""
    print_step(1, 5, "Proveedor de IA")

    print(f"  {C.BOLD}Jarvis necesita un cerebro de IA para funcionar.{C.RESET}")
    print(f"  Puedes usar uno {C.GREEN}GRATIS y local{C.RESET} o uno en la nube (de pago).\n")

    choice = ask_choice("¿Que proveedor quieres usar?", [
        ("Ollama — GRATIS, local, sin internet", "Corre en tu PC. No necesitas pagar ni crear cuentas. Privado."),
        ("Claude (Anthropic) — Pago", "Requiere API key de console.anthropic.com"),
        ("OpenAI (GPT) — Pago", "Requiere API key de platform.openai.com"),
        ("Google Gemini — Tier gratis disponible", "Requiere API key de aistudio.google.com/apikey"),
    ])

    if choice == 0:
        config["provider"] = "ollama"
        _setup_ollama(config)
    elif choice == 1:
        config["provider"] = "claude"
        key = ask("Pega tu API key de Anthropic (sk-ant-...)")
        config["anthropic_key"] = key
    elif choice == 2:
        config["provider"] = "openai"
        key = ask("Pega tu API key de OpenAI (sk-...)")
        config["openai_key"] = key
    elif choice == 3:
        config["provider"] = "gemini"
        key = ask("Pega tu API key de Gemini")
        config["gemini_key"] = key


def _setup_ollama(config):
    """Sub-flujo para instalar y configurar Ollama."""
    print()

    # Verificar Ollama
    if check_ollama():
        print_ok("Ollama ya esta instalado")
    else:
        print_warn("Ollama no esta instalado")
        print()
        print(f"  {C.BOLD}Ollama es el servidor de IA local. Sin el, Jarvis no puede pensar.{C.RESET}")
        print(f"  {C.DIM}Instalando automaticamente...{C.RESET}")
        print()

        # Intentar con winget
        installed = False
        if shutil.which("winget"):
            print(f"  {C.DIM}Instalando Ollama con winget (puede tardar unos minutos)...{C.RESET}")
            result = subprocess.run(
                ["winget", "install", "Ollama.Ollama", "--accept-source-agreements", "--accept-package-agreements", "--silent", "--disable-interactivity"],
                capture_output=True, text=True, timeout=300,
            )
            # Actualizar PATH
            user_path = subprocess.run(["powershell", "-NoProfile", "-Command",
                "[Environment]::GetEnvironmentVariable('Path','User')"],
                capture_output=True, text=True).stdout.strip()
            machine_path = subprocess.run(["powershell", "-NoProfile", "-Command",
                "[Environment]::GetEnvironmentVariable('Path','Machine')"],
                capture_output=True, text=True).stdout.strip()
            os.environ["PATH"] = machine_path + ";" + user_path + ";" + os.environ.get("PATH", "")

            if check_ollama():
                installed = True
                print_ok("Ollama instalado correctamente")

        if not installed:
            # Descarga directa
            print(f"  {C.DIM}Descargando Ollama desde ollama.ai...{C.RESET}")
            try:
                import urllib.request
                installer_path = os.path.join(os.environ.get("TEMP", "."), "OllamaSetup.exe")
                urllib.request.urlretrieve("https://ollama.com/download/OllamaSetup.exe", installer_path)
                print(f"  {C.DIM}Ejecutando instalador...{C.RESET}")
                subprocess.run([installer_path, "/VERYSILENT", "/NORESTART"], timeout=120)
                time.sleep(5)
                # Actualizar PATH
                user_path = subprocess.run(["powershell", "-NoProfile", "-Command",
                    "[Environment]::GetEnvironmentVariable('Path','User')"],
                    capture_output=True, text=True).stdout.strip()
                os.environ["PATH"] = user_path + ";" + os.environ.get("PATH", "")

                if check_ollama():
                    installed = True
                    print_ok("Ollama instalado correctamente")
                try:
                    os.unlink(installer_path)
                except OSError:
                    pass
            except Exception as e:
                print_err(f"Error descargando: {e}")

        if not installed:
            print()
            print_err("No pude instalar Ollama automaticamente.")
            print()
            print(f"  {C.BOLD}Instalalo manualmente:{C.RESET}")
            print(f"  {C.CYAN}1.{C.RESET} Ve a {C.BOLD}https://ollama.ai{C.RESET}")
            print(f"  {C.CYAN}2.{C.RESET} Descarga e instala para Windows")
            print(f"  {C.CYAN}3.{C.RESET} Despues de instalar, vuelve aqui y presiona Enter")
            print()
            try:
                os.startfile("https://ollama.ai")
            except Exception:
                pass
            input(f"  {C.CYAN}>{C.RESET} Presiona Enter cuando hayas instalado Ollama...")

            if not check_ollama():
                print_err("Ollama sigue sin detectarse. Ejecuta setup.py de nuevo despues de instalar.")
                sys.exit(1)
            print_ok("Ollama detectado")

    # Detectar GPU
    print()
    gpu = detect_gpu()

    if gpu["has_nvidia"]:
        print_ok(f"GPU detectada: {gpu['name']} (NVIDIA)")
        print_info("Ollama usara tu GPU automaticamente. Respuestas rapidas.")
        config["gpu"] = "nvidia"
    elif gpu["has_amd"]:
        print_ok(f"GPU detectada: {gpu['name']} (AMD)")
        print()
        print(f"  {C.YELLOW}AMD requiere configuracion extra para usar GPU con Ollama.{C.RESET}")
        print(f"  {C.WHITE}Puedes elegir:{C.RESET}")
        gpu_choice = ask_choice("¿Como quieres ejecutar los modelos?", [
            ("CPU (funciona siempre, mas lento ~5s por respuesta)", "Recomendado si no quieres complicarte"),
            ("GPU AMD (mas rapido si funciona, puede requerir drivers)", "Intentara usar tu GPU. Si falla, cae a CPU automaticamente."),
        ])
        if gpu_choice == 1:
            print_info("Configurando variable HSA_OVERRIDE_GFX_VERSION...")
            subprocess.run(["setx", "HSA_OVERRIDE_GFX_VERSION", "10.3.0"],
                         capture_output=True, timeout=10)
            print_info("Reinicia Ollama despues de la instalacion para activar GPU.")
            config["gpu"] = "amd"
        else:
            config["gpu"] = "cpu"
    else:
        print_info("No se detecto GPU dedicada. Ollama usara CPU.")
        print_info("Funciona perfecto, las respuestas tardan ~5 segundos.")
        config["gpu"] = "cpu"

    # Asegurarse de que Ollama esta corriendo
    print()
    print(f"  {C.DIM}Verificando que Ollama este corriendo...{C.RESET}")
    try:
        import urllib.request
        urllib.request.urlopen("http://localhost:11434/api/tags", timeout=3)
        print_ok("Ollama esta corriendo")
    except Exception:
        print(f"  {C.DIM}Iniciando Ollama...{C.RESET}")
        if sys.platform == "win32":
            ollama_app = os.path.join(os.environ.get("LOCALAPPDATA", ""), "Programs", "Ollama", "ollama app.exe")
            if os.path.exists(ollama_app):
                subprocess.Popen([ollama_app], creationflags=subprocess.CREATE_NO_WINDOW)
            else:
                subprocess.Popen(["ollama", "serve"], creationflags=subprocess.CREATE_NO_WINDOW)
        time.sleep(5)
        try:
            urllib.request.urlopen("http://localhost:11434/api/tags", timeout=3)
            print_ok("Ollama iniciado")
        except Exception:
            print_warn("No pude iniciar Ollama. Puede que necesites abrirlo manualmente.")

    # Determinar modelos a descargar
    print()
    print(f"  {C.BOLD}Descargando modelos de IA...{C.RESET}")
    print_info("Esto puede tardar varios minutos la primera vez (se descargan una sola vez).")
    print_info("El progreso se muestra en la terminal.")
    print()

    # Modelo principal: llama3.2 (rapido para conversacion)
    if ollama_has_model("llama3.2"):
        print_ok("llama3.2 ya descargado (modelo de conversacion)")
    else:
        print(f"  {C.CYAN}Descargando llama3.2 (~2GB) — modelo de conversacion...{C.RESET}")
        print_info("Esto tarda unos minutos dependiendo de tu internet.")
        result = subprocess.run(["ollama", "pull", "llama3.2"], timeout=600)
        if result.returncode == 0 and ollama_has_model("llama3.2"):
            print_ok("llama3.2 descargado")
        else:
            print_err("Error descargando llama3.2. Puedes intentar despues con: ollama pull llama3.2")

    # Modelo de vision: llava (opcional)
    print()
    print(f"  {C.BOLD}Modelo de vision (opcional):{C.RESET}")
    print_info("llava permite a Jarvis analizar fotos y capturas de pantalla.")
    print_info("Tamano: ~4.7GB")
    print()
    if ollama_has_model("llava"):
        print_ok("llava ya descargado")
        config["vision"] = True
    else:
        if ask_yes_no("Descargar llava para analisis de imagenes? (4.7GB)", default=True):
            print(f"  {C.CYAN}Descargando llava (~4.7GB)...{C.RESET}")
            print_info("Esto puede tardar bastante. Se paciente.")
            result = subprocess.run(["ollama", "pull", "llava"], timeout=1800)
            if result.returncode == 0 and ollama_has_model("llava"):
                print_ok("llava descargado")
                config["vision"] = True
            else:
                print_warn("Error descargando llava. Puedes intentar despues con: ollama pull llava")
                config["vision"] = False
        else:
            config["vision"] = False
            print_info("Omitido. Puedes descargarlo despues con: ollama pull llava")

    config["ollama_model"] = "llama3.2"
    config["vision_model"] = "llava" if config.get("vision") else ""


def step_telegram(config):
    """Paso 2: Configurar Telegram."""
    print_step(2, 5, "Telegram (control remoto)")

    print(f"  {C.BOLD}Telegram te permite controlar Jarvis desde tu celular.{C.RESET}")
    print_info("Puedes enviar mensajes de texto, audio, fotos y documentos.")
    print_info("Jarvis responde y ejecuta acciones en tu PC remotamente.")
    print(f"  {C.DIM}(Opcional pero muy recomendado){C.RESET}")
    print()

    if not ask_yes_no("¿Quieres configurar Telegram?", default=True):
        config["telegram_token"] = ""
        config["telegram_user_id"] = ""
        print_info("Omitido. Puedes configurarlo despues editando el archivo .env")
        return

    # Guia para crear bot
    print()
    print(f"  {C.BOLD}{C.CYAN}Como crear tu bot de Telegram:{C.RESET}")
    print(f"  {C.WHITE}1.{C.RESET} Abre Telegram en tu celular o PC")
    print(f"  {C.WHITE}2.{C.RESET} Busca {C.BOLD}@BotFather{C.RESET} (es un bot oficial de Telegram)")
    print(f"  {C.WHITE}3.{C.RESET} Envia {C.BOLD}/newbot{C.RESET}")
    print(f"  {C.WHITE}4.{C.RESET} Dale un nombre (ej: 'Mi Jarvis')")
    print(f"  {C.WHITE}5.{C.RESET} Dale un username terminado en 'bot' (ej: 'mi_jarvis_bot')")
    print(f"  {C.WHITE}6.{C.RESET} BotFather te dara un {C.BOLD}token{C.RESET} — copialo")
    print()

    token = ask("Pega el token de tu bot")

    # Validar token
    if token:
        print(f"  {C.DIM}Verificando token...{C.RESET}", end="", flush=True)
        try:
            import urllib.request
            req = urllib.request.Request(f"https://api.telegram.org/bot{token}/getMe")
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read())
            if data.get("ok"):
                bot_name = data["result"]["username"]
                print(f" {C.GREEN}✅ Bot valido: @{bot_name}{C.RESET}")
                config["telegram_token"] = token
            else:
                print(f" {C.RED}Token invalido{C.RESET}")
                config["telegram_token"] = token  # guardar igual, usuario lo corregira
        except Exception:
            print(f" {C.YELLOW}No pude verificar (sin internet?). Se guardara de todas formas.{C.RESET}")
            config["telegram_token"] = token
    else:
        config["telegram_token"] = ""
        return

    # User ID
    print()
    print(f"  {C.BOLD}{C.CYAN}Ahora necesito tu User ID de Telegram:{C.RESET}")
    print(f"  {C.WHITE}1.{C.RESET} Busca {C.BOLD}@userinfobot{C.RESET} en Telegram")
    print(f"  {C.WHITE}2.{C.RESET} Envia {C.BOLD}/start{C.RESET}")
    print(f"  {C.WHITE}3.{C.RESET} Te respondera con tu {C.BOLD}Id{C.RESET} (un numero)")
    print()
    print_info("Este ID es para seguridad: solo TU puedes darle ordenes al bot.")
    print()

    user_id = ask("Pega tu User ID (numero)")
    config["telegram_user_id"] = user_id
    if user_id:
        print_ok(f"User ID configurado: {user_id}")


def step_dependencies(config):
    """Paso 3: Instalar dependencias."""
    print_step(3, 5, "Instalando dependencias")

    # Python dependencies
    print(f"  {C.BOLD}Instalando paquetes de Python...{C.RESET}")
    run_cmd(
        f"{sys.executable} -m pip install -r requirements.txt -q",
        "Instalando dependencias",
        timeout=300,
    )

    # FFmpeg
    print()
    if check_ffmpeg():
        print_ok("FFmpeg ya instalado")
    else:
        print(f"  {C.DIM}Instalando FFmpeg (necesario para audio y voz)...{C.RESET}")
        ffmpeg_installed = False

        # Intentar con winget
        if shutil.which("winget"):
            if run_cmd("winget install Gyan.FFmpeg --accept-source-agreements --accept-package-agreements --silent --disable-interactivity",
                       "Instalando FFmpeg con winget", timeout=180):
                ffmpeg_installed = True

        # Intentar con scoop
        if not ffmpeg_installed and check_scoop():
            if run_cmd("scoop install ffmpeg", "Instalando FFmpeg con scoop", timeout=120):
                ffmpeg_installed = True

        if ffmpeg_installed or check_ffmpeg():
            print_ok("FFmpeg instalado")
        else:
            print_warn("No pude instalar FFmpeg automaticamente.")
            print_info("Jarvis funcionara pero sin soporte de audio en Telegram.")
            print_info("Para instalar despues: winget install Gyan.FFmpeg")


def step_autostart(config):
    """Paso 4: Configurar inicio automatico."""
    print_step(4, 5, "Inicio automatico")

    print(f"  {C.BOLD}Jarvis puede arrancar automaticamente cuando enciendas tu PC.{C.RESET}")
    print_info("Se abrira una terminal con Jarvis listo para atenderte.")
    print_info("Te saludara y te dara informacion util del dia.")
    print()

    if not ask_yes_no("¿Quieres que Jarvis arranque al encender el PC?", default=True):
        config["autostart"] = False
        print_info("Omitido. Para iniciar Jarvis manualmente: python main.py")
        return

    config["autostart"] = True

    # Crear script de inicio
    jarvis_dir = os.path.dirname(os.path.abspath(__file__))
    bat_content = f'@echo off\ncd /d "{jarvis_dir}"\n"{sys.executable}" main.py\npause\n'

    startup_dir = os.path.join(
        os.environ.get("APPDATA", ""),
        "Microsoft", "Windows", "Start Menu", "Programs", "Startup",
    )

    bat_path = os.path.join(startup_dir, "Jarvis.bat")
    try:
        with open(bat_path, "w") as f:
            f.write(bat_content)
        print_ok(f"Inicio automatico configurado")
        print_info(f"Archivo: {bat_path}")
    except Exception as e:
        print_err(f"No pude crear el acceso directo: {e}")
        print_info(f"Puedes crearlo manualmente: copia un .bat en {startup_dir}")


def step_finalize(config):
    """Paso 5: Generar .env y verificar."""
    print_step(5, 5, "Configuracion final")

    # Generar .env
    jarvis_dir = os.path.dirname(os.path.abspath(__file__))
    env_path = os.path.join(jarvis_dir, ".env")

    env_lines = [
        "# ==========================================",
        "# JARVIS - Configuracion generada por setup.py",
        "# ==========================================",
        "",
        f"AI_PROVIDER={config.get('provider', 'ollama')}",
        "ASSISTANT_NAME=Jarvis",
        "VOICE_LANGUAGE=es",
        "VOICE_SPEED=180",
        "",
        f"OPENAI_API_KEY={config.get('openai_key', '')}",
        f"ANTHROPIC_API_KEY={config.get('anthropic_key', '')}",
        f"GEMINI_API_KEY={config.get('gemini_key', '')}",
        "",
        "CLAUDE_MODEL=claude-sonnet-4-20250514",
        "OPENAI_MODEL=gpt-4o",
        "GEMINI_MODEL=gemini-2.0-flash",
        f"OLLAMA_MODEL={config.get('ollama_model', 'llama3.2')}",
        f"OLLAMA_VISION_MODEL={config.get('vision_model', 'llava')}",
        "OLLAMA_FALLBACK_MODEL=llama3.2",
        "",
        "# Telegram",
        f"TELEGRAM_BOT_TOKEN={config.get('telegram_token', '')}",
        f"TELEGRAM_ALLOWED_USERS={config.get('telegram_user_id', '')}",
        "TELEGRAM_ENABLE_VOICE=true",
    ]

    with open(env_path, "w", encoding="utf-8") as f:
        f.write("\n".join(env_lines) + "\n")

    print_ok("Archivo .env generado")

    # Resumen
    print()
    print(f"  {C.CYAN}{'━' * 60}{C.RESET}")
    print(f"  {C.BOLD}{C.WHITE}  RESUMEN DE CONFIGURACION{C.RESET}")
    print(f"  {C.CYAN}{'━' * 60}{C.RESET}")
    print()

    provider = config.get("provider", "ollama").upper()
    print_ok(f"Proveedor IA: {provider}")

    if config.get("provider") == "ollama":
        print_ok(f"Modelo principal: {config.get('ollama_model', 'llama3.2')}")
        if config.get("vision"):
            print_ok(f"Modelo de vision: {config.get('vision_model', 'llava')}")
        gpu = config.get("gpu", "cpu")
        if gpu == "nvidia":
            print_ok("GPU: NVIDIA (acelerada)")
        elif gpu == "amd":
            print_ok("GPU: AMD (requiere reiniciar Ollama)")
        else:
            print_ok("Procesador: CPU")

    if config.get("telegram_token"):
        print_ok(f"Telegram: Configurado (User ID: {config.get('telegram_user_id', '?')})")
    else:
        print_info("Telegram: No configurado")

    if config.get("autostart"):
        print_ok("Inicio automatico: Activado")
    else:
        print_info("Inicio automatico: Desactivado")

    ffmpeg = "Instalado" if check_ffmpeg() else "No instalado"
    print_ok(f"FFmpeg: {ffmpeg}")


def step_first_run(config):
    """Ofrece ejecutar Jarvis por primera vez."""
    print()
    print(f"  {C.GREEN}{C.BOLD}{'━' * 60}{C.RESET}")
    print(f"  {C.GREEN}{C.BOLD}  ¡Instalacion completa!{C.RESET}")
    print(f"  {C.GREEN}{C.BOLD}{'━' * 60}{C.RESET}")
    print()
    print(f"  Para iniciar Jarvis en cualquier momento:")
    print(f"  {C.CYAN}{C.BOLD}  python main.py{C.RESET}")
    print()

    if config.get("telegram_token"):
        print_info("Tambien puedes hablarle desde Telegram a tu bot.")
    print()

    if ask_yes_no("¿Quieres arrancar Jarvis ahora?", default=True):
        print()
        print(f"  {C.CYAN}Iniciando Jarvis...{C.RESET}")
        print()
        os.execv(sys.executable, [sys.executable, "main.py"])


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    os.chdir(os.path.dirname(os.path.abspath(__file__)))

    # Habilitar colores ANSI en Windows
    if os.name == "nt":
        os.system("")

    clear()
    print_banner()

    print(f"  {C.WHITE}Bienvenido! Este asistente te guiara para configurar JARVIS{C.RESET}")
    print(f"  {C.WHITE}en tu PC. Solo sigue los pasos.{C.RESET}")
    print()
    print(f"  {C.DIM}Presiona Ctrl+C en cualquier momento para cancelar.{C.RESET}")

    config = {}

    step_provider(config)
    step_telegram(config)
    step_dependencies(config)
    step_autostart(config)
    step_finalize(config)
    step_first_run(config)


if __name__ == "__main__":
    main()
