import json
import re
from rich.console import Console
from . import pc_control
from . import automation

console = Console()

# Mapeo de herramientas disponibles
TOOLS = {
    "open_app": {
        "function": pc_control.open_application,
        "description": "Abre una app (spotify, chrome, notepad, word, excel, vscode, etc.)",
        "params": ["app_name"],
    },
    "close_app": {
        "function": pc_control.close_application,
        "description": "Cierra una app",
        "params": ["app_name"],
    },
    "open_website": {
        "function": pc_control.open_website,
        "description": "Abre una web",
        "params": ["url"],
    },
    "search_web": {
        "function": pc_control.search_web,
        "description": "Busca en Google",
        "params": ["query"],
    },
    "datetime": {
        "function": pc_control.get_datetime,
        "description": "Fecha y hora actual",
        "params": [],
    },
    "set_volume": {
        "function": pc_control.set_volume,
        "description": "Volumen del sistema (0-100)",
        "params": ["level"],
    },
    "mute": {
        "function": pc_control.mute_volume,
        "description": "Silenciar/activar sonido",
        "params": [],
    },
    "screenshot": {
        "function": pc_control.take_screenshot,
        "description": "Captura de pantalla",
        "params": [],
    },
    "lock_pc": {
        "function": pc_control.lock_pc,
        "description": "Bloquea el PC",
        "params": [],
    },
    "shutdown": {
        "function": pc_control.shutdown_pc,
        "description": "Apaga/reinicia PC (action: shutdown, restart, cancel)",
        "params": ["action"],
    },
    "open_folder": {
        "function": pc_control.open_folder,
        "description": "Abre carpeta en explorador",
        "params": ["path"],
    },
    "media_play": {
        "function": pc_control.media_play_pause,
        "description": "Play/Pausa musica",
        "params": [],
    },
    "media_next": {
        "function": pc_control.media_next,
        "description": "Siguiente cancion",
        "params": [],
    },
    "media_prev": {
        "function": pc_control.media_previous,
        "description": "Cancion anterior",
        "params": [],
    },
    "spotify_play": {
        "function": pc_control.spotify_play,
        "description": "Reproduce en Spotify. uri: spotify:collection:tracks (me gusta)",
        "params": ["uri"],
    },
    "type_text": {
        "function": automation.type_text,
        "description": "Escribe texto donde esta el cursor",
        "params": ["text"],
    },
    "press_key": {
        "function": automation.press_key,
        "description": "Presiona tecla (enter, escape, tab, f5, etc.)",
        "params": ["key"],
    },
    "hotkey": {
        "function": automation.hotkey,
        "description": "Combinacion de teclas (ctrl+c, alt+f4, ctrl+shift+n)",
        "params": ["keys"],
    },
    "click": {
        "function": automation.click_at,
        "description": "Click en coordenada X,Y",
        "params": ["x", "y"],
    },
    "create_folder": {
        "function": automation.create_folder,
        "description": "Crea una carpeta",
        "params": ["path"],
    },
    "create_file": {
        "function": automation.create_file,
        "description": "Crea un archivo con contenido",
        "params": ["path", "content"],
    },
    "run_cmd": {
        "function": automation.run_command,
        "description": "Ejecuta comando en terminal",
        "params": ["command"],
    },
    "open_and_search": {
        "function": automation.open_and_search,
        "description": "Abre app/web y busca algo (youtube, google, github, etc.)",
        "params": ["app_or_url", "search_text"],
    },
}


def get_tools_prompt() -> str:
    """Genera la descripcion de herramientas para el system prompt de la IA."""
    tools_desc = []
    for name, tool in TOOLS.items():
        params = ", ".join(tool["params"]) if tool["params"] else ""
        tools_desc.append(f'  - {name}({params}): {tool["description"]}')

    return "\n".join(tools_desc)


class ToolExecutor:
    """Detecta y ejecuta herramientas en las respuestas de la IA."""

    TOOL_PATTERN = re.compile(
        r'\[TOOL:(\w+)\s*\{([^}]*)\}\]',
        re.IGNORECASE,
    )

    def process_response(self, response: str) -> tuple[str, list[dict]]:
        results = []
        matches = list(self.TOOL_PATTERN.finditer(response))

        if not matches:
            return response, results

        for match in matches:
            tool_name = match.group(1).strip().lower()
            params_str = match.group(2).strip()
            params = self._parse_params(params_str)
            result = self._execute_tool(tool_name, params)
            results.append(result)

        clean_response = self.TOOL_PATTERN.sub("", response).strip()
        # Limpiar espacios dobles
        clean_response = re.sub(r'\s{2,}', ' ', clean_response).strip()

        if not clean_response:
            messages = [r["message"] for r in results]
            clean_response = " ".join(messages)

        return clean_response, results

    def _parse_params(self, params_str: str) -> dict:
        if not params_str:
            return {}

        try:
            return json.loads("{" + params_str + "}")
        except json.JSONDecodeError:
            pass

        params = {}
        for part in re.finditer(r'(\w+)\s*[:=]\s*["\']?([^"\'",}]+)["\']?', params_str):
            key = part.group(1).strip()
            value = part.group(2).strip()
            try:
                value = int(value)
            except ValueError:
                pass
            params[key] = value

        return params

    def _execute_tool(self, tool_name: str, params: dict) -> dict:
        if tool_name not in TOOLS:
            return {"tool": tool_name, "success": False, "message": f"Herramienta '{tool_name}' no existe"}

        tool = TOOLS[tool_name]
        func = tool["function"]

        try:
            console.print(f"  [bold magenta]>[/bold magenta] {tool_name} {params}")

            expected_params = tool["params"]
            if not expected_params:
                result = func()
            elif len(expected_params) == 1:
                param_value = params.get(expected_params[0], list(params.values())[0] if params else "")
                result = func(param_value)
            else:
                result = func(**params)

            status = "[green]OK[/green]" if result.get("success") else "[red]FALLO[/red]"
            console.print(f"  [bold magenta]>[/bold magenta] {status} {result.get('message', '')}")

            result["tool"] = tool_name
            return result

        except Exception as e:
            console.print(f"  [red]Error ejecutando {tool_name}: {e}[/red]")
            return {"tool": tool_name, "success": False, "message": str(e)}
