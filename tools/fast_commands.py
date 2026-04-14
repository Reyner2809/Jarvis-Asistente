import re
import os
import random
from . import pc_control
from .code_executor import execute_code


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

    # Verbos sinonimos para abrir aplicaciones (regex-grupo, no-capturador)
    # Cubre: abre, abreme, ejecuta, ejecutame, lanza, lanzame, inicia, iniciame,
    # arranca, corre, prende, enciende, activa, levanta, dame, sacame, ponme,
    # mas formas en infinitivo (abrir, ejecutar, etc.)
    # Nota: 'ponme' se omite aqui porque es ambiguo ("ponme una cancion" no es
    # abrir). El compound pattern ya lo captura cuando viene con "y pon/busca".
    _OPEN_VERBS = (
        r"(?:abre|abreme|abrir|ejecuta|ejecutame|ejecutar|lanza|lanzame|lanzar|"
        r"inicia|iniciame|iniciar|arranca|arrancame|arrancar|corre|correme|correr|"
        r"prende|prendeme|prender|enciende|enciendeme|encender|activa|activame|activar|"
        r"levanta|levantame|levantar|dame|sacame|abremela|abremelo|"
        r"podrias\s+abrir|puedes\s+abrir|necesito|quiero)"
    )
    # Verbos sinonimos para cerrar
    _CLOSE_VERBS = (
        r"(?:cierra|cierrame|cierralo|cierramela|cerrar|"
        r"termina|terminame|terminar|finaliza|finalizame|finalizar|"
        r"mata|matame|matar|kill|quita|quitame|quitar)"
    )
    # Verbos sinonimos para reproducir (compuestos con spotify/youtube)
    _PLAY_VERBS = (
        r"(?:pon|ponme|reproduce|reproducir|coloca|colocame|busca|buscame|play|"
        r"escucha|escuchame|tocame|toca|tira|tirame|sueltame|suelta|dame|"
        r"ponle|metele|cantame)"
    )

    # Patrones de comandos rapidos
    # FAST COMMANDS: patrones que cubren acciones simples sin razonamiento.
    # Ordenados de MAS especifico a MAS general — el primero que matchea gana.
    PATTERNS = [
        # === ACCIONES COMPUESTAS GENERICAS (deben ir ANTES del open_app simple) ===
        # "abre/ejecuta/lanza <APP> y <VERBO> <CONTENIDO>"
        # Captura: (app, verbo_accion, contenido). El handler decide que tool usar.
        # Ejemplos:
        #   "ejecuta spotify y pon EL REGENTE"  -> spotify_search(EL REGENTE)
        #   "abre youtube y pon Bad Bunny"      -> open_and_search(youtube, Bad Bunny)
        #   "lanza chrome y busca recetas"      -> open_and_search(chrome, recetas) o search_web
        (rf"^{_OPEN_VERBS}\s+(?:la\s+|el\s+|los\s+|las\s+|mi\s+|me\s+)?(?:app\s+|aplicacion\s+|programa\s+|web\s+|pagina\s+)?(.+?)(?:\s+y\s+|\s*,\s*)({_PLAY_VERBS}|busca|buscame|search|escribe|escribeme)\s+(.+)", "_handle_open_compound"),

        # === SPOTIFY EXPLICITO (solo cuando menciona "spotify" textualmente) ===
        (r"(?:pon|reproduce|reproducir|play|busca|coloca|ponme).+(?:me gusta|liked|favorit|mis gustos).*(?:en\s+)?spotify", "_handle_spotify_liked"),
        (r"(?:busca|buscar|buscame)\s+en\s+spotify\s+(.+)", "_handle_spotify_search"),
        (r"(?:pon|reproduce|play|coloca|ponme)\s+(.+?)\s+en\s+spotify", "_handle_spotify_search"),
        (r"en\s+spotify\s+(?:pon|reproduce|busca|play)\s+(.+)", "_handle_spotify_search"),
        (r"spotify\s+(?:pon|reproduce|busca|play)\s+(.+)", "_handle_spotify_search"),
        # Media controls (inequivocos, no necesitan contexto)
        (r"(?:pon|reproduce|play|reproducir)\s+(?:la\s+)?musica$", "_handle_play"),
        (r"(?:pausa|pausar|pause|para|detener|deten|stop|detente)(?:\s+(?:la\s+)?(?:musica|cancion|reproduccion|todo))?$", "_handle_play"),
        (r"(?:siguiente|next|salta|skip)(?:\s+(?:cancion|track|tema))?$", "_handle_next"),
        (r"(?:anterior|previous|prev|atras)(?:\s+(?:cancion|track|tema))?$", "_handle_prev"),
        # Volumen (inequivoco)
        (r"(?:sube|subir|subele|aumenta).+volumen.*?(\d+)?", "_handle_volume_up"),
        (r"(?:baja|bajar|bajale|reduce|disminuye).+volumen.*?(\d+)?", "_handle_volume_down"),
        (r"(?:volumen|volume)\s+(?:a|al|en)?\s*(\d+)", "_handle_volume_set"),
        (r"(?:silencia|mute|mutea|silenciar)$", "_handle_mute"),
        # Hora (inequivoco)
        (r"(?:que\s+hora|hora\s+es|dime\s+la\s+hora|que\s+hora\s+es)", "_handle_time"),
        # Captura de pantalla (inequivoco)
        (r"(?:captura|screenshot|pantallazo|captura\s+de\s+pantalla)", "_handle_screenshot"),
        # Grabar pantalla
        (r"(?:graba|grabar|record)\s+(?:los\s+)?(?:ultimos|últimos)\s+(\d+)\s+(?:segundos|seg|s)", "_handle_record"),
        (r"(?:graba|grabar|record)\s+(?:la\s+)?(?:pantalla|screen)(?:\s+(\d+)\s+(?:segundos|seg|s))?", "_handle_record"),
        (r"(?:graba|grabar|record)\s+(\d+)\s+(?:segundos|seg|s)", "_handle_record"),
        # Bloquear PC (inequivoco)
        (r"(?:bloquea|bloquear|lock)\s+(?:el\s+|la\s+|mi\s+)?(?:pc|computador|equipo|computadora|ordenador|compu|laptop|portatil|pantalla|sesion|screen)", "_handle_lock"),
        (r"bloquea(?:lo|la|te)?$", "_handle_lock"),
        # Apagar / reiniciar (inequivoco)
        (r"(?:apaga|apagar)\s+(?:el\s+)?(?:pc|computador|equipo|computadora|ordenador)", "_handle_shutdown"),
        (r"(?:apaga|apagar)(?:lo|te)?$", "_handle_shutdown"),
        (r"(?:reinicia|reiniciar|restart)\s+(?:el\s+)?(?:pc|computador|equipo|computadora|ordenador)", "_handle_restart"),
        (r"(?:reinicia|reiniciar|restart)(?:lo|te)?$", "_handle_restart"),
        (r"(?:suspende|suspender|dormir|duerme|sleep)\s+(?:el\s+)?(?:pc|computador|equipo|computadora|ordenador)", "_handle_sleep"),
        (r"(?:hiberna|hibernar|hibernate)\s+(?:el\s+)?(?:pc|computador|equipo|computadora|ordenador)", "_handle_hibernate"),
        (r"(?:cierra|cerrar)\s+(?:la\s+)?sesion", "_handle_logoff"),
        (r"(?:cancela|cancelar)\s+(?:el\s+)?(?:apagado|reinicio|shutdown|restart)", "_handle_cancel_shutdown"),
        # Presentacion (inequivoco)
        (r"(?:presentate|preséntate|quien\s+eres|quién\s+eres|como\s+te\s+llamas|cómo\s+te\s+llamas|que\s+eres|qué\s+eres|dime\s+quien\s+eres|tu\s+nombre)", "_handle_introduce"),

        # === ABRIR / CERRAR APP (catch-all al FINAL) ===
        # Abrir cualquier app: "abre X", "ejecuta X", "lanza X", "inicia X", etc.
        # Se evalua despues de los patrones especificos (spotify, youtube, etc.)
        # Si la app no existe, _handle_open retorna None y cae al IA.
        (rf"^{_OPEN_VERBS}\s+(?:la\s+|el\s+|los\s+|las\s+|mi\s+|me\s+)?(?:app\s+|aplicacion\s+|programa\s+)?(.+)", "_handle_open"),
        # Cerrar app (excluye pc/sesion que tienen sus propios patrones de shutdown/logoff arriba)
        (rf"^{_CLOSE_VERBS}\s+(?:la\s+|el\s+|los\s+|las\s+|mi\s+|me\s+)?(?:app\s+|aplicacion\s+|programa\s+|ventana\s+(?:de\s+)?)?(?!(?:el\s+|la\s+)?(?:pc|computador|computadora|equipo|ordenador|sesion|sesión)\b)(.+)", "_handle_close"),
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

    # Mapa de sitios web conocidos para resolver app -> URL en handlers compuestos
    _WEB_KEYWORDS = {
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

    def _handle_open(self, match) -> str | None:
        raw_target = match.group(1).strip().rstrip(".")
        # Limpia articulos ('la calculadora' -> 'calculadora', 'a chrome' -> 'chrome')
        target = pc_control._clean_app_name(raw_target) or raw_target
        target_lower = target.lower()

        for key, url in self._WEB_KEYWORDS.items():
            if key in target_lower:
                result = pc_control.open_website(url)
                if result["success"]:
                    return f"{self._random_response('open')} {key.capitalize()} abierto."
                return f"No pude abrir {key}."

        # Es una app - buscar en todo el sistema
        result = pc_control.find_and_open_app(target)
        if result["success"]:
            return f"{self._random_response('open')} {target.capitalize()} abierto."
        return None  # Dejar que la IA maneje si no se pudo

    def _handle_open_compound(self, match) -> str | None:
        """
        Maneja "abre/ejecuta <APP> y <VERBO> <CONTENIDO>" para CUALQUIER app.
        Decide la accion correcta segun la app y el verbo:
          - Spotify + play_verb -> spotify_search (Spotify se abre solo)
          - Sitio web (youtube, github, etc.) + verb -> open_and_search
          - App desktop (chrome, brave) + busca -> open app + search_web
          - Cualquier app + escribe -> open app + type_text
        Si no puede resolver, retorna None y deja al IA.
        """
        from . import automation
        import time

        raw_app = match.group(1).strip().rstrip(",.")
        verb = match.group(2).strip().lower()
        content = match.group(3).strip().rstrip(".")
        if not content:
            return None

        # Limpia articulos
        app = pc_control._clean_app_name(raw_app) or raw_app
        app_lower = app.lower()

        # Verbo "escribe X" -> abrir app y tipear
        if verb in ("escribe", "escribeme"):
            open_result = pc_control.find_and_open_app(app)
            if not open_result.get("success"):
                # Probar como web
                for key, url in self._WEB_KEYWORDS.items():
                    if key in app_lower:
                        pc_control.open_website(url)
                        open_result = {"success": True}
                        break
            if not open_result.get("success"):
                return None
            time.sleep(1.5)  # esperar a que la app abra
            try:
                automation.type_text(content)
            except Exception:
                return None
            return f"{self._random_response('open')} {app.capitalize()} abierto y texto escrito."

        # Spotify: spotify_search ya abre Spotify automaticamente
        if "spotify" in app_lower:
            return self._spotify_search_and_play(content)

        # Sitios web conocidos (youtube, github, google, etc.) -> open_and_search
        for key, url in self._WEB_KEYWORDS.items():
            if key in app_lower:
                try:
                    result = automation.open_and_search(url, content)
                    if result.get("success"):
                        return f"{self._random_response('open')} {key.capitalize()} abierto, buscando '{content}'."
                except Exception:
                    pass
                return None

        # App desktop (chrome, brave, firefox) + busca -> abrir y buscar en Google
        if verb in ("busca", "buscame", "search"):
            open_result = pc_control.find_and_open_app(app)
            if open_result.get("success"):
                time.sleep(1.0)
                pc_control.search_web(content)
                return f"{self._random_response('search')} {app.capitalize()} abierto, buscando '{content}'."
            return None

        # No supimos resolver el compuesto -> dejar al IA
        return None

    def _handle_whatsapp_send(self, match) -> str | None:
        contact = match.group(1).strip().rstrip(".,")
        message = match.group(2).strip().rstrip(".")
        # Quitar comillas accidentales
        contact = contact.strip('"\'')
        message = message.strip('"\'')
        if not contact or not message:
            return None
        result = pc_control.whatsapp_send_message(contact, message)
        if result["success"]:
            return f"Listo, senor. Mensaje enviado a {contact} por WhatsApp."
        return f"No pude enviar el mensaje: {result['message']}"

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

    def _handle_record(self, match) -> str:
        seconds = 30
        for g in match.groups():
            if g and g.isdigit():
                seconds = int(g)
                break
        result = pc_control.record_screen(seconds)
        if result["success"]:
            return f"{self._random_response('system')} {result['message']}"
        return result["message"]

    def _handle_introduce(self, match) -> str:
        from config import Config
        name = Config.ASSISTANT_NAME
        intros = [
            f"Soy {name}, su asistente de inteligencia artificial personal. Estoy aqui para lo que necesite, senor. Puedo abrir aplicaciones, buscar en internet, controlar su equipo y mucho mas.",
            f"Me llamo {name}, senor. Soy su sistema de asistencia virtual inspirado en la IA de Tony Stark. Controlo su PC, busco informacion y ejecuto lo que me pida.",
            f"{name} a su servicio. Soy una inteligencia artificial disenada para asistirle en todo: desde abrir Spotify hasta buscar noticias o bloquear su equipo. Pidame lo que sea.",
            f"Mi nombre es {name}. Soy su mayordomo digital, senor. Gestiono aplicaciones, respondo preguntas, busco en la web y controlo su sistema. Estoy listo para servirle.",
            f"Soy {name}, su IA personal. Piense en mi como su asistente de confianza: rapido, eficiente y siempre disponible. Digame en que puedo ayudarle.",
        ]
        return random.choice(intros)

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

    # =========================================================================
    # Creacion de documentos y archivos
    # =========================================================================

    def _handle_create_word(self, match) -> str:
        content = match.group(1).strip().rstrip(".") if match.group(1) else ""
        desktop = os.path.expanduser("~\\Desktop").replace("\\", "\\\\")

        if content:
            # Limpiar el contenido para usarlo como titulo y texto
            safe_content = content.replace('"', '\\"').replace("'", "\\'")
            filename = re.sub(r'[^\w\s-]', '', content[:40]).strip().replace(' ', '_') or "documento"
        else:
            safe_content = "Documento creado por Jarvis"
            filename = "documento"

        code = f'''import subprocess
subprocess.run(["pip", "install", "python-docx"], capture_output=True)
from docx import Document
doc = Document()
doc.add_heading("{safe_content[:80]}", level=1)
doc.add_paragraph("{safe_content}")
filepath = r"{desktop}\\{filename}.docx"
doc.save(filepath)
import os
os.startfile(filepath)
print(f"Documento creado: {{filepath}}")
'''
        result = execute_code(code)
        if result["success"]:
            return f"Listo, senor. Documento Word creado en su escritorio: {filename}.docx"
        return f"No pude crear el documento: {result['message']}"

    def _handle_create_excel(self, match) -> str:
        content = match.group(1).strip().rstrip(".") if match.group(1) else ""
        desktop = os.path.expanduser("~\\Desktop").replace("\\", "\\\\")

        if content:
            safe_content = content.replace('"', '\\"')
            filename = re.sub(r'[^\w\s-]', '', content[:40]).strip().replace(' ', '_') or "hoja"
        else:
            safe_content = "Hoja de calculo"
            filename = "hoja"

        code = f'''import subprocess
subprocess.run(["pip", "install", "openpyxl"], capture_output=True)
from openpyxl import Workbook
wb = Workbook()
ws = wb.active
ws.title = "{safe_content[:30]}"
ws["A1"] = "{safe_content}"
filepath = r"{desktop}\\{filename}.xlsx"
wb.save(filepath)
import os
os.startfile(filepath)
print(f"Excel creado: {{filepath}}")
'''
        result = execute_code(code)
        if result["success"]:
            return f"Listo, senor. Excel creado en su escritorio: {filename}.xlsx"
        return f"No pude crear el Excel: {result['message']}"

    def _handle_create_txt(self, match) -> str:
        content = match.group(1).strip().rstrip(".") if match.group(1) else ""
        desktop = os.path.expanduser("~\\Desktop").replace("\\", "\\\\")

        if content:
            safe_content = content.replace('"', '\\"')
            filename = re.sub(r'[^\w\s-]', '', content[:40]).strip().replace(' ', '_') or "nota"
        else:
            safe_content = "Nota creada por Jarvis"
            filename = "nota"

        code = f'''filepath = r"{desktop}\\{filename}.txt"
with open(filepath, "w", encoding="utf-8") as f:
    f.write("{safe_content}")
import os
os.startfile(filepath)
print(f"Archivo creado: {{filepath}}")
'''
        result = execute_code(code)
        if result["success"]:
            return f"Listo, senor. Archivo de texto creado en su escritorio: {filename}.txt"
        return f"No pude crear el archivo: {result['message']}"

    # =========================================================================
    # Info del sistema y archivos
    # =========================================================================

    def _handle_list_files(self, match) -> str:
        folder = match.group(1).strip().lower().rstrip(".")
        folder_map = {
            "escritorio": "Desktop",
            "desktop": "Desktop",
            "descargas": "Downloads",
            "downloads": "Downloads",
            "documentos": "Documents",
            "documents": "Documents",
        }
        folder_name = folder_map.get(folder, folder)

        # Si es una ruta conocida, usar expanduser
        if folder_name in ("Desktop", "Downloads", "Documents"):
            path = os.path.expanduser(f"~\\{folder_name}")
        else:
            path = folder_name

        try:
            if not os.path.exists(path):
                return f"No encontre la carpeta '{folder}'."
            items = os.listdir(path)
            if not items:
                return f"La carpeta {folder} esta vacia."
            listing = "\n".join(f"  - {item}" for item in items[:30])
            total = len(items)
            extra = f"\n  ... y {total - 30} mas." if total > 30 else ""
            return f"Archivos en {folder} ({total}):\n{listing}{extra}"
        except Exception as e:
            return f"Error listando archivos: {e}"

    def _handle_disk_space(self, match) -> str:
        try:
            drive = match.group(1).strip().upper() if match.lastindex and match.group(1) else "C"
        except (IndexError, AttributeError):
            drive = "C"
        if not drive.endswith(":"):
            drive += ":"
        try:
            import shutil
            total, used, free = shutil.disk_usage(f"{drive}/")
            total_gb = total // (1024 ** 3)
            free_gb = free // (1024 ** 3)
            used_gb = used // (1024 ** 3)
            pct = round(used / total * 100, 1)
            return f"Disco {drive} tiene {free_gb} GB libres de {total_gb} GB totales. Usado: {used_gb} GB ({pct}%)."
        except Exception as e:
            return f"No pude obtener info del disco {drive}: {e}"

    def _handle_system_info(self, match) -> str:
        result = pc_control.get_system_info()
        if result["success"]:
            data = result["data"]
            return (
                f"Info del sistema:\n"
                f"  - OS: {data['os']}\n"
                f"  - Version: {data['version']}\n"
                f"  - Procesador: {data['processor']}\n"
                f"  - Usuario: {data['user']}\n"
                f"  - PC: {data['pc_name']}"
            )
        return "No pude obtener la info del sistema."
