#!/usr/bin/env python3
"""
JARVIS - Asistente de Inteligencia Artificial Personal
Inspirado en JARVIS de Iron Man.

Uso: python main.py
"""

import sys
import os
import logging
import threading
import queue

log = logging.getLogger("jarvis.main")

# Agregar el directorio raiz al path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from rich.console import Console
from rich.panel import Panel
from rich.text import Text
from rich.live import Live
from rich.spinner import Spinner

import re

from config import Config
from ai_providers import ProviderManager
from voice import VoiceEngine, SpeechToText
from memory import ConversationMemory, UserMemory
from utils import CommandHandler
from tools import ToolExecutor, FastCommandDetector
from tools.intent_router import IntentRouter
from telegram_io import TelegramIO
from knowledge import KnowledgeManager
from scheduler import TaskScheduler

# Patrones que indican que el usuario necesita informacion de internet
INTERNET_PATTERNS = [
    # Noticias
    r"noticia|noticias|que\s+(?:esta|está)\s+pasando|que\s+(?:ha|hay)\s+pasado",
    # Clima/tiempo
    r"clima|(?:que|cómo)\s+(?:tal\s+)?(?:el\s+)?(?:tiempo|temperatura)|va\s+a\s+llover|pronostico",
    # Precios/cotizaciones
    r"precio\s+de|cotizacion|(?:cuanto|cuánto)\s+(?:vale|cuesta)|dolar|bitcoin|bolsa",
    # Resultados deportivos
    r"resultado|marcador|(?:quien|quién)\s+(?:gano|ganó)|partido\s+de|score",
    # Eventos actuales
    r"hoy\s+(?:en|que)|esta\s+semana|actualmente|actual|reciente|ultimo|última|últim",
    # Búsqueda explícita de info
    r"(?:busca|buscame|dime)\s+(?:informacion|info)\s+(?:sobre|de|del)",
    r"(?:que|qué)\s+(?:sabes|hay)\s+(?:sobre|de|del|acerca)",
    r"(?:investiga|averigua|encuentra)\s+(?:sobre|de|del|acerca|info)",
    # "averigua/investiga + interrogativo X" — ej "averigua que es X",
    # "investiga como funciona Y", "averigua con que lenguaje esta hecho Z"
    r"(?:investiga|averigua|encuentra|consulta)\s+(?:que|qué|cual|cuál|como|cómo|cuando|cuándo|donde|dónde|por\s*que|porqué|quien|quién|cuanto|cuánto|con\s+(?:que|qué)|en\s+(?:que|qué)|de\s+(?:que|qué)|para\s+(?:que|qué))",
    # "averigua/investiga/busca en internet X", "en google X", "en la web X"
    r"(?:investiga|averigua|encuentra|busca|buscame|dime|consulta)\s+(?:en\s+)?(?:internet|la\s+web|google|la\s+red)",
    # Personas/eventos/lugares actuales
    r"(?:quien|quién)\s+es\s+(?:el|la)\s+(?:presidente|primer\s+ministro)",
    r"(?:cuando|cuándo)\s+(?:es|sera|será)\s+(?:el|la|los|las)",
]

_internet_re = re.compile("|".join(INTERNET_PATTERNS), re.IGNORECASE)


def needs_internet(text: str) -> bool:
    """Detecta si la pregunta necesita informacion actualizada de internet."""
    return bool(_internet_re.search(text))


# ===========================================================================
# CLASIFICADOR HEURISTICO DE INPUT
# ===========================================================================
# El objetivo es que el LLM pesado (gemma4:e4b o el que el usuario tenga como
# OLLAMA_MODEL) SOLO se invoque para tareas que de verdad lo requieran:
#   - Analisis de documentos ("analizame este pdf")
#   - Generacion de codigo ("hazme un script para X")
#   - Correccion de codigo ("arregla este error")
#   - Explicaciones profundas ("como funciona un motor")
#   - Investigacion elaborada
#
# Todo lo demas (abrir/cerrar apps, reproducir, buscar, saludos, preguntas
# cortas, media controls) debe ir por el PATH RAPIDO:
#   fast_commands -> intent_router(llama3.2) -> chat(llama3.2)
#
# Esto significa que:
#   - Usuario con OLLAMA_MODEL=llama3.2: TODO vuela (~1-3s por respuesta).
#   - Usuario con OLLAMA_MODEL=gemma4:e4b: solo las 10-20% de consultas
#     realmente pesadas usan gemma4. El resto usa llama3.2 (light model).
#     Resultado: el doble o triple de rapidez promedio.

