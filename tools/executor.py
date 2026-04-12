"""
Executor de herramientas para Jarvis.

Soporta dos modos:
1. Function calling nativo (Ollama tools API) — usado por el Agent Loop
2. Regex [TOOL:...] en texto — legacy, por compatibilidad
"""

import json
import re
from rich.console import Console
from . import pc_control
from . import automation
from .code_executor import execute_code

console = Console()

TOOLS = {
    "open_app": {
        "function": pc_control.find_and_open_app,
        "description": "Abre cualquier aplicacion instalada en el PC",
        "params": ["app_name"],
        "schema": {
            "app_name": {"type": "string", "description": "Nombre de la app (chrome, spotify, calculadora, whatsapp, etc.)"},
        },
    },
    "close_app": {
        "function": pc_control.close_application,
        "description": "Cierra una aplicacion",
        "params": ["app_name"],
        "schema": {
            "app_name": {"type": "string", "description": "Nombre de la app a cerrar"},
        },
    },
    "open_website": {
        "function": pc_control.open_website,
        "description": "Abre una pagina web en el navegador",
        "params": ["url"],
        "schema": {
            "url": {"type": "string", "description": "URL de la pagina (youtube.com, google.com, etc.)"},
        },
    },
    "search_web": {
        "function": pc_control.search_web,
        "description": "Abre Google en el navegador con una busqueda (para que el usuario VEA los resultados)",
        "params": ["query"],
        "schema": {
            "query": {"type": "string", "description": "Texto a buscar en Google"},
        },
    },
    "internet_search": {
        "function": None,  # Se inyecta en runtime
        "description": "Busca informacion en internet (DuckDuckGo) y devuelve los resultados como texto. Usa esto cuando NECESITES la informacion para responder.",
        "params": ["query"],
        "schema": {
            "query": {"type": "string", "description": "Que buscar en internet"},
        },
    },
    "open_and_search": {
        "function": automation.open_and_search,
        "description": "Abre una app o sitio web y busca algo dentro (youtube, github, google, etc.)",
        "params": ["app_or_url", "search_text"],
        "schema": {
            "app_or_url": {"type": "string", "description": "App o URL donde buscar (youtube.com, github.com, etc.)"},
            "search_text": {"type": "string", "description": "Texto a buscar dentro de la app/web"},
        },
    },
    "datetime": {
        "function": pc_control.get_datetime,
        "description": "Obtiene la fecha y hora actual",
        "params": [],
        "schema": {},
    },
    "set_volume": {
        "function": pc_control.set_volume,
        "description": "Ajusta el volumen del sistema (0-100)",
        "params": ["level"],
        "schema": {
            "level": {"type": "integer", "description": "Nivel de volumen de 0 a 100"},
        },
    },
    "mute": {
        "function": pc_control.mute_volume,
        "description": "Silencia o activa el sonido del sistema",
        "params": [],
        "schema": {},
    },
    "screenshot": {
        "function": pc_control.take_screenshot,
        "description": "Toma una captura de pantalla y la guarda",
        "params": [],
        "schema": {},
    },
    "record_screen": {
        "function": pc_control.record_screen,
        "description": "Graba la pantalla por N segundos",
        "params": ["seconds"],
        "schema": {
            "seconds": {"type": "integer", "description": "Segundos a grabar (default: 30)"},
        },
    },
    "lock_pc": {
        "function": pc_control.lock_pc,
        "description": "Bloquea el PC",
        "params": [],
        "schema": {},
    },
    "shutdown": {
        "function": pc_control.shutdown_pc,
        "description": "Apaga, reinicia, suspende o cancela apagado del PC",
        "params": ["action"],
        "schema": {
            "action": {"type": "string", "description": "Accion: shutdown, restart, sleep, hibernate, logoff, cancel"},
        },
    },
    "open_folder": {
        "function": pc_control.open_folder,
        "description": "Abre una carpeta en el explorador de archivos",
        "params": ["path"],
        "schema": {
            "path": {"type": "string", "description": "Ruta de la carpeta"},
        },
    },
    "media_play": {
        "function": pc_control.media_play_pause,
        "description": "Play o pausa de la musica/media actual",
        "params": [],
        "schema": {},
    },
    "media_next": {
        "function": pc_control.media_next,
        "description": "Siguiente cancion o track",
        "params": [],
        "schema": {},
    },
    "media_prev": {
        "function": pc_control.media_previous,
        "description": "Cancion o track anterior",
        "params": [],
        "schema": {},
    },
    "spotify_play": {
        "function": pc_control.spotify_play,
        "description": "Reproduce contenido en Spotify usando URI (spotify:collection:tracks para me gusta)",
        "params": ["uri"],
        "schema": {
            "uri": {"type": "string", "description": "Spotify URI"},
        },
    },
    "spotify_search": {
        "function": pc_control.spotify_search_and_play,
        "description": "Busca y reproduce algo en Spotify (cancion, artista, album, playlist)",
        "params": ["query"],
        "schema": {
            "query": {"type": "string", "description": "Nombre de cancion, artista o album a reproducir"},
        },
    },
    "whatsapp_send": {
        "function": pc_control.whatsapp_send_message,
        "description": "Envia un mensaje de WhatsApp a un contacto por nombre",
        "params": ["contact", "message"],
        "schema": {
            "contact": {"type": "string", "description": "Nombre del contacto en WhatsApp"},
            "message": {"type": "string", "description": "Texto del mensaje"},
        },
    },
    "type_text": {
        "function": automation.type_text,
        "description": "Escribe texto donde esta el cursor actualmente",
        "params": ["text"],
        "schema": {
            "text": {"type": "string", "description": "Texto a escribir"},
        },
    },
    "press_key": {
        "function": automation.press_key,
        "description": "Presiona una tecla (enter, escape, tab, f5, etc.)",
        "params": ["key"],
        "schema": {
            "key": {"type": "string", "description": "Nombre de la tecla"},
        },
    },
    "hotkey": {
        "function": automation.hotkey,
        "description": "Ejecuta una combinacion de teclas (ctrl+c, alt+f4, ctrl+shift+n)",
        "params": ["keys"],
        "schema": {
            "keys": {"type": "string", "description": "Combinacion de teclas separadas por +"},
        },
    },
    "click": {
        "function": automation.click_at,
        "description": "Hace click en una coordenada X,Y de la pantalla",
        "params": ["x", "y"],
        "schema": {
            "x": {"type": "integer", "description": "Coordenada X"},
            "y": {"type": "integer", "description": "Coordenada Y"},
        },
    },
    "create_folder": {
        "function": automation.create_folder,
        "description": "Crea una carpeta nueva",
        "params": ["path"],
        "schema": {
            "path": {"type": "string", "description": "Ruta de la carpeta a crear"},
        },
    },
    "create_file": {
        "function": automation.create_file,
        "description": "Crea un archivo con contenido",
        "params": ["path", "content"],
        "schema": {
            "path": {"type": "string", "description": "Ruta del archivo"},
            "content": {"type": "string", "description": "Contenido del archivo"},
        },
    },
    "run_cmd": {
        "function": automation.run_command,
        "description": "Ejecuta un comando en la terminal del sistema",
        "params": ["command"],
        "schema": {
            "command": {"type": "string", "description": "Comando a ejecutar"},
        },
    },
    "analyze_image": {
        "function": None,
        "description": "Analiza una imagen con IA vision (describe contenido, OCR, interpreta graficos)",
        "params": ["image_path", "prompt"],
        "schema": {
            "image_path": {"type": "string", "description": "Ruta absoluta a la imagen"},
            "prompt": {"type": "string", "description": "Pregunta especifica sobre la imagen (opcional)"},
        },
    },
    "analyze_screenshot": {
        "function": None,
        "description": "Captura la pantalla del PC y la analiza con IA vision",
        "params": [],
        "schema": {},
    },
    "schedule_reminder": {
        "function": None,
        "description": "Programa un recordatorio para el futuro. Acepta tiempo relativo ('en 30 minutos', 'en 2 horas') o absoluto ('a las 5pm', 'manana a las 9am'). El recordatorio se envia por Telegram o consola cuando llega la hora.",
        "params": ["message", "time_description"],
        "schema": {
            "message": {"type": "string", "description": "Texto del recordatorio"},
            "time_description": {"type": "string", "description": "Cuando avisar: 'en 30 minutos', 'a las 5pm', 'manana a las 9am'"},
        },
    },
    "list_reminders": {
        "function": None,
        "description": "Muestra todos los recordatorios programados pendientes",
        "params": [],
        "schema": {},
    },
    "remember": {
        "function": None,
        "description": "Guarda un hecho importante sobre el usuario en la memoria de largo plazo. Usa esto cuando el usuario comparta informacion personal, preferencias, contactos, o diga 'recuerda que...'",
        "params": ["fact", "category"],
        "schema": {
            "fact": {"type": "string", "description": "El hecho a recordar en lenguaje natural"},
            "category": {"type": "string", "description": "Categoria: personal, preferencia, contacto, nota, profesion, ubicacion"},
        },
    },
    "recall_memory": {
        "function": None,
        "description": "Busca en la memoria de largo plazo del usuario. Usa esto cuando el usuario pregunte algo que te haya dicho antes.",
        "params": ["query"],
        "schema": {
            "query": {"type": "string", "description": "Que buscar en la memoria"},
        },
    },
    "knowledge_search": {
        "function": None,
        "description": "Busca en la base de conocimiento del usuario (documentos cargados previamente)",
        "params": ["query"],
        "schema": {
            "query": {"type": "string", "description": "Texto a buscar en los documentos"},
        },
    },
    "knowledge_load": {
        "function": None,
        "description": "Carga un archivo a la base de conocimiento (PDF, DOCX, TXT, CSV, codigo)",
        "params": ["file_path"],
        "schema": {
            "file_path": {"type": "string", "description": "Ruta absoluta del archivo a cargar"},
        },
    },
    "execute_code": {
        "function": execute_code,
        "description": "Ejecuta codigo Python para cualquier tarea (crear documentos, calculos, instalar paquetes, manipular archivos, etc.)",
        "params": ["code"],
        "schema": {
            "code": {"type": "string", "description": "Codigo Python a ejecutar"},
        },
    },
}


