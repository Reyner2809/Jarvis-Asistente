import subprocess
import time
import os
from rich.console import Console

console = Console()


def type_text(text: str) -> dict:
    """Escribe texto donde este el cursor actualmente."""
    try:
        import pyautogui
        time.sleep(0.3)
        # pyautogui.typewrite no soporta unicode, usar write para espanol
        for char in text:
            if char.isascii():
                pyautogui.typewrite(char, interval=0.01)
            else:
                # Usar clipboard para caracteres especiales
                _type_unicode(char)
        return {"success": True, "message": f"Texto escrito"}
    except ImportError:
        return _type_text_fallback(text)
    except Exception as e:
        return {"success": False, "message": f"Error: {e}"}


def _type_unicode(text: str):
    """Escribe texto unicode via clipboard en Windows."""
    import pyautogui
    import subprocess
    # Copiar al clipboard
    process = subprocess.Popen(['clip'], stdin=subprocess.PIPE, creationflags=subprocess.CREATE_NO_WINDOW)
    process.communicate(text.encode('utf-16-le'))
    # Ctrl+V para pegar
    pyautogui.hotkey('ctrl', 'v')
    time.sleep(0.05)


def _type_text_fallback(text: str) -> dict:
    """Fallback sin pyautogui usando PowerShell."""
    try:
        ps_script = f'''
Add-Type -AssemblyName System.Windows.Forms
[System.Windows.Forms.SendKeys]::SendWait("{_escape_sendkeys(text)}")
'''
        subprocess.run(
            ["powershell", "-NoProfile", "-Command", ps_script],
            capture_output=True,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
        return {"success": True, "message": "Texto escrito"}
    except Exception as e:
        return {"success": False, "message": f"Error: {e}"}


def _escape_sendkeys(text: str) -> str:
    """Escapa caracteres especiales para SendKeys."""
    special = {'+': '{+}', '^': '{^}', '%': '{%}', '~': '{~}', '(': '{(}', ')': '{)}', '{': '{{}', '}': '{}}'}
    return ''.join(special.get(c, c) for c in text)


def press_key(key: str) -> dict:
    """Presiona una tecla o combinacion."""
    try:
        import pyautogui
        key = key.lower().strip()

        # Manejar combinaciones como ctrl+c, alt+f4
        if '+' in key:
            keys = [k.strip() for k in key.split('+')]
            pyautogui.hotkey(*keys)
        else:
            pyautogui.press(key)

        return {"success": True, "message": f"Tecla '{key}' presionada"}
    except Exception as e:
        return {"success": False, "message": f"Error: {e}"}


def hotkey(keys: str) -> dict:
    """Ejecuta una combinacion de teclas (ej: ctrl+c, alt+f4, ctrl+shift+n)."""
    try:
        import pyautogui
        key_list = [k.strip().lower() for k in keys.split('+')]
        pyautogui.hotkey(*key_list)
        return {"success": True, "message": f"Combinacion {keys} ejecutada"}
    except Exception as e:
        return {"success": False, "message": f"Error: {e}"}


def click_at(x: int, y: int) -> dict:
    """Hace click en una posicion especifica."""
    try:
        import pyautogui
        pyautogui.click(x, y)
        return {"success": True, "message": f"Click en ({x}, {y})"}
    except Exception as e:
        return {"success": False, "message": f"Error: {e}"}


def move_mouse(x: int, y: int) -> dict:
    """Mueve el mouse a una posicion."""
    try:
        import pyautogui
        pyautogui.moveTo(x, y)
        return {"success": True, "message": f"Mouse movido a ({x}, {y})"}
    except Exception as e:
        return {"success": False, "message": f"Error: {e}"}


def create_folder(path: str) -> dict:
    """Crea una carpeta."""
    try:
        os.makedirs(path, exist_ok=True)
        return {"success": True, "message": f"Carpeta creada: {path}"}
    except Exception as e:
        return {"success": False, "message": f"Error: {e}"}


def create_file(path: str, content: str = "") -> dict:
    """Crea un archivo con contenido opcional."""
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        return {"success": True, "message": f"Archivo creado: {path}"}
    except Exception as e:
        return {"success": False, "message": f"Error: {e}"}


def run_command(command: str) -> dict:
    """Ejecuta un comando en la terminal y retorna el resultado."""
    try:
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=30,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
        output = result.stdout or result.stderr or "Comando ejecutado sin output"
        return {"success": result.returncode == 0, "message": output[:500]}
    except subprocess.TimeoutExpired:
        return {"success": False, "message": "El comando tardo mas de 30 segundos"}
    except Exception as e:
        return {"success": False, "message": f"Error: {e}"}


def open_and_search(app_or_url: str, search_text: str) -> dict:
    """Abre una app/web y escribe texto de busqueda."""
    try:
        import pyautogui
        from . import pc_control

        # Detectar si es web
        web_search_urls = {
            "youtube": "https://www.youtube.com/results?search_query=",
            "google": "https://www.google.com/search?q=",
            "github": "https://github.com/search?q=",
            "amazon": "https://www.amazon.com/s?k=",
            "mercadolibre": "https://listado.mercadolibre.com/",
        }

        import urllib.parse
        app_lower = app_or_url.lower().strip()

        for key, base_url in web_search_urls.items():
            if key in app_lower:
                url = base_url + urllib.parse.quote(search_text)
                pc_control.open_website(url)
                return {"success": True, "message": f"Buscando '{search_text}' en {key.capitalize()}"}

        # Si no es web conocida, abrir app y escribir
        pc_control.open_application(app_or_url)
        time.sleep(2)
        pyautogui.typewrite(search_text, interval=0.02) if search_text.isascii() else _type_unicode(search_text)
        pyautogui.press('enter')
        return {"success": True, "message": f"Busqueda ejecutada en {app_or_url}"}

    except ImportError:
        # Sin pyautogui, intentar via URL si es posible
        import urllib.parse
        url = f"https://www.google.com/search?q={urllib.parse.quote(search_text + ' ' + app_or_url)}"
        os.startfile(url)
        return {"success": True, "message": f"Busqueda abierta en navegador"}
    except Exception as e:
        return {"success": False, "message": f"Error: {e}"}