# Palabras/frases que indican que el usuario SI quiere razonamiento pesado.
# Si detectamos esto, vamos al modelo principal (puede ser gemma4) con agent
# loop completo.
_HEAVY_TASK_RE = re.compile(
    r"\b("
    # Analisis de documentos/imagenes/datos
    r"analiza(?:me)?|analizalo|analizala|analizar|analisis|"
    # Generacion/escritura de contenido largo
    r"hazme\s+(?:un|una)\s+(?:script|codigo|programa|funcion|ensayo|articulo|redaccion|carta|correo|email|resumen\s+(?:largo|detallado|completo)|comparacion|tabla|plan|plantilla|presentacion)|"
    r"escribeme\s+(?:un|una)\s+(?:script|codigo|programa|funcion|ensayo|articulo|carta|correo|email|poema|cancion|historia|cuento|plan)|"
    r"(?:pasa|dame|generame|crea(?:me)?)\s+(?:un|una)\s+(?:script|codigo|programa|funcion|snippet|ejemplo\s+de\s+codigo)|"
    # Correccion/debug
    r"corrigeme|corrige\s+(?:este|el|la|mi)|debug(?:uea|gea)?|depura|arregla\s+(?:este|el|la|mi|mi\s+codigo)|"
    r"revisa\s+(?:mi|este|el|la)\s+(?:codigo|script|error|funcion|programa)|"
    # Explicaciones profundas
    r"como\s+funciona(?:n)?\s+(?:un|una|el|la|los|las)|"
    r"por\s*que\s+(?:sucede|pasa|es|ocurre)|"
    r"explicame\s+(?:a\s+fondo|en\s+detalle|detalladamente|el\s+concepto|como\s+funciona|por\s*que)|"
    r"que\s+es\s+(?:un|una|el\s+concepto)|"
    # Investigacion
    r"investiga(?:me)?|investigar|compara(?:me)?(?:\s+entre)?|"
    # Resumir/extraer de documento
    r"resume\s+(?:este|el|ese|mi)\s+(?:documento|archivo|pdf|texto|file)|"
    r"resumeme\s+(?:este|el|ese|mi)"
    r")\b",
    re.IGNORECASE,
)

# Verbos de accion directa. Si el input empieza con uno de estos y NO matcheo
# heavy_task, es una accion simple. La mandamos al intent_router aunque tenga
# "y" (tareas compuestas como "abre youtube Y busca X").
_ACTION_VERB_RE = re.compile(
    r"^\s*(?:jarvis[,\s]+)?(?:"
    r"abre|abrir|abreme|cierra|cerrar|cierrame|"
    r"pon|ponme|ponle|reproduce|reproduceme|reproducir|coloca|colocame|"
    r"busca|buscame|buscalo|search|googlea|"
    r"baja|sube|subele|bajale|aumenta|reduce|silencia|mutea|"
    r"bloquea|bloquear|lock|apaga|apagar|reinicia|reiniciar|"
    r"suspende|suspender|hiberna|hibernar|duerme|"
    r"captura|screenshot|pantallazo|graba|grabar|"
    r"dime\s+la\s+hora|que\s+hora|hora\s+es|"
    r"recuerda(?:me)?|avisame|agenda(?:me)?|programa(?:me)?|"
    r"manda(?:le)?|enviame|envia(?:le)?|escribele|"
    r"siguiente|anterior|pausa|pausar|play|stop|detente|para|"
    r"ejecuta|lanza|inicia|arranca|prende|enciende|activa|levanta|"
    r"sacame|dame\s+(?:la|el|los|las)?|mostrame|muestrame|"
    r"que\s+hay|que\s+tengo|lista(?:me)?"
    r")\b",
    re.IGNORECASE,
)


def classify_input(text: str) -> str:
    """Clasifica el input como 'heavy', 'action' o 'simple'.

    - 'heavy': tarea que realmente necesita el modelo potente.
    - 'action': comando de accion (abrir/cerrar/reproducir/etc).
    - 'simple': pregunta corta o charla casual.
    """
    t = text.strip()
    if _HEAVY_TASK_RE.search(t):
        return "heavy"
    if _ACTION_VERB_RE.match(t):
        return "action"
    return "simple"

console = Console()