AGENT_LOOP_TOOLS = [
    "internet_search", "execute_code", "open_app", "open_website",
    "datetime", "knowledge_search", "whatsapp_send", "search_web",
    "remember", "recall_memory", "schedule_reminder", "list_reminders",
]


def get_tools_schema(subset: list[str] | None = None) -> list[dict]:
    """
    Genera el array de tools en formato JSON schema compatible con
    Ollama function calling API.

    Si subset es None, devuelve AGENT_LOOP_TOOLS (las esenciales para
    el agent loop). Si se pasa una lista, filtra por esos nombres.
    """
    allowed = set(subset) if subset else set(AGENT_LOOP_TOOLS)

    schemas = []
    for name, tool in TOOLS.items():
        if name not in allowed:
            continue
        if tool["function"] is None:
            continue

        properties = {}
        required = []
        for param_name, param_schema in tool.get("schema", {}).items():
            properties[param_name] = param_schema
            required.append(param_name)

        schemas.append({
            "type": "function",
            "function": {
                "name": name,
                "description": tool["description"],
                "parameters": {
                    "type": "object",
                    "properties": properties,
                    "required": required,
                },
            },
        })

    return schemas


def get_tools_prompt() -> str:
    """Legacy: genera descripcion de tools para system prompt (texto)."""
    tools_desc = []
    for name, tool in TOOLS.items():
        params = ", ".join(tool["params"]) if tool["params"] else ""
        tools_desc.append(f'  - {name}({params}): {tool["description"]}')
    return "\n".join(tools_desc)


