import subprocess
import os
import sys
import datetime
import platform
from rich.console import Console

console = Console()

# Aplicaciones conocidas y sus posibles rutas en Windows
KNOWN_APPS = {
    "spotify": [
        os.path.expandvars(r"%APPDATA%\Spotify\Spotify.exe"),
        os.path.expandvars(r"%LOCALAPPDATA%\Microsoft\WindowsApps\Spotify.exe"),
    ],
    "chrome": [
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe"),
    ],
    "brave": [
        r"C:\Program Files\BraveSoftware\Brave-Browser\Application\brave.exe",
        os.path.expandvars(r"%LOCALAPPDATA%\BraveSoftware\Brave-Browser\Application\brave.exe"),
    ],
    "firefox": [
        r"C:\Program Files\Mozilla Firefox\firefox.exe",
        r"C:\Program Files (x86)\Mozilla Firefox\firefox.exe",
    ],
    "notepad": ["notepad.exe"],
    "bloc de notas": ["notepad.exe"],
    "calculadora": ["calc.exe"],
    "calculator": ["calc.exe"],
    "explorador": ["explorer.exe"],
    "explorer": ["explorer.exe"],
    "cmd": ["cmd.exe"],
    "terminal": ["wt.exe", "cmd.exe"],
    "powershell": ["powershell.exe"],
    "word": [
        r"C:\Program Files\Microsoft Office\root\Office16\WINWORD.EXE",
        r"C:\Program Files (x86)\Microsoft Office\root\Office16\WINWORD.EXE",
    ],
    "excel": [
        r"C:\Program Files\Microsoft Office\root\Office16\EXCEL.EXE",
        r"C:\Program Files (x86)\Microsoft Office\root\Office16\EXCEL.EXE",
    ],
    "code": [
        os.path.expandvars(r"%LOCALAPPDATA%\Programs\Microsoft VS Code\Code.exe"),
    ],
    "vscode": [
        os.path.expandvars(r"%LOCALAPPDATA%\Programs\Microsoft VS Code\Code.exe"),
    ],
    "visual studio code": [
        os.path.expandvars(r"%LOCALAPPDATA%\Programs\Microsoft VS Code\Code.exe"),
    ],
    "cursor": [
        os.path.expandvars(r"%LOCALAPPDATA%\Programs\cursor\Cursor.exe"),
    ],
    "postman": [
        os.path.expandvars(r"%LOCALAPPDATA%\Postman\Postman.exe"),
    ],
    "discord": [
        os.path.expandvars(r"%LOCALAPPDATA%\Discord\Update.exe"),
    ],
    "whatsapp": [
        os.path.expandvars(r"%LOCALAPPDATA%\WhatsApp\WhatsApp.exe"),
    ],
    "telegram": [
        os.path.expandvars(r"%APPDATA%\Telegram Desktop\Telegram.exe"),
    ],
    "paint": ["mspaint.exe"],
    "configuracion": ["ms-settings:"],
    "settings": ["ms-settings:"],
}


def open_application(app_name: str) -> dict:
    """Abre una aplicacion en el PC."""
    app_key = app_name.lower().strip()

    # Buscar en apps conocidas
    if app_key in KNOWN_APPS:
        paths = KNOWN_APPS[app_key]
        for path in paths:
            try:
                if path.startswith("ms-"):
                    os.startfile(path)
                    return {"success": True, "message": f"Se abrio {app_name}"}

                if os.path.exists(path) or "\\" not in path:
                    if app_key == "discord":
                        subprocess.Popen([path, "--processStart", "Discord.exe"],
                                        creationflags=subprocess.CREATE_NO_WINDOW)
                    else:
                        subprocess.Popen([path], creationflags=subprocess.CREATE_NO_WINDOW)
                    return {"success": True, "message": f"Se abrio {app_name}"}
            except Exception:
                continue

    # Intentar abrir directamente con el nombre (por si esta en PATH)
    try:
        subprocess.Popen([app_key], creationflags=subprocess.CREATE_NO_WINDOW, shell=True)
        return {"success": True, "message": f"Se abrio {app_name}"}
    except Exception:
        pass

    # Intentar con start
    try:
        os.system(f'start "" "{app_key}"')
        return {"success": True, "message": f"Se intento abrir {app_name}"}
    except Exception:
        return {"success": False, "message": f"No se pudo encontrar ni abrir {app_name}"}