# Patrones que indican que el usuario pregunta SOBRE un documento cargado
# (meta-query), no sobre su contenido especifico.
_DOC_META_RE = re.compile(
    r"(?:resum|resume|resumen|resumeme|resumelo|resumela|resumir)"
    r"|(?:de\s+que\s+(?:trata|habla|va|se\s+trata))"
    r"|(?:que\s+(?:dice|contiene|tiene|trae))\s+(?:el|ese|este|mi|lo|la)?\s*(?:documento|archivo|doc|pdf|texto|file)"
    r"|(?:que\s+(?:dice|contiene))\s+(?:lo\s+que|eso)"
    r"|(?:dime|explicame|cuentame)\s+(?:sobre|de|que\s+dice)\s+(?:el|ese|lo)"
    r"|(?:analiza|analisis)\s+(?:del?|el|ese|este|mi|lo)?\s*(?:documento|archivo)"
    r"|(?:lo\s+que\s+(?:te\s+)?(?:cargue|subi|envie|mande))",
    re.IGNORECASE,
)


def _build_rag_context(user_input: str, knowledge) -> str | None:
    """
    Decide que contexto RAG inyectar segun la pregunta del usuario.
    - Si es meta-query ('resumeme el documento') -> inyecta todo el documento.
    - Si es content-query ('que riesgos hay?') -> busqueda semantica normal.
    """
    # Meta-query: inyectar contenido completo del documento mas reciente
    if _DOC_META_RE.search(user_input):
        full = knowledge.get_all_content()
        if full:
            return full

    # Content-query: busqueda semantica
    return knowledge.build_context(user_input, top_k=5)


BANNER = r"""
       ██╗ █████╗ ██████╗ ██╗   ██╗██╗███████╗
       ██║██╔══██╗██╔══██╗██║   ██║██║██╔════╝
       ██║███████║██████╔╝██║   ██║██║███████╗
  ██   ██║██╔══██║██╔══██╗╚██╗ ██╔╝██║╚════██║
  ╚█████╔╝██║  ██║██║  ██║ ╚████╔╝ ██║███████║
   ╚════╝ ╚═╝  ╚═╝╚═╝  ╚═╝  ╚═══╝  ╚═╝╚══════╝
"""


def display_banner():
    banner_text = Text(BANNER, style="bold cyan")
    panel = Panel(
        banner_text,
        subtitle="[dim]Escribe /ayuda para ver comandos | Habla en cualquier momento[/dim]",
        border_style="cyan",
    )
    console.print(panel)


def display_response(text: str, source: str = ""):
    title = f"[bold cyan]{Config.ASSISTANT_NAME}[/bold cyan]"
    if source:
        title += f" [dim]({source})[/dim]"
    panel = Panel(
        text,
        title=title,
        border_style="cyan",
        padding=(1, 2),
    )
    console.print(panel)


def keyboard_input_thread(input_queue: queue.Queue, stop_event: threading.Event):
    """Hilo que lee input del teclado sin bloquear el hilo principal."""
    while not stop_event.is_set():
        try:
            text = input()
            if text is not None:
                # 4-tupla: (source, text, chat_id, is_voice). chat_id=None y
                # is_voice=False para teclado.
                input_queue.put(("keyboard", text.strip(), None, False))
        except EOFError:
            input_queue.put(("keyboard", "/salir", None, False))
            break
        except Exception:
            break


def _startup_greeting(user_memory, voice_engine, mic_available, stt, telegram_io):
    """Saludo proactivo al iniciar Jarvis, estilo JARVIS de Iron Man."""
    from datetime import datetime
    import random as _rnd

    now = datetime.now()
    hour = now.hour

    # Saludo segun hora
    if hour < 12:
        saludo = "Buenos dias"
    elif hour < 18:
        saludo = "Buenas tardes"
    else:
        saludo = "Buenas noches"

    # Nombre del usuario (si lo recuerda)
    user_name = ""
    if user_memory and user_memory.count > 0:
        for fact in user_memory.recall_all():
            if "nombre" in fact["text"].lower():
                parts = fact["text"].split("es ")
                if len(parts) > 1:
                    user_name = parts[-1].strip().rstrip(".")
                    break

    name_part = f", senor {user_name}" if user_name else ", senor"
    date_str = now.strftime("%A %d de %B, %I:%M %p")

    # Variacion con personalidad
    closers = [
        "A su servicio, como siempre.",
        "A su entera disposicion.",
        "Listo para trabajar, senor.",
        "Aqui me tiene.",
        "Todos los sistemas en linea.",
        "Un placer volver a atenderle.",
    ]
    greeting = f"{saludo}{name_part}. {_rnd.choice(closers)}"
    time_info = f"Son las {date_str}."

    console.print(f"\n  [bold cyan]{Config.ASSISTANT_NAME}:[/bold cyan] {greeting}")
    console.print(f"  [dim]{time_info}[/dim]")
    console.print(f"  [dim]¿En que puedo ayudarle hoy?[/dim]")

    # Hablar el saludo
    if voice_engine and voice_engine.is_enabled:
        if mic_available and stt:
            stt.pause()
        voice_engine.speak(f"{greeting} {time_info}")
        if mic_available and stt:
            stt.resume()

    # Enviar saludo por Telegram
    if telegram_io and telegram_io.is_available:
        try:
            for uid in telegram_io.allowed_users:
                telegram_io.send_reply(uid, f"{greeting}\n{time_info}\n\n¿En que puedo ayudarle hoy?")
                break
        except Exception:
            pass


