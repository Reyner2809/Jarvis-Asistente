"""
Intent Router: clasificador de intenciones ultraligero.

En vez de depender de regex para cada variacion de comando, envía una
llamada minima a Ollama (~1-2s) que decide si el input del usuario es
una ACCION (tool call) o una PREGUNTA (conversacion). Si es accion,
devuelve el tool call listo para ejecutar.

Flujo:  usuario -> IntentRouter -> tool_call | None
Si devuelve tool_call: se ejecuta directo sin pasar por la IA completa.
Si devuelve None: el input va al SLOW PATH (IA conversacional).
"""

import json
import logging
import urllib.request

from config import Config

log = logging.getLogger("jarvis.intent_router")

INTENT_PROMPT = """Clasificador de intenciones. Decide si es ACCION o PREGUNTA. Responde SOLO JSON.

ACCIONES:
- open_app(app_name): abrir app
- close_app(app_name): cerrar app
- open_website(url): abrir pagina web
- search_web(query): buscar en google
- open_and_search(app_or_url, search_text): abrir app/web Y buscar algo (youtube, github, etc)
- media_play: play/pausa
- media_next: siguiente
- media_prev: anterior
- set_volume(level): volumen 0-100
- mute: silenciar
- lock_pc: bloquear pc
- shutdown(action): shutdown/restart/sleep/cancel
- screenshot: captura pantalla
- analyze_screenshot: ver que hay en pantalla
- datetime: hora/fecha
- spotify_search(query): reproducir algo en SPOTIFY
- whatsapp_send(contact, message): mensaje whatsapp
- knowledge_search(query): buscar en documentos
- execute_code(code): ejecutar python
- schedule_reminder(message, time_description): programar recordatorio
- remember(fact, category): guardar dato del usuario en memoria

REGLAS CRITICAS:
- Responde SOLO: {"tool":"nombre","params":{...}} o {"tool":"none"}
- "en youtube pon/coloca/busca X" = open_and_search(app_or_url="youtube.com", search_text=X)
- "busca en google X" = search_web(query=X)
- "pon/reproduce X" SIN mencionar plataforma = spotify_search(query=X)
- "pon/reproduce X en youtube" = open_and_search(app_or_url="youtube.com", search_text=X)
- "abre youtube/instagram/twitter" = open_website(url="youtube.com"/"instagram.com"/etc)
- "pausa/para/detente" = media_play
- PREGUNTA/conversacion = {"tool":"none"}
- Limpia articulos: "la calculadora" -> "calculadora"

EJEMPLOS:
"en youtube coloca un video random" -> {"tool":"open_and_search","params":{"app_or_url":"youtube.com","search_text":"video random"}}
"reproduce el regente" -> {"tool":"spotify_search","params":{"query":"el regente"}}
"pon el regente en youtube" -> {"tool":"open_and_search","params":{"app_or_url":"youtube.com","search_text":"el regente"}}
"abre chrome" -> {"tool":"open_app","params":{"app_name":"chrome"}}
"pausa" -> {"tool":"media_play","params":{}}
"busca en google recetas" -> {"tool":"search_web","params":{"query":"recetas"}}
"manda whatsapp a juan diciendo hola" -> {"tool":"whatsapp_send","params":{"contact":"juan","message":"hola"}}
"recuerdame en 30 minutos sacar la comida" -> {"tool":"schedule_reminder","params":{"message":"sacar la comida","time_description":"en 30 minutos"}}
"avisame a las 5pm que tengo reunion" -> {"tool":"schedule_reminder","params":{"message":"tengo reunion","time_description":"a las 5pm"}}
"todos los dias a las 9am recuerdame la reunion" -> {"tool":"schedule_reminder","params":{"message":"la reunion del trabajo","time_description":"todos los dias a las 9am"}}
"cada lunes a las 8am dime las noticias" -> {"tool":"schedule_reminder","params":{"message":"revisar las noticias","time_description":"cada lunes a las 8am"}}
"de lunes a viernes a las 7am despiertame" -> {"tool":"schedule_reminder","params":{"message":"hora de despertar","time_description":"de lunes a viernes a las 7am"}}
"recuerda que mi color favorito es azul" -> {"tool":"remember","params":{"fact":"El color favorito del usuario es azul","category":"preferencia"}}
"cuanto es 2+2" -> {"tool":"none"}
"como estas" -> {"tool":"none"}"""


class IntentRouter:
    """Clasificador de intenciones con Ollama."""

    def __init__(self):
        self._base_url = "http://localhost:11434"

    def classify(self, user_input: str) -> dict | None:
        """
        Clasifica el input del usuario.
        Devuelve dict con 'tool' y 'params' si es una accion.
        Devuelve None si es conversacion o si hubo error.
        """
        try:
            payload = json.dumps({
                "model": Config.OLLAMA_MODEL,
                "messages": [
                    {"role": "system", "content": INTENT_PROMPT},
                    {"role": "user", "content": user_input},
                ],
                "stream": False,
                "options": {
                    "num_predict": 100,
                    "temperature": 0.1,
                },
            }).encode("utf-8")

            req = urllib.request.Request(
                f"{self._base_url}/api/chat",
                data=payload,
                headers={"Content-Type": "application/json"},
            )

            with urllib.request.urlopen(req, timeout=15) as resp:
                data = json.loads(resp.read().decode("utf-8"))

            raw = data["message"]["content"].strip()
            return self._parse_response(raw)

        except Exception as e:
            log.debug("IntentRouter error: %s", e)
            return None

    def _parse_response(self, raw: str) -> dict | None:
        """Parsea la respuesta JSON del clasificador."""
        # Limpiar markdown si viene envuelto en ```json ... ```
        raw = raw.strip()
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[-1].rsplit("```", 1)[0].strip()

        try:
            result = json.loads(raw)
        except json.JSONDecodeError:
            # Intentar extraer JSON de la respuesta
            import re
            match = re.search(r'\{[^{}]+\}', raw)
            if match:
                try:
                    result = json.loads(match.group())
                except json.JSONDecodeError:
                    return None
            else:
                return None

        tool = result.get("tool", "none")
        if tool == "none" or not tool:
            return None

        return {
            "tool": tool,
            "params": result.get("params", {}),
        }