def close_application(app_name: str) -> dict:
    """Cierra una aplicacion."""
    process_names = {
        "spotify": "Spotify.exe",
        "chrome": "chrome.exe",
        "brave": "brave.exe",
        "firefox": "firefox.exe",
        "notepad": "notepad.exe",
        "word": "WINWORD.EXE",
        "excel": "EXCEL.EXE",
        "code": "Code.exe",
        "vscode": "Code.exe",
        "cursor": "Cursor.exe",
        "discord": "Discord.exe",
        "postman": "Postman.exe",
    }

    app_key = app_name.lower().strip()
    proc_name = process_names.get(app_key, f"{app_key}.exe")

    try:
        result = subprocess.run(
            ["taskkill", "/IM", proc_name, "/F"],
            capture_output=True, text=True,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
        if result.returncode == 0:
            return {"success": True, "message": f"Se cerro {app_name}"}
        else:
            return {"success": False, "message": f"No se encontro {app_name} ejecutandose"}
    except Exception as e:
        return {"success": False, "message": f"Error cerrando {app_name}: {e}"}


def open_website(url: str) -> dict:
    """Abre una pagina web en el navegador predeterminado."""
    try:
        if not url.startswith("http"):
            url = f"https://{url}"
        os.startfile(url)
        return {"success": True, "message": f"Se abrio {url}"}
    except Exception as e:
        return {"success": False, "message": f"Error abriendo {url}: {e}"}


def search_web(query: str) -> dict:
    """Busca algo en Google."""
    try:
        import urllib.parse
        url = f"https://www.google.com/search?q={urllib.parse.quote(query)}"
        os.startfile(url)
        return {"success": True, "message": f"Buscando '{query}' en Google"}
    except Exception as e:
        return {"success": False, "message": f"Error buscando: {e}"}


def get_system_info() -> dict:
    """Obtiene informacion del sistema."""
    try:
        info = {
            "os": f"{platform.system()} {platform.release()}",
            "version": platform.version(),
            "machine": platform.machine(),
            "processor": platform.processor(),
            "user": os.getenv("USERNAME", "desconocido"),
            "pc_name": platform.node(),
        }
        return {"success": True, "message": str(info), "data": info}
    except Exception as e:
        return {"success": False, "message": f"Error: {e}"}


def get_datetime() -> dict:
    """Obtiene la fecha y hora actual."""
    now = datetime.datetime.now()
    return {
        "success": True,
        "message": now.strftime("%A %d de %B de %Y, %I:%M %p"),
        "data": {
            "date": now.strftime("%Y-%m-%d"),
            "time": now.strftime("%H:%M:%S"),
            "day": now.strftime("%A"),
        }
    }


def set_volume(level: int) -> dict:
    """Ajusta el volumen del sistema (0-100)."""
    try:
        level = max(0, min(100, level))
        # Convertir porcentaje a valor de 0-65535
        value = int(level * 65535 / 100)
        ps_script = f'''
$obj = New-Object -ComObject WScript.Shell
# Primero silenciar y luego subir al nivel deseado
for ($i = 0; $i -lt 50; $i++) {{ $obj.SendKeys([char]174) }}
$steps = [math]::Round({level} / 2)
for ($i = 0; $i -lt $steps; $i++) {{ $obj.SendKeys([char]175) }}
'''
        subprocess.run(
            ["powershell", "-NoProfile", "-Command", ps_script],
            capture_output=True,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
        return {"success": True, "message": f"Volumen ajustado a {level}%"}
    except Exception as e:
        return {"success": False, "message": f"Error ajustando volumen: {e}"}


def mute_volume() -> dict:
    """Silencia o activa el sonido."""
    try:
        ps_script = '''
$obj = New-Object -ComObject WScript.Shell
$obj.SendKeys([char]173)
'''
        subprocess.run(
            ["powershell", "-NoProfile", "-Command", ps_script],
            capture_output=True,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
        return {"success": True, "message": "Se cambio el estado del silencio"}
    except Exception as e:
        return {"success": False, "message": f"Error: {e}"}


def take_screenshot() -> dict:
    """Toma una captura de pantalla."""
    try:
        screenshots_dir = os.path.join(os.path.expanduser("~"), "Pictures", "Jarvis_Screenshots")
        os.makedirs(screenshots_dir, exist_ok=True)

        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        filepath = os.path.join(screenshots_dir, f"screenshot_{timestamp}.png")

        ps_script = f'''
Add-Type -AssemblyName System.Windows.Forms
$screen = [System.Windows.Forms.Screen]::PrimaryScreen.Bounds
$bitmap = New-Object System.Drawing.Bitmap($screen.Width, $screen.Height)
$graphics = [System.Drawing.Graphics]::FromImage($bitmap)
$graphics.CopyFromScreen($screen.Location, [System.Drawing.Point]::Empty, $screen.Size)
$bitmap.Save("{filepath}")
$graphics.Dispose()
$bitmap.Dispose()
'''
        subprocess.run(
            ["powershell", "-NoProfile", "-Command", ps_script],
            capture_output=True,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )

        if os.path.exists(filepath):
            return {"success": True, "message": f"Captura guardada en {filepath}"}
        else:
            return {"success": False, "message": "No se pudo guardar la captura"}
    except Exception as e:
        return {"success": False, "message": f"Error: {e}"}


def lock_pc() -> dict:
    """Bloquea el PC usando la API de Windows directamente."""
    try:
        import ctypes
        ctypes.windll.user32.LockWorkStation()
        return {"success": True, "message": "PC bloqueado"}
    except Exception as e:
        return {"success": False, "message": f"Error: {e}"}


def shutdown_pc(action: str = "shutdown") -> dict:
    """Apaga, reinicia o suspende el PC."""
    try:
        if action == "restart":
            subprocess.run(
                ["shutdown", "/r", "/t", "10", "/c", "Jarvis reiniciara el equipo en 10 segundos. Usa shutdown /a para cancelar."],
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
            return {"success": True, "message": "El PC se reiniciara en 10 segundos. Diga 'cancela el apagado' para detenerlo."}
        elif action == "shutdown":
            subprocess.run(
                ["shutdown", "/s", "/t", "10", "/c", "Jarvis apagara el equipo en 10 segundos. Usa shutdown /a para cancelar."],
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
            return {"success": True, "message": "El PC se apagara en 10 segundos. Diga 'cancela el apagado' para detenerlo."}
        elif action == "cancel":
            subprocess.run(["shutdown", "/a"], creationflags=subprocess.CREATE_NO_WINDOW)
            return {"success": True, "message": "Se cancelo el apagado/reinicio."}
        elif action == "sleep":
            # Suspender PC
            subprocess.run(
                ["powershell", "-NoProfile", "-Command",
                 "Add-Type -AssemblyName System.Windows.Forms; [System.Windows.Forms.Application]::SetSuspendState('Suspend', $false, $false)"],
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
            return {"success": True, "message": "PC en modo suspendido."}
        elif action == "hibernate":
            subprocess.run(["shutdown", "/h"], creationflags=subprocess.CREATE_NO_WINDOW)
            return {"success": True, "message": "PC en modo hibernacion."}
        elif action == "logoff":
            subprocess.run(["shutdown", "/l"], creationflags=subprocess.CREATE_NO_WINDOW)
            return {"success": True, "message": "Cerrando sesion."}
        return {"success": False, "message": "Accion no reconocida"}
    except Exception as e:
        return {"success": False, "message": f"Error: {e}"}


def open_folder(path: str) -> dict:
    """Abre una carpeta en el explorador."""
    try:
        if os.path.exists(path):
            os.startfile(path)
            return {"success": True, "message": f"Se abrio la carpeta {path}"}
        else:
            return {"success": False, "message": f"La carpeta {path} no existe"}
    except Exception as e:
        return {"success": False, "message": f"Error: {e}"}


def _send_media_key(key_code: str):
    """Envia una tecla multimedia usando PowerShell."""
    ps_script = f'''
Add-Type -TypeDefinition @"
using System;
using System.Runtime.InteropServices;
public class MediaKey {{
    [DllImport("user32.dll")]
    public static extern void keybd_event(byte bVk, byte bScan, uint dwFlags, int dwExtraInfo);
    public const byte VK_MEDIA_PLAY_PAUSE = 0xB3;
    public const byte VK_MEDIA_NEXT_TRACK = 0xB0;
    public const byte VK_MEDIA_PREV_TRACK = 0xB1;
    public const byte VK_MEDIA_STOP = 0xB2;
    public const uint KEYEVENTF_KEYDOWN = 0x0000;
    public const uint KEYEVENTF_KEYUP = 0x0002;
    public static void Press(byte key) {{
        keybd_event(key, 0, KEYEVENTF_KEYDOWN, 0);
        keybd_event(key, 0, KEYEVENTF_KEYUP, 0);
    }}
}}
"@
[MediaKey]::Press([MediaKey]::{key_code})
'''
    subprocess.run(
        ["powershell", "-NoProfile", "-Command", ps_script],
        capture_output=True,
        creationflags=subprocess.CREATE_NO_WINDOW,
    )


def media_play_pause() -> dict:
    """Reproduce o pausa la musica/media actual."""
    try:
        _send_media_key("VK_MEDIA_PLAY_PAUSE")
        return {"success": True, "message": "Play/Pausa ejecutado"}
    except Exception as e:
        return {"success": False, "message": f"Error: {e}"}


def media_next() -> dict:
    """Siguiente cancion/track."""
    try:
        _send_media_key("VK_MEDIA_NEXT_TRACK")
        return {"success": True, "message": "Siguiente cancion"}
    except Exception as e:
        return {"success": False, "message": f"Error: {e}"}


def media_previous() -> dict:
    """Cancion anterior."""
    try:
        _send_media_key("VK_MEDIA_PREV_TRACK")
        return {"success": True, "message": "Cancion anterior"}
    except Exception as e:
        return {"success": False, "message": f"Error: {e}"}


def spotify_play(uri: str = "") -> dict:
    """Abre Spotify y reproduce contenido especifico usando URIs de Spotify."""
    try:
        if uri:
            os.startfile(uri)
            return {"success": True, "message": f"Reproduciendo en Spotify"}
        else:
            _send_media_key("VK_MEDIA_PLAY_PAUSE")
            return {"success": True, "message": "Play/Pausa en Spotify"}
    except Exception as e:
        return {"success": False, "message": f"Error: {e}"}


def _focus_spotify() -> bool:
    """Enfoca la ventana de Spotify."""
    try:
        ps_script = '''
$spotify = Get-Process Spotify -ErrorAction SilentlyContinue | Where-Object { $_.MainWindowHandle -ne 0 }
if ($spotify) {
    $hwnd = $spotify.MainWindowHandle
    Add-Type -TypeDefinition @"
    using System;
    using System.Runtime.InteropServices;
    public class WinAPI {
        [DllImport("user32.dll")]
        public static extern bool SetForegroundWindow(IntPtr hWnd);
        [DllImport("user32.dll")]
        public static extern bool ShowWindow(IntPtr hWnd, int nCmdShow);
    }
"@
    [WinAPI]::ShowWindow($hwnd, 9)
    [WinAPI]::SetForegroundWindow($hwnd)
    Write-Output "OK"
} else {
    Write-Output "NOT_FOUND"
}
'''
        result = subprocess.run(
            ["powershell", "-NoProfile", "-Command", ps_script],
            capture_output=True, text=True,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
        return "OK" in result.stdout
    except Exception:
        return False


def _clipboard_type(text: str):
    """Escribe texto usando el clipboard (soporta unicode/espanol)."""
    import pyautogui
    import time
    ps_copy = f'Set-Clipboard -Value "{text}"'
    subprocess.run(
        ["powershell", "-NoProfile", "-Command", ps_copy],
        capture_output=True,
        creationflags=subprocess.CREATE_NO_WINDOW,
    )
    pyautogui.hotkey('ctrl', 'v')
    time.sleep(0.3)


def _is_spotify_running() -> bool:
    """Verifica si Spotify esta corriendo."""
    try:
        result = subprocess.run(
            ["tasklist", "/FI", "IMAGENAME eq Spotify.exe", "/NH"],
            capture_output=True, text=True,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
        return "Spotify.exe" in result.stdout
    except Exception:
        return False


def spotify_search_and_play(query: str) -> dict:
    """Busca algo en Spotify y lo reproduce usando Ctrl+K (Quick Search)."""
    import time

    try:
        import pyautogui
    except ImportError:
        import urllib.parse
        os.startfile(f"spotify:search:{urllib.parse.quote(query)}")
        return {"success": True, "message": f"Buscando '{query}' en Spotify"}

    try:
        # 1. Si Spotify no esta corriendo, abrirlo
        if not _is_spotify_running():
            open_application("spotify")
            time.sleep(4)

        # 2. Enfocar ventana de Spotify
        if not _focus_spotify():
            # Si no se pudo enfocar, intentar abrir
            open_application("spotify")
            time.sleep(3)
            _focus_spotify()
            time.sleep(1)
        else:
            time.sleep(0.5)

        # 3. Abrir Quick Search con Ctrl+K
        pyautogui.hotkey('ctrl', 'k')
        time.sleep(1)

        # 4. Escribir la query usando clipboard (soporta acentos, ñ, etc.)
        _clipboard_type(query)

        # 5. Esperar a que aparezcan los resultados del Quick Search
        time.sleep(2)

        # 6. Enter reproduce el primer resultado directamente desde Quick Search
        pyautogui.press('enter')

        return {"success": True, "message": f"Reproduciendo '{query}' en Spotify"}

    except Exception as e:
        # Fallback: abrir URI de busqueda
        try:
            import urllib.parse
            os.startfile(f"spotify:search:{urllib.parse.quote(query)}")
        except Exception:
            pass
        return {"success": False, "message": f"Error: {e}"}


def spotify_search(query: str) -> dict:
    """Wrapper que llama a spotify_search_and_play."""
    return spotify_search_and_play(query)