def main():
    display_banner()
    console.print("\n[bold cyan]Inicializando sistemas...[/bold cyan]")

    # Inicializar componentes
    provider_manager = ProviderManager()
    if not provider_manager.initialize():
        sys.exit(1)

    voice_engine = VoiceEngine()
    voice_engine.initialize()

    stt = SpeechToText()
    mic_available = stt.initialize()

    tool_executor = ToolExecutor()
    fast_cmd = FastCommandDetector()
    intent_router = IntentRouter()

    # Pre-calentar SOLO el modelo ligero (llama3.2) en background. Es el que
    # se usa en el 90% de interacciones (router + chat simple + acciones).
    # El modelo pesado (gemma4:e4b u otro que el usuario tenga como
    # OLLAMA_MODEL) NO se precarga: solo se usa para tareas heavy
    # (infrecuentes) y pagar su cold start en el primer uso real es mejor que
    # gastar RAM a ciegas al arranque. Warmup es 100% silencioso.
    def _warmup():
        import urllib.request, urllib.error, json as _json
        try:
            payload = _json.dumps({
                "model": Config.OLLAMA_LIGHT_MODEL,
                "messages": [{"role": "user", "content": "ok"}],
                "stream": False,
                "options": {"num_predict": 1},
            }).encode("utf-8")
            req = urllib.request.Request(
                "http://localhost:11434/api/chat",
                data=payload,
                headers={"Content-Type": "application/json"},
            )
            urllib.request.urlopen(req, timeout=30).read()
        except Exception:
            # Silencioso: si falla, el primer input real lo cargara.
            pass
    threading.Thread(target=_warmup, daemon=True).start()
    memory = ConversationMemory()
    user_memory = UserMemory()
    user_memory.initialize()
    cmd_handler = CommandHandler(provider_manager, voice_engine, memory, stt, knowledge=None, user_memory=user_memory)
    system_prompt = Config.get_system_prompt()

    # Base de conocimiento RAG (opcional — solo si chromadb esta instalado)
    knowledge = KnowledgeManager()
    rag_available = knowledge.initialize()
    if rag_available:
        console.print(f"  [cyan]Base de conocimiento:[/cyan] activa ({knowledge.total_chunks} fragmentos)")
    else:
        console.print("  [dim]  Base de conocimiento: no disponible (instala chromadb para RAG)[/dim]")
    cmd_handler._knowledge = knowledge

    # Inyectar funciones de RAG en el executor si esta disponible
    if rag_available:
        from tools.executor import TOOLS

        def _knowledge_search_fn(query: str) -> dict:
            hits = knowledge.query(query, top_k=5)
            if not hits:
                return {"success": True, "message": "No encontre informacion relevante en la base de conocimiento."}
            lines = []
            for h in hits:
                lines.append(f"[{h['source']}] (relevancia {h['score']:.0%}): {h['text'][:300]}")
            return {"success": True, "message": "\n".join(lines)}

        def _knowledge_load_fn(file_path: str) -> dict:
            result = knowledge.add_document(file_path)
            return {"success": result["success"], "message": result["message"]}

        TOOLS["knowledge_search"]["function"] = _knowledge_search_fn
        TOOLS["knowledge_load"]["function"] = _knowledge_load_fn

    # Inyectar funciones de memoria en el executor
    def _remember_fn(fact: str, category: str = "general") -> dict:
        user_memory.remember(fact, category)
        return {"success": True, "message": f"Recordare: {fact}"}

    def _recall_memory_fn(query: str) -> dict:
        hits = user_memory.recall(query)
        if hits:
            lines = [h["text"] for h in hits]
            return {"success": True, "message": "\n".join(lines)}
        return {"success": True, "message": "No encontre recuerdos sobre eso."}

    from tools.executor import TOOLS
    TOOLS["remember"]["function"] = _remember_fn
    TOOLS["recall_memory"]["function"] = _recall_memory_fn

    # Inyectar funciones de scheduler
    def _schedule_reminder_fn(message: str, time_description: str) -> dict:
        # Canal de entrega: siempre Telegram si disponible
        _channel = "console"
        _chat_id = None
        if telegram_active:
            _channel = "telegram"
            if source == "telegram" and chat_id is not None:
                _chat_id = chat_id
            else:
                _allowed = telegram_io.allowed_users
                if _allowed:
                    _chat_id = next(iter(_allowed))

        # 1) Intentar como recurrente ("todos los dias", "cada lunes", etc.)
        run_at, repeat = scheduler.parse_recurring(time_description)
        if run_at and repeat:
            task_info = scheduler.add_task(message, run_at, _channel, _chat_id, repeat=repeat)
            repeat_label = {
                "daily": "todos los dias",
                "weekly": f"semanalmente",
                "hourly": "cada hora",
                "every": f"cada {repeat.get('minutes', '?')} minutos",
            }.get(repeat["type"], repeat["type"])
            return {"success": True, "message": f"Recordatorio recurrente ({repeat_label}) programado. Proxima ejecucion: {task_info['run_at']}. Mensaje: '{message}'"}

        # 2) Intentar como relativo ("en 30 minutos")
        run_at = scheduler.parse_relative_time(time_description)
        if run_at is None:
            # 3) Intentar como absoluto ("a las 5pm")
            run_at = scheduler.parse_absolute_time(time_description)
        if run_at is None:
            return {"success": False, "message": f"No entendi el tiempo '{time_description}'. Usa: 'en 30 minutos', 'a las 5pm', 'todos los dias a las 9am', 'cada lunes a las 8am'."}

        task_info = scheduler.add_task(message, run_at, _channel, _chat_id)
        return {"success": True, "message": f"Recordatorio programado para {task_info['run_at']}: '{message}'"}

    def _list_reminders_fn() -> dict:
        tasks = scheduler.list_tasks()
        if not tasks:
            return {"success": True, "message": "No hay recordatorios pendientes."}
        lines = []
        for t in tasks:
            lines.append(f"- [{t['id']}] {t['run_at'][:16]} — {t['message']}")
        return {"success": True, "message": "\n".join(lines)}

    TOOLS["schedule_reminder"]["function"] = _schedule_reminder_fn
    TOOLS["list_reminders"]["function"] = _list_reminders_fn

    # Inyectar funcion de busqueda en internet (DuckDuckGo -> texto)
    def _internet_search_fn(query: str) -> dict:
        from tools.web_search import search_internet
        results = search_internet(query)
        if results:
            return {"success": True, "message": results}
        return {"success": False, "message": "No encontre resultados para esa busqueda."}

    from tools.executor import TOOLS
    TOOLS["internet_search"]["function"] = _internet_search_fn

    # Inyectar funciones de vision en el executor
    from tools.executor import TOOLS as _TOOLS
    from tools import pc_control as _pc_control

    def _analyze_image_fn(image_path: str, prompt: str = "") -> dict:
        result = provider_manager.analyze_image(image_path, prompt)
        if result:
            return {"success": True, "message": result}
        return {"success": False, "message": "No pude analizar la imagen. Verifica que el modelo soporta vision."}

    def _analyze_screenshot_fn() -> dict:
        ss_result = _pc_control.take_screenshot()
        if not ss_result.get("success"):
            return {"success": False, "message": "No pude capturar la pantalla."}
        ss_path = ss_result["message"].replace("Captura guardada en ", "")
        analysis = provider_manager.analyze_image(ss_path, "Describe en detalle en espanol lo que ves en esta captura de pantalla.")
        if analysis:
            return {"success": True, "message": analysis}
        return {"success": False, "message": "Capture la pantalla pero no pude analizarla."}

    _TOOLS["analyze_image"]["function"] = _analyze_image_fn
    _TOOLS["analyze_screenshot"]["function"] = _analyze_screenshot_fn

    # Cola unificada para input (voz, teclado y telegram).
    # Formato: (source, text, chat_id)  -- chat_id es None salvo para Telegram.
    input_queue = queue.Queue()
    stop_event = threading.Event()

    # Iniciar escucha de voz continua
    if mic_available:
        stt.start_listening()

    # Iniciar hilo de teclado
    kb_thread = threading.Thread(
        target=keyboard_input_thread,
        args=(input_queue, stop_event),
        daemon=True,
    )
    kb_thread.start()

    # Inicializar integracion con Telegram (opcional). Le pasamos el voice_engine
    # para poder responder con audio cuando el usuario envia un audio por Telegram.
    telegram_io = TelegramIO(input_queue, voice_engine=voice_engine, knowledge_manager=knowledge, provider_manager=provider_manager)
    telegram_active = telegram_io.initialize()
    if telegram_active:
        telegram_io.start()

    # Scheduler de recordatorios
    def _console_reminder(msg):
        console.print(f"\n  [bold yellow]{msg}[/bold yellow]")
        console.print(f"\n  [cyan]{Config.ASSISTANT_NAME} >[/cyan] ", end="")

    scheduler = TaskScheduler(
        telegram_io=telegram_io if telegram_active else None,
        console_callback=_console_reminder,
    )
    scheduler.initialize()
    scheduler.start()
    cmd_handler._scheduler = scheduler

    console.print("[bold green]\n  Sistemas en linea. Listo para servir, senor.[/bold green]")
    console.print("[dim]  Control del PC activado. Puedo abrir apps, buscar en la web, y mas.[/dim]")
    if mic_available:
        console.print(f'[dim]  Di "{Config.ASSISTANT_NAME}" + tu comando para activarme por voz.[/dim]')
        console.print("[dim]  Tambien puedes escribir directamente.[/dim]")
    else:
        console.print("[dim]  Microfono no disponible. Escribe tus comandos.[/dim]")
    if telegram_active:
        bot_username = telegram_io.bot_username
        if bot_username:
            console.print(f"[dim]  Telegram activo: @{bot_username}[/dim]")
        else:
            console.print("[dim]  Telegram activo[/dim]")

    # Saludo proactivo al iniciar
    _startup_greeting(user_memory, voice_engine, mic_available, stt, telegram_io if telegram_active else None)

    console.print(f"\n  [cyan]{Config.ASSISTANT_NAME} >[/cyan] ", end="")

    # Helper para responder al usuario segun el origen del mensaje
    def reply(text: str, source: str, chat_id, *, header: str = "", as_voice: bool = False):
        """
        Envia la respuesta al canal correspondiente (consola+voz o Telegram).
        Telegram NUNCA activa la voz del PC — la respuesta va solo a Telegram.
        """
        if source == "telegram" and chat_id is not None:
            if as_voice:
                telegram_io.send_voice_reply(chat_id, text)
            else:
                telegram_io.send_reply(chat_id, text)
            return
        display_response(text, header)
        if mic_available:
            stt.pause()
        voice_engine.speak(text)
        if mic_available:
            stt.resume()

    # Loop principal
    while not stop_event.is_set():
        try:
            user_input = None
            source = ""
            chat_id = None
            is_voice_input = False

            # Revisar si hay input de voz
            if mic_available:
                voice_text = stt.get_speech(timeout=0.05)
                if voice_text:
                    if voice_text == "__WAKE__":
                        # Solo dijo "Jarvis" sin comando -> activar escucha temporal
                        stt.activate_listening()
                        console.print(f"\n  [bold cyan]Digame, senor.[/bold cyan]")
                        stt.pause()
                        voice_engine.speak("Digame, senor.")
                        stt.resume()
                        console.print(f"\n  [cyan]{Config.ASSISTANT_NAME} >[/cyan] ", end="")
                        continue
                    # Desactivar escucha activa al recibir comando
                    stt.deactivate_listening()
                    user_input = voice_text
                    source = "voz"
                    console.print(f"\n  [green]Escuche:[/green] \"{user_input}\"")

            # Revisar si hay input de teclado o telegram
            if user_input is None:
                try:
                    item = input_queue.get(timeout=0.1)
                    # Formato: (source, text, chat_id, is_voice). Soporta tambien
                    # tuplas mas cortas por compatibilidad.
                    if len(item) == 4:
                        msg_type, text, chat_id, is_voice_input = item
                    elif len(item) == 3:
                        msg_type, text, chat_id = item
                    else:
                        msg_type, text = item
                        chat_id = None
                    if text:
                        user_input = text
                        if msg_type == "telegram":
                            source = "telegram"
                            tag = "voz" if is_voice_input else "texto"
                            console.print(
                                f"\n  [magenta]Telegram[/magenta] [{chat_id}] ({tag}): \"{user_input}\""
                            )
                        else:
                            source = "texto"
                except queue.Empty:
                    continue

            if not user_input:
                console.print(f"\n  [cyan]{Config.ASSISTANT_NAME} >[/cyan] ", end="")
                continue

            # Extraer hechos personales del input
            user_memory.extract_facts(user_input)

            # Si el usuario escribio solo "Jarvis" por teclado, tratarlo como wake word.
            # Desde Telegram no tiene sentido (ya estas hablando con el bot), asi que se ignora.
            if SpeechToText.is_wake_word(user_input):
                if source == "telegram":
                    telegram_io.send_reply(chat_id, "Digame, senor.")
                    continue
                if mic_available:
                    stt.activate_listening()
                console.print(f"\n  [bold cyan]Digame, senor.[/bold cyan]")
                if mic_available:
                    stt.pause()
                voice_engine.speak("Digame, senor.")
                if mic_available:
                    stt.resume()
                console.print(f"\n  [cyan]{Config.ASSISTANT_NAME} >[/cyan] ", end="")
                continue

            # Manejar comandos del sistema (solo desde teclado/voz local;
            # comandos como /salir desde Telegram son peligrosos -> los ignoramos)
            if cmd_handler.is_command(user_input):
                if source == "telegram":
                    telegram_io.send_reply(
                        chat_id,
                        "Los comandos del sistema (/salir, /voz, etc.) solo "
                        "estan disponibles desde el PC, senor.",
                    )
                    continue
                should_continue = cmd_handler.handle(user_input)
                if not should_continue:
                    break
                console.print(f"\n  [cyan]{Config.ASSISTANT_NAME} >[/cyan] ", end="")
                continue

            # FAST PATH: Intentar ejecutar comando rapido sin IA (regex, instantaneo)
            handled, fast_response = fast_cmd.try_execute(user_input)
            if handled:
                memory.add_message("user", user_input)
                memory.add_message("assistant", fast_response)
                reply(fast_response, source, chat_id, as_voice=is_voice_input)
                if source != "telegram":
                    console.print(f"\n  [cyan]{Config.ASSISTANT_NAME} >[/cyan] ", end="")
                continue

            # CLASIFICAR el input: 'heavy' | 'action' | 'simple'
            # Esto determina tanto el camino como el modelo a usar.
            input_class = classify_input(user_input)

            # INTENT ROUTER: para acciones probamos SIEMPRE, aunque sea
            # compuesta — el fast_commands ya cubrio las compuestas comunes,
            # asi que lo que quede aqui debe ir por tool_call rapido.
            # Para preguntas/chat saltamos el router (no aporta).
            _looks_like_question = bool(re.match(
                r'^(?:que|qué|como|cómo|cuando|cuándo|donde|dónde|por\s*que|porqué|'
                r'cual|cuál|cuanto|cuánto|quien|quién|explicame|cuentame|dime\s+(?:un|algo)|'
                r'sabes|puedes\s+(?:explicar|decir|contar))\b',
                user_input.lower(),
            ))
            # Compound SOLO para tareas 'heavy' (ej "busca X y crealo en word")
            _is_compound_task = (input_class == "heavy") and bool(re.search(
                r'\by\s+(?:dime|crea|crealas|crealo|ponlas|ponlo|manda|mandame|mandale|'
                r'enviale|envia|enviame|resume|resumelo|resumeme|guarda|guardalo|analiza)\b',
                user_input.lower(),
            ))
            intent = None
            # Intentar router si: es accion (aunque sea compuesta), o es input
            # corto no-pregunta. Saltar si es claramente pregunta o tarea pesada.
            if input_class == "action" or (not _looks_like_question and not _is_compound_task and input_class != "heavy"):
                intent = intent_router.classify(user_input)
            if intent is not None:
                tool_name = intent["tool"]
                params = intent["params"]
                console.print(f"  [bold magenta]>[/bold magenta] {tool_name} {params}")
                result = tool_executor._execute_tool(tool_name, params)
                intent_response = result.get("message", "Hecho, senor.")
                memory.add_message("user", user_input)
                memory.add_message("assistant", intent_response)
                reply(intent_response, source, chat_id, as_voice=is_voice_input)
                if source != "telegram":
                    console.print(f"\n  [cyan]{Config.ASSISTANT_NAME} >[/cyan] ", end="")
                continue

            # INTERNET PATH: Si necesita info actual, buscar en DuckDuckGo + resumir con IA
            if needs_internet(user_input):
                memory.add_message("user", user_input)

                console.print("")
                with Live(
                    Spinner("dots", text="[cyan] Buscando en internet...[/cyan]", style="cyan"),
                    console=console,
                    transient=True,
                ):
                    response = provider_manager.search_and_answer(user_input)

                if response:
                    clean_response, _ = tool_executor.process_response(response)
                    memory.add_message("assistant", clean_response)
                    reply(clean_response, source, chat_id, header="internet", as_voice=is_voice_input)
                    if source != "telegram":
                        console.print(f"\n  [cyan]{Config.ASSISTANT_NAME} >[/cyan] ", end="")
                    continue
                else:
                    # No se pudo buscar, avisar y dejar que Ollama intente solo
                    memory.messages.pop()
                    console.print(f"\n  [yellow]No pude buscar en internet. Intentare responder con lo que se.[/yellow]")

            # AGENT PATH: Routing inteligente.
            # - Preguntas / conversacion -> chat() rapido SIN tools
            # - Tareas con acciones -> agent_chat() con function calling y loop
            # Inyectar memoria + RAG en el mensaje del usuario (no en system
            # prompt — Ollama lo ignora). Esto garantiza que la IA VEA los datos.
            context_parts = []

            # Memoria del usuario (hechos personales)
            mem_ctx = user_memory.build_context()
            if mem_ctx:
                context_parts.append(mem_ctx)

            # RAG (documentos cargados)
            if rag_available and knowledge.total_chunks > 0:
                rag_context = _build_rag_context(user_input, knowledge)
                if rag_context:
                    context_parts.append(rag_context)

            if context_parts:
                augmented_input = "\n\n".join(context_parts) + "\n\nPREGUNTA DEL USUARIO: " + user_input
            else:
                augmented_input = user_input

            memory.add_message("user", augmented_input)

            from tools.executor import get_tools_schema, execute_tool_call

            def _on_tool_call(step, tool_name, args):
                console.print(f"  [bold magenta]Paso {step}[/bold magenta] {tool_name}({args})")

            # Elegir modelo segun la clase del input:
            #   - 'heavy': modelo principal (OLLAMA_MODEL, ej gemma4)
            #   - 'action' / 'simple': modelo ligero (OLLAMA_LIGHT_MODEL, llama3.2)
            # Y el numero de pasos del agent loop se reduce para tareas ligeras.
            if input_class == "heavy":
                model_override = None  # usa default (principal)
                steps_for_agent = Config.MAX_AGENT_STEPS
            else:
                model_override = Config.OLLAMA_LIGHT_MODEL
                steps_for_agent = Config.MAX_AGENT_STEPS_LIGHT

            try:
                if _looks_like_question or input_class == "simple":
                    # Conversacion: chat rapido sin tools (~2-5s con modelo ligero)
                    console.print("")
                    with Live(
                        Spinner("dots", text="[cyan] Pensando...[/cyan]", style="cyan"),
                        console=console,
                        transient=True,
                    ):
                        response = provider_manager.chat(
                            memory.get_context_messages(),
                            system_prompt,
                            model_override=model_override,
                        )
                else:
                    # Tarea con acciones: Agent Loop con tools
                    console.print("")
                    with Live(
                        Spinner("dots", text="[cyan] Pensando...[/cyan]", style="cyan"),
                        console=console,
                        transient=True,
                    ):
                        response = provider_manager.agent_chat(
                            messages=memory.get_context_messages(),
                            system_prompt=system_prompt,
                            tools_schema=get_tools_schema(),
                            execute_fn=execute_tool_call,
                            max_steps=steps_for_agent,
                            on_tool_call=_on_tool_call,
                            model_override=model_override,
                        )

            except ConnectionError as e:
                console.print(f"\n[bold red]Error: {e}[/bold red]")
                memory.messages.pop()
                if source == "telegram":
                    telegram_io.send_reply(chat_id, f"Error: {e}")
                else:
                    console.print(f"\n  [cyan]{Config.ASSISTANT_NAME} >[/cyan] ", end="")
                continue
            except Exception as e:
                console.print(f"\n[bold red]Error inesperado: {e}[/bold red]")
                memory.messages.pop()
                if source == "telegram":
                    telegram_io.send_reply(chat_id, f"Error inesperado: {e}")
                else:
                    console.print(f"\n  [cyan]{Config.ASSISTANT_NAME} >[/cyan] ", end="")
                continue

            clean_response = response

            memory.add_message("assistant", clean_response)

            if source == "telegram":
                reply(clean_response, source, chat_id, header=provider_manager.current_provider_name, as_voice=is_voice_input)
            else:
                display_response(clean_response, provider_manager.current_provider_name)
                if mic_available:
                    stt.pause()
                voice_engine.speak(clean_response)
                if mic_available:
                    stt.resume()
                console.print(f"\n  [cyan]{Config.ASSISTANT_NAME} >[/cyan] ", end="")

        except KeyboardInterrupt:
            break

    # Cleanup
    stop_event.set()
    scheduler.stop()
    if mic_available:
        stt.stop_listening()
    if telegram_active:
        telegram_io.stop()
    memory.save_session()
    console.print(f"\n[bold cyan]Hasta luego, senor. Estare aqui cuando me necesite.[/bold cyan]\n")


if __name__ == "__main__":
    main()