def execute_tool_call(tool_name: str, arguments: dict) -> dict:
    """
    Ejecuta una tool call del function calling nativo.
    Devuelve dict con tool, success, message.
    """
    if tool_name not in TOOLS:
        return {"tool": tool_name, "success": False, "message": f"Herramienta '{tool_name}' no existe"}

    tool = TOOLS[tool_name]
    func = tool["function"]

    if func is None:
        return {"tool": tool_name, "success": False, "message": f"'{tool_name}' no esta disponible"}

    try:
        console.print(f"  [bold magenta]>[/bold magenta] {tool_name}({arguments})")

        expected_params = tool["params"]
        if not expected_params:
            result = func()
        elif len(expected_params) == 1:
            param_value = arguments.get(expected_params[0], list(arguments.values())[0] if arguments else "")
            if expected_params[0] in ("level", "seconds", "x", "y"):
                try:
                    param_value = int(param_value)
                except (ValueError, TypeError):
                    pass
            result = func(param_value)
        else:
            result = func(**arguments)

        status = "[green]OK[/green]" if result.get("success") else "[red]FALLO[/red]"
        console.print(f"  [bold magenta]>[/bold magenta] {status} {result.get('message', '')[:120]}")

        result["tool"] = tool_name
        return result

    except Exception as e:
        console.print(f"  [red]Error ejecutando {tool_name}: {e}[/red]")
        return {"tool": tool_name, "success": False, "message": str(e)}


class ToolExecutor:
    """Legacy: detecta y ejecuta herramientas en texto con regex [TOOL:...]."""

    TOOL_PATTERN = re.compile(
        r'\[TOOL:(\w+)\s*(\{(?:[^{}]|\{[^{}]*\})*\})\]',
        re.IGNORECASE | re.DOTALL,
    )

    def process_response(self, response: str) -> tuple[str, list[dict]]:
        results = []
        matches = list(self.TOOL_PATTERN.finditer(response))
        if not matches:
            return response, results

        for match in matches:
            tool_name = match.group(1).strip().lower()
            params_str = match.group(2).strip()
            params = self._parse_params_json(params_str)
            result = execute_tool_call(tool_name, params)
            results.append(result)

        clean_response = self.TOOL_PATTERN.sub("", response).strip()
        clean_response = re.sub(r'\s{2,}', ' ', clean_response).strip()

        if not clean_response:
            messages = [r["message"] for r in results]
            clean_response = " ".join(messages)

        return clean_response, results

    def _execute_tool(self, tool_name: str, params: dict) -> dict:
        return execute_tool_call(tool_name, params)

    def _parse_params_json(self, params_str: str) -> dict:
        if not params_str:
            return {}
        try:
            return json.loads(params_str)
        except json.JSONDecodeError:
            pass
        inner = params_str.strip()
        if inner.startswith("{") and inner.endswith("}"):
            inner = inner[1:-1].strip()
        try:
            return json.loads("{" + inner + "}")
        except json.JSONDecodeError:
            pass
        params = {}
        for part in re.finditer(r'(\w+)\s*[:=]\s*["\']?([^"\'",}]+)["\']?', inner):
            key = part.group(1).strip()
            value = part.group(2).strip()
            try:
                value = int(value)
            except ValueError:
                pass
            params[key] = value
        return params
