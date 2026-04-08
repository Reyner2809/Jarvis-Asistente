import re
import random
from . import pc_control


class FastCommandDetector:
    """
    Detecta comandos simples y los ejecuta INMEDIATAMENTE sin pasar por la IA.
    Solo los comandos que no necesitan razonamiento pasan por aqui.
    """

    # Respuestas variadas para que no suene robotico
    RESPONSES = {
        "open": [
            "Enseguida, senor.",
            "Abriendo ahora mismo.",
            "En camino.",
            "Listo, senor.",
            "Por supuesto.",
        ],
        "close": [
            "Cerrando ahora.",
            "Hecho, senor.",
            "Cerrado.",
            "Listo.",
        ],
        "media": [
            "Hecho.",
            "Listo, senor.",
            "Enseguida.",
        ],
        "search": [
            "Buscando ahora mismo.",
            "Enseguida, senor.",
            "Abriendo la busqueda.",
        ],
        "volume": [
            "Volumen ajustado.",
            "Listo, senor.",
        ],
        "system": [
            "Hecho, senor.",
            "Ejecutado.",
        ],
    }

    # Patrones de comandos rapidos
    PATTERNS = [
        # Spotify especifico (ANTES de abrir/buscar para que tenga prioridad)
        # Me gusta / favoritos / playlist favoritos
        (r"(?:pon|reproduce|reproducir|play).+(?:me gusta|liked|favorit|mis gustos|mis favorit)", "_handle_spotify_liked"),
        (r"(?:pon|reproduce|reproducir|play).+(?:playlist).+(?:favorit|me gusta)", "_handle_spotify_liked"),
        # Buscar en spotify: "busca en spotify la cancion llamada X"
        (r"(?:busca|buscar|buscame)\s+en\s+spotify\s+(?:la\s+)?(?:cancion|song|track)\s+(?:llamada?\s+|que\s+se\s+llama\s+)?(.+)", "_handle_spotify_search"),
        (r"(?:busca|buscar|buscame)\s+en\s+spotify\s+(?:el\s+)?(?:album|disco)\s+(?:llamado?\s+)?(.+)", "_handle_spotify_search"),
        (r"(?:busca|buscar|buscame)\s+en\s+spotify\s+(.+)", "_handle_spotify_search"),
        # "busca la cancion X en spotify"
        (r"(?:busca|buscar|buscame)\s+(?:la\s+)?(?:cancion|song|track)\s+(?:llamada?\s+|que\s+se\s+llama\s+)?(.+?)\s+en\s+spotify", "_handle_spotify_search"),
        (r"(?:busca|buscar|buscame)\s+(.+?)\s+en\s+spotify", "_handle_spotify_search"),
        # Reproducir algo en spotify: "pon X en spotify"
        (r"(?:pon|reproduce|reproducir|play|coloca|ponme)\s+(?:la\s+)?(?:cancion|song|track)\s+(?:llamada?\s+|que\s+se\s+llama\s+)?(.+?)\s+en\s+spotify", "_handle_spotify_search"),
        (r"(?:pon|reproduce|reproducir|play|coloca|ponme)\s+(?:el\s+)?(?:album|disco)\s+(?:llamado?\s+)?(.+?)\s+en\s+spotify", "_handle_spotify_search"),
        (r"(?:pon|reproduce|reproducir|play|coloca|ponme)\s+(.+?)\s+en\s+spotify", "_handle_spotify_search"),
        # "en spotify pon/busca X"
        (r"en\s+spotify\s+(?:pon|reproduce|busca|play)\s+(.+)", "_handle_spotify_search"),
        # "spotify pon/busca X"
        (r"spotify\s+(?:pon|reproduce|busca|play)\s+(.+)", "_handle_spotify_search"),
        # "pon la cancion X" (sin mencionar spotify, asume spotify)
        (r"(?:pon|reproduce|reproducir|play|ponme)\s+(?:la\s+)?(?:cancion|song|track)\s+(?:llamada?\s+|que\s+se\s+llama\s+)?(.+)", "_handle_spotify_search"),
        (r"(?:pon|reproduce|reproducir|play|ponme)\s+(?:el\s+)?(?:album|disco)\s+(?:llamado?\s+)?(.+)", "_handle_spotify_search"),
        (r"(?:pon|reproduce|reproducir|play|ponme)\s+(?:musica|music|algo)\s+de\s+(.+)", "_handle_spotify_search"),
        # Abrir aplicaciones
        (r"(?:abre|abrir|abreme|ejecuta|lanza|inicia|open)\s+(.+)", "_handle_open"),
        # Cerrar aplicaciones
        (r"(?:cierra|cerrar|cierrame|mata|close|kill)\s+(.+)", "_handle_close"),
        # Buscar en web
        (r"(?:busca|buscar|buscame|search|googlea)\s+(.+)", "_handle_search"),
        # Media controls
        (r"(?:pon|reproduce|play|reproducir)\s+(?:la\s+)?musica", "_handle_play"),
        (r"(?:pausa|pausar|pause|para|detener|deten)\s+(?:la\s+)?(?:musica|cancion|reproduccion)?", "_handle_play"),
        (r"(?:siguiente|next|salta|skip)\s+(?:cancion|track|tema)?", "_handle_next"),
        (r"(?:anterior|previous|prev|atras)\s+(?:cancion|track|tema)?", "_handle_prev"),
        # Volumen
        (r"(?:sube|subir|subele|aumenta).+volumen.*?(\d+)?", "_handle_volume_up"),
        (r"(?:baja|bajar|bajale|reduce|disminuye).+volumen.*?(\d+)?", "_handle_volume_down"),
        (r"(?:volumen|volume)\s+(?:a|al|en)?\s*(\d+)", "_handle_volume_set"),
        (r"(?:silencia|mute|mutea|silenciar)", "_handle_mute"),
        # Sistema
        (r"(?:que\s+hora|hora\s+es|dime\s+la\s+hora|que\s+hora\s+es)", "_handle_time"),
        (r"(?:captura|screenshot|pantallazo|captura\s+de\s+pantalla)", "_handle_screenshot"),
        # Bloquear PC
        (r"(?:bloquea|bloquear|lock)\s+(?:el\s+)?(?:pc|computador|equipo|computadora|ordenador)", "_handle_lock"),
        (r"(?:bloquea|bloquear|lock)\s+(?:la\s+)?(?:pantalla|sesion|screen)", "_handle_lock"),
        (r"bloquea(?:lo|te)?$", "_handle_lock"),
        # Apagar / reiniciar / suspender
        (r"(?:apaga|apagar)\s+(?:el\s+)?(?:pc|computador|equipo|computadora|ordenador)", "_handle_shutdown"),
        (r"(?:apaga|apagar)(?:lo|te)?$", "_handle_shutdown"),
        (r"(?:reinicia|reiniciar|restart)\s+(?:el\s+)?(?:pc|computador|equipo|computadora|ordenador)", "_handle_restart"),
        (r"(?:reinicia|reiniciar|restart)(?:lo|te)?$", "_handle_restart"),
        (r"(?:suspende|suspender|dormir|duerme|sleep)\s+(?:el\s+)?(?:pc|computador|equipo|computadora|ordenador)", "_handle_sleep"),
        (r"(?:hiberna|hibernar|hibernate)\s+(?:el\s+)?(?:pc|computador|equipo|computadora|ordenador)", "_handle_hibernate"),
        (r"(?:cierra|cerrar)\s+(?:la\s+)?sesion", "_handle_logoff"),
        (r"(?:cancela|cancelar)\s+(?:el\s+)?(?:apagado|reinicio|shutdown|restart)", "_handle_cancel_shutdown"),
        # Escribir texto
        (r"(?:escribe|escribir|escribeme|teclea|tipea)\s+[\"'](.+?)[\"']", "_handle_type_text"),
        (r"(?:escribe|escribir|escribeme|teclea|tipea)\s+(.+)", "_handle_type_text"),
        # Click
        (r"(?:haz\s+)?click\s+(?:en\s+)?(?:el\s+)?(.+)", "_handle_click_info"),
        # Presionar teclas
        (r"(?:presiona|pulsa|press)\s+(.+)", "_handle_press_key"),
        # CATCH-ALL: "reproduce/pon X" que no matcheo nada -> busca en Spotify
        (r"(?:pon|reproduce|reproducir|play|ponme|coloca)\s+(.+)", "_handle_spotify_catch_all"),
    ]

    def __init__(self):
        self._compiled = [(re.compile(p, re.IGNORECASE), h) for p, h in self.PATTERNS]

    def _random_response(self, category: str) -> str:
        return random.choice(self.RESPONSES.get(category, self.RESPONSES["system"]))

    def try_execute(self, user_input: str) -> tuple[bool, str]:
        """
        Intenta ejecutar un comando rapido.
        Retorna (handled: bool, response: str).
        Si handled es False, el mensaje debe ir a la IA.
        """
        text = user_input.strip()

        # Quitar "jarvis" del inicio (el usuario puede decir "Jarvis abre spotify")
        text_clean = re.sub(r'^(?:jarvis|hey\s+jarvis|oye\s+jarvis|oye|hey)[,.\s]*', '', text, flags=re.IGNORECASE).strip()
        if text_clean:
            text = text_clean

        for pattern, handler_name in self._compiled:
            match = pattern.search(text)
            if match:
                handler = getattr(self, handler_name)
                result = handler(match)
                if result is not None:
                    return True, result

        return False, ""

    def _handle_open(self, match) -> str | None:
        target = match.group(1).strip().rstrip(".")

        # Detectar si es una web
        web_keywords = {
            "youtube": "youtube.com",
            "google": "google.com",
            "gmail": "mail.google.com",
            "twitter": "twitter.com",
            "x": "x.com",
            "facebook": "facebook.com",
            "instagram": "instagram.com",
            "github": "github.com",
            "whatsapp web": "web.whatsapp.com",
            "chatgpt": "chat.openai.com",
            "linkedin": "linkedin.com",
            "reddit": "reddit.com",
            "twitch": "twitch.tv",
            "netflix": "netflix.com",
            "amazon": "amazon.com",
            "mercadolibre": "mercadolibre.com",
        }

        target_lower = target.lower()
        for key, url in web_keywords.items():
            if key in target_lower:
                result = pc_control.open_website(url)
                if result["success"]:
                    return f"{self._random_response('open')} {key.capitalize()} abierto."
                return f"No pude abrir {key}."

        # Es una app
        result = pc_control.open_application(target)
        if result["success"]:
            return f"{self._random_response('open')} {target.capitalize()} abierto."
        return None  # Dejar que la IA maneje si no se pudo

    def _handle_close(self, match) -> str:
        target = match.group(1).strip().rstrip(".")
        result = pc_control.close_application(target)
        if result["success"]:
            return f"{self._random_response('close')} {target.capitalize()} cerrado."
        return f"No encontre {target} ejecutandose."

    def _handle_search(self, match) -> str:
        query = match.group(1).strip().rstrip(".")
        # Limpiar prefijos comunes
        for prefix in ["en google ", "en internet ", "en la web "]:
            if query.startswith(prefix):
                query = query[len(prefix):]
        result = pc_control.search_web(query)
        return f"{self._random_response('search')} Buscando: {query}"

    def _handle_play(self, match) -> str:
        pc_control.media_play_pause()
        return self._random_response("media")

    def _handle_next(self, match) -> str:
        pc_control.media_next()
        return f"{self._random_response('media')} Siguiente cancion."

    def _handle_prev(self, match) -> str:
        pc_control.media_previous()
        return f"{self._random_response('media')} Cancion anterior."

    def _handle_spotify_liked(self, match) -> str:
        # Buscar "liked songs" en Spotify usando el mismo metodo que funciona
        return self._spotify_search_and_play("liked songs")

    def _clean_spotify_query(self, raw: str) -> str:
        """Limpia el texto para obtener solo el nombre de la cancion/album/artista.

        Ejemplos:
        - "la cancion llamada Lloraras de Oscar d'leon" -> "Lloraras de Oscar d'leon"
        - "el album Thriller de Michael Jackson" -> "Thriller de Michael Jackson"
        - "musica de Bad Bunny" -> "Bad Bunny"
        - "algo de reggaeton" -> "reggaeton"
        - "Lloraras de Oscar d'leon en spotify" -> "Lloraras de Oscar d'leon"
        """
        query = raw.strip().strip('"\'.,;:!?')
        query_lower = query.lower()

        # Limpiar "en spotify" al final PRIMERO
        for suffix in [" en spotify", " de spotify", " en el spotify"]:
            if query_lower.endswith(suffix):
                query = query[:len(query) - len(suffix)].strip()
                query_lower = query.lower()

        # Prefijos que son puro ruido (el contenido real viene despues)
        noise_prefixes = [
            "la cancion llamada ", "la cancion que se llama ",
            "cancion llamada ", "cancion que se llama ",
            "el album llamado ", "el album que se llama ",
            "album llamado ", "album que se llama ",
            "el disco llamado ", "el disco que se llama ",
            "que se llama ", "llamada ", "llamado ",
        ]
        for prefix in noise_prefixes:
            if query_lower.startswith(prefix):
                query = query[len(prefix):]
                return query.strip().strip('"\'.,;:!?')

        # Prefijos que indican "busca esto DE artista" -> mantener todo
        # "la cancion X de Y" -> "X de Y" (mantener "de Y" porque es el artista)
        content_prefixes = [
            "la cancion ", "cancion ", "el tema ", "tema ",
            "el track ", "track ", "la song ", "song ",
            "el album ", "album ", "el disco ", "disco ",
            "la playlist ", "playlist ",
        ]
        for prefix in content_prefixes:
            if query_lower.startswith(prefix):
                query = query[len(prefix):]
                return query.strip().strip('"\'.,;:!?')

        # "musica de X" o "algo de X" -> solo X (el artista)
        for prefix in ["musica de ", "algo de ", "music de ", "canciones de "]:
            if query_lower.startswith(prefix):
                query = query[len(prefix):]
                return query.strip().strip('"\'.,;:!?')

        return query.strip().strip('"\'.,;:!?')

    def _spotify_search_and_play(self, query: str) -> str:
        """Busca en Spotify y lo reproduce."""
        if not query:
            return "No entendi que buscar en Spotify. Dime el nombre de la cancion o artista."

        result = pc_control.spotify_search_and_play(query)
        if result["success"]:
            return f"{self._random_response('media')} Reproduciendo '{query}' en Spotify."
        return f"No pude buscar en Spotify: {result['message']}"

    def _handle_spotify_search(self, match) -> str:
        query = self._clean_spotify_query(match.group(1))
        return self._spotify_search_and_play(query)

    def _handle_spotify_play(self, match) -> str:
        pc_control.media_play_pause()
        return f"{self._random_response('media')} Reproduciendo en Spotify."

    def _handle_spotify_catch_all(self, match) -> str:
        """Catch-all: cualquier 'reproduce/pon X' que no matcheo nada mas -> Spotify."""
        raw = match.group(1).strip()
        # Ignorar si es "musica" sola (eso es play/pause)
        if raw.lower().strip() in ["musica", "la musica", "music"]:
            pc_control.media_play_pause()
            return self._random_response("media")
        query = self._clean_spotify_query(raw)
        if query:
            return self._spotify_search_and_play(query)
        return None

    def _handle_volume_up(self, match) -> str:
        level = match.group(1)
        if level:
            pc_control.set_volume(int(level))
            return f"{self._random_response('volume')} Volumen al {level}%."
        pc_control.set_volume(80)
        return f"{self._random_response('volume')} Volumen subido."

    def _handle_volume_down(self, match) -> str:
        level = match.group(1)
        if level:
            pc_control.set_volume(int(level))
            return f"{self._random_response('volume')} Volumen al {level}%."
        pc_control.set_volume(30)
        return f"{self._random_response('volume')} Volumen bajado."

    def _handle_volume_set(self, match) -> str:
        level = int(match.group(1))
        pc_control.set_volume(level)
        return f"{self._random_response('volume')} Volumen al {level}%."

    def _handle_mute(self, match) -> str:
        pc_control.mute_volume()
        return f"{self._random_response('media')} Sonido silenciado."

    def _handle_time(self, match) -> str:
        result = pc_control.get_datetime()
        return f"Son las {result['message']}, senor."

    def _handle_screenshot(self, match) -> str:
        result = pc_control.take_screenshot()
        if result["success"]:
            return f"{self._random_response('system')} {result['message']}"
        return "No pude tomar la captura."

    def _handle_lock(self, match) -> str:
        pc_control.lock_pc()
        return "Bloqueando el equipo, senor."

    def _handle_shutdown(self, match) -> str:
        result = pc_control.shutdown_pc("shutdown")
        return f"Entendido, senor. {result['message']}"

    def _handle_restart(self, match) -> str:
        result = pc_control.shutdown_pc("restart")
        return f"Entendido, senor. {result['message']}"

    def _handle_sleep(self, match) -> str:
        result = pc_control.shutdown_pc("sleep")
        return f"{self._random_response('system')} {result['message']}"

    def _handle_hibernate(self, match) -> str:
        result = pc_control.shutdown_pc("hibernate")
        return f"{self._random_response('system')} {result['message']}"

    def _handle_logoff(self, match) -> str:
        result = pc_control.shutdown_pc("logoff")
        return f"{self._random_response('system')} {result['message']}"

    def _handle_cancel_shutdown(self, match) -> str:
        result = pc_control.shutdown_pc("cancel")
        return f"{self._random_response('system')} {result['message']}"

    def _handle_type_text(self, match) -> str | None:
        text = match.group(1).strip()
        if not text:
            return None
        try:
            import pyautogui
            import time
            time.sleep(0.5)
            pyautogui.typewrite(text, interval=0.02) if text.isascii() else pyautogui.write(text)
            return f"{self._random_response('system')} Texto escrito."
        except ImportError:
            return None  # Dejar a la IA
        except Exception:
            return None

    def _handle_click_info(self, match) -> str:
        return "No puedo identificar donde hacer click sin ver la pantalla. Puedo hacer click en coordenadas especificas si me das la posicion X,Y."

    def _handle_press_key(self, match) -> str | None:
        key = match.group(1).strip().lower()
        key_map = {
            "enter": "enter", "intro": "enter",
            "escape": "escape", "esc": "escape",
            "tab": "tab", "tabulador": "tab",
            "espacio": "space", "space": "space",
            "borrar": "backspace", "backspace": "backspace", "delete": "delete",
            "f1": "f1", "f2": "f2", "f3": "f3", "f4": "f4", "f5": "f5",
            "f11": "f11", "f12": "f12",
        }
        mapped = key_map.get(key)
        if mapped:
            try:
                import pyautogui
                pyautogui.press(mapped)
                return f"{self._random_response('system')} Tecla {key} presionada."
            except ImportError:
                return None
        return None
