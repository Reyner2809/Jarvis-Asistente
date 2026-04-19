"""
Jarvis Bridge Server — expone Jarvis via HTTP/WebSocket para la UI Electron.

Uso:
    python -m bridge.server [--port 17891] [--host 127.0.0.1]

Endpoints:
    GET  /api/health       Ping simple para verificar que el bridge esta vivo.
    GET  /api/state        Estado actual (proveedor, modelo, uptime).
    POST /api/command      Procesa un input de texto. Body: {"text": "..."}
    WS   /ws/events        Conexion persistente para recibir eventos en vivo:
                           - {"type": "route", "route": "fast|intent_router|chat|..."}
                           - {"type": "tool_call", "step": int, "name": str, "args": {...}}
                           - {"type": "response", "text": str, "route": str, ...}
                           - {"type": "thinking"} / {"type": "searching"}

NO toca main.py ni interfiere con el CLI. Es un segundo entry point
independiente que importa los mismos modulos de Jarvis.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import queue
import sys
import threading
import time
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Any, Optional

# Agregar el root del proyecto al sys.path para poder importar los modulos
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
import uvicorn

from config import Config
from ai_providers import ProviderManager
from memory import ConversationMemory, UserMemory
from tools import FastCommandDetector, ToolExecutor
from tools.intent_router import IntentRouter

# RAG opcional (puede no estar instalado chromadb)
try:
    from knowledge import KnowledgeManager
except Exception:
    KnowledgeManager = None

# Scheduler opcional (recordatorios)
try:
    from scheduler import TaskScheduler
except Exception:
    TaskScheduler = None

from bridge.processor import JarvisProcessor
from bridge.voice_loop import VoiceLoop


log = logging.getLogger("jarvis.bridge")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
)


# ===========================================================================
# Event bus simple para broadcast WebSocket
# ===========================================================================

class EventBus:
    """Cola en memoria para distribuir eventos a todos los WS conectados."""

    def __init__(self):
        self._subscribers: list[asyncio.Queue] = []

    def subscribe(self) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue(maxsize=256)
        self._subscribers.append(q)
        return q

    def unsubscribe(self, q: asyncio.Queue):
        try:
            self._subscribers.remove(q)
        except ValueError:
            pass

    def publish(self, event: dict):
        """Thread-safe publish — se puede llamar desde cualquier hilo."""
        for q in list(self._subscribers):
            try:
                q.put_nowait(event)
            except asyncio.QueueFull:
                pass  # cliente lento, dropeamos el evento


# ===========================================================================
# Estado global del bridge
# ===========================================================================

class BridgeState:
    started_at: float = 0.0
    provider_manager: Optional[ProviderManager] = None
    fast_cmd: Optional[FastCommandDetector] = None
    intent_router: Optional[IntentRouter] = None
    tool_executor: Optional[ToolExecutor] = None
    memory: Optional[ConversationMemory] = None
    user_memory: Optional[UserMemory] = None
    knowledge: Optional[Any] = None
    processor: Optional[JarvisProcessor] = None
    voice: Optional[VoiceLoop] = None
    scheduler: Optional[Any] = None
    event_bus: EventBus = EventBus()
    # Greeting: se genera al iniciar y se envia al primer cliente WS que
    # conecta (para que una sola sesion de bridge no salude dos veces).
    greeting_text: str = ""
    greeting_delivered: bool = False
    # Telegram bot (opcional — solo si hay token configurado)
    telegram: Optional[Any] = None
    telegram_input_queue: Optional["queue.Queue"] = None
    telegram_stop: threading.Event = threading.Event()


state = BridgeState()


def _bind_tools():
    """Registra en el diccionario global TOOLS las implementaciones de las
    herramientas que requieren acceso a los managers del bridge (RAG, memoria,
    scheduler, vision, internet). Espejo exacto de lo que hace main.py.

    Sin este bind, el agent loop intentaria llamar tools por nombre pero
    TOOLS[name]['function'] seria None y fallaria.
    """
    from tools.executor import TOOLS

    # ---- RAG (ChromaDB) ----
    if state.knowledge is not None:
        knowledge = state.knowledge

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

    # ---- Memoria del usuario ----
    um = state.user_memory
    def _remember_fn(fact: str, category: str = "general") -> dict:
        um.remember(fact, category)
        return {"success": True, "message": f"Recordare: {fact}"}

    def _recall_memory_fn(query: str) -> dict:
        hits = um.recall(query)
        if hits:
            return {"success": True, "message": "\n".join(h["text"] for h in hits)}
        return {"success": True, "message": "No encontre recuerdos sobre eso."}

    TOOLS["remember"]["function"] = _remember_fn
    TOOLS["recall_memory"]["function"] = _recall_memory_fn

    # ---- Scheduler (recordatorios) ----
    if state.scheduler is not None:
        sched = state.scheduler

        def _schedule_reminder_fn(message: str, time_description: str) -> dict:
            # En el bridge no tenemos telegram/console context — siempre entregamos
            # por el event_bus como notificacion WS + TTS.
            run_at, repeat = sched.parse_recurring(time_description)
            if run_at and repeat:
                info = sched.add_task(message, run_at, "console", None, repeat=repeat)
                rlabel = {
                    "daily": "todos los dias", "weekly": "semanalmente",
                    "hourly": "cada hora", "every": f"cada {repeat.get('minutes','?')} minutos",
                }.get(repeat["type"], repeat["type"])
                return {"success": True, "message": f"Recordatorio recurrente ({rlabel}) programado. Proxima: {info['run_at']}. Mensaje: '{message}'"}
            run_at = sched.parse_relative_time(time_description) or sched.parse_absolute_time(time_description)
            if run_at is None:
                return {"success": False, "message": f"No entendi el tiempo '{time_description}'."}
            info = sched.add_task(message, run_at, "console", None)
            return {"success": True, "message": f"Recordatorio programado para {info['run_at']}: '{message}'"}

        def _list_reminders_fn() -> dict:
            tasks = sched.list_tasks()
            if not tasks:
                return {"success": True, "message": "No hay recordatorios pendientes."}
            lines = [f"- [{t['id']}] {t['run_at'][:16]} — {t['message']}" for t in tasks]
            return {"success": True, "message": "\n".join(lines)}

        TOOLS["schedule_reminder"]["function"] = _schedule_reminder_fn
        TOOLS["list_reminders"]["function"] = _list_reminders_fn

    # ---- Busqueda en internet (DuckDuckGo) ----
    def _internet_search_fn(query: str) -> dict:
        from tools.web_search import search_internet
        results = search_internet(query)
        if results:
            return {"success": True, "message": results}
        return {"success": False, "message": "No encontre resultados."}
    TOOLS["internet_search"]["function"] = _internet_search_fn

    # ---- Vision (analyze_image, analyze_screenshot) ----
    pm = state.provider_manager
    if pm is not None and hasattr(pm, "analyze_image"):
        from tools import pc_control as _pc

        def _analyze_image_fn(image_path: str, prompt: str = "") -> dict:
            r = pm.analyze_image(image_path, prompt)
            return {"success": bool(r), "message": r or "No pude analizar la imagen."}

        def _analyze_screenshot_fn() -> dict:
            ss = _pc.take_screenshot()
            if not ss.get("success"):
                return {"success": False, "message": "No pude capturar la pantalla."}
            path = ss["message"].replace("Captura guardada en ", "")
            r = pm.analyze_image(path, "Describe en detalle en espanol lo que ves en esta captura.")
            return {"success": bool(r), "message": r or "Capture pero no pude analizarla."}

        TOOLS["analyze_image"]["function"] = _analyze_image_fn
        TOOLS["analyze_screenshot"]["function"] = _analyze_screenshot_fn


_DIAS = ['Lunes', 'Martes', 'Miercoles', 'Jueves', 'Viernes', 'Sabado', 'Domingo']
_MESES = ['Enero', 'Febrero', 'Marzo', 'Abril', 'Mayo', 'Junio',
          'Julio', 'Agosto', 'Septiembre', 'Octubre', 'Noviembre', 'Diciembre']


def _fecha_espanol(now=None) -> str:
    """Fecha y hora formateada en espanol (sin depender del locale del SO)."""
    if now is None:
        now = datetime.now()
    dia = _DIAS[now.weekday()]
    mes = _MESES[now.month - 1]
    return f"{dia} {now.day} de {mes}, {now.strftime('%I:%M %p')}"


def build_greeting(user_memory) -> str:
    """Genera el saludo de arranque estilo JARVIS."""
    import random as _rnd
    now = datetime.now()
    hour = now.hour

    if hour < 12:
        saludo = "Buenos dias"
    elif hour < 18:
        saludo = "Buenas tardes"
    else:
        saludo = "Buenas noches"

    user_name = ""
    if user_memory and getattr(user_memory, "count", 0) > 0:
        try:
            for fact in user_memory.recall_all():
                if "nombre" in fact["text"].lower():
                    parts = fact["text"].split("es ")
                    if len(parts) > 1:
                        user_name = parts[-1].strip().rstrip(".")
                        break
        except Exception:
            pass

    name_part = f", senor {user_name}" if user_name else ", senor"
    date_str = _fecha_espanol(now)

    closers = [
        "A su servicio, como siempre.",
        "A su entera disposicion.",
        "Listo para trabajar, senor.",
        "Aqui me tiene.",
        "Todos los sistemas en linea.",
        "Un placer volver a atenderle.",
    ]
    return f"{saludo}{name_part}. {_rnd.choice(closers)} Son las {date_str}."


# ===========================================================================
# Lifecycle: inicializa Jarvis al arrancar
# ===========================================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Inicializa todos los managers de Jarvis antes de aceptar requests."""
    log.info("Inicializando Jarvis Bridge...")
    state.started_at = time.time()

    # Provider Manager (detecta Ollama / API keys)
    state.provider_manager = ProviderManager()
    if not state.provider_manager.initialize():
        log.error("No se pudo inicializar ProviderManager — ningun proveedor disponible")
        # seguimos de todos modos, los endpoints devolveran error
    else:
        log.info(f"Proveedor activo: {state.provider_manager.current_provider_name}")

    # Detectores de comandos
    state.fast_cmd = FastCommandDetector()
    state.intent_router = IntentRouter()
    state.tool_executor = ToolExecutor()

    # Memoria
    state.memory = ConversationMemory()
    state.user_memory = UserMemory()
    state.user_memory.initialize()

    # RAG opcional
    if KnowledgeManager is not None:
        try:
            km = KnowledgeManager()
            if km.initialize():
                state.knowledge = km
                log.info(f"Base de conocimiento: {km.total_chunks} fragmentos")
        except Exception as e:
            log.warning(f"RAG no disponible: {e}")

    # Scheduler (recordatorios) — opcional pero util
    if TaskScheduler is not None:
        try:
            def _reminder_fire(msg: str):
                # Cuando un recordatorio dispara, lo mostramos en el chat como
                # mensaje de Jarvis + TTS lo habla.
                state.event_bus.publish({
                    "type": "response",
                    "text": f"Recordatorio: {msg}",
                    "source": "reminder",
                    "ts": datetime.now().isoformat(),
                })
                if state.voice and state.voice.available and not state.voice.is_paused:
                    try: state.voice.speak(f"Recordatorio, senor. {msg}")
                    except Exception: pass

            sch = TaskScheduler(
                telegram_io=None,
                console_callback=_reminder_fire,
            )
            sch.initialize()
            sch.start()
            state.scheduler = sch
            log.info("Scheduler de recordatorios iniciado")
        except Exception as e:
            log.warning(f"Scheduler no disponible: {e}")

    # Processor
    state.processor = JarvisProcessor(
        provider_manager=state.provider_manager,
        fast_cmd=state.fast_cmd,
        intent_router=state.intent_router,
        tool_executor=state.tool_executor,
        memory=state.memory,
        user_memory=state.user_memory,
        knowledge=state.knowledge,
    )

    # Registrar implementaciones de tools (RAG, memoria, scheduler, vision, etc.)
    _bind_tools()
    log.info("Tools ligados al agent loop")

    # Voice loop (mic + wake word + TTS) — opcional, solo si hay microfono
    try:
        vl = VoiceLoop(state.processor, state.event_bus.publish)
        if vl.initialize():
            vl.start()
            state.voice = vl
            log.info("Voz activa: diga 'Jarvis' + comando")
        else:
            log.info("Voz no disponible (sin microfono)")
    except Exception as e:
        log.warning(f"No se pudo iniciar el voice loop: {e}")

    # Generar el saludo ahora (no se entrega hasta que el primer cliente WS conecte)
    state.greeting_text = build_greeting(state.user_memory)
    log.info(f"Saludo preparado: {state.greeting_text}")

    # Telegram bot (opcional — solo si hay token configurado en el .env)
    try:
        from telegram_io import TelegramIO
        state.telegram_input_queue = queue.Queue()
        voice_for_tg = state.voice._tts if (state.voice and state.voice.available) else None
        tg = TelegramIO(
            state.telegram_input_queue,
            voice_engine=voice_for_tg,
            knowledge_manager=state.knowledge,
            provider_manager=state.provider_manager,
        )
        if tg.initialize():
            tg.start()
            state.telegram = tg
            log.info(f"Telegram activo: @{tg.bot_username or '?'}")

            # Consumer: procesa mensajes de Telegram con el mismo JarvisProcessor
            def _telegram_consumer():
                while not state.telegram_stop.is_set():
                    try:
                        item = state.telegram_input_queue.get(timeout=0.5)
                    except Exception:
                        continue
                    if not (isinstance(item, tuple) and len(item) >= 3):
                        continue
                    source, text, chat_id = item[0], item[1], item[2]
                    if source != "telegram" or not text or chat_id is None:
                        continue
                    as_voice = len(item) >= 4 and bool(item[3])
                    try:
                        result = state.processor.process(text, lambda e: None)
                        reply = (result.response or "").strip()
                        if not reply:
                            continue
                        if as_voice:
                            try:
                                state.telegram.send_voice_reply(chat_id, reply)
                            except Exception:
                                state.telegram.send_reply(chat_id, reply)
                        else:
                            state.telegram.send_reply(chat_id, reply)
                    except Exception as e:
                        log.warning(f"Telegram consumer error: {e}")
                        try:
                            state.telegram.send_reply(chat_id, f"Error: {e}")
                        except Exception:
                            pass

            consumer_t = threading.Thread(
                target=_telegram_consumer,
                daemon=True,
                name="jarvis-telegram-consumer",
            )
            consumer_t.start()

            # Saludo proactivo a los usuarios autorizados
            try:
                for uid in (tg.allowed_users or []):
                    try:
                        tg.send_reply(uid, state.greeting_text)
                    except Exception as e:
                        log.debug(f"No se pudo enviar saludo a {uid}: {e}")
            except Exception:
                pass
    except Exception as e:
        log.info(f"Telegram no iniciado: {e}")

    log.info("Jarvis Bridge listo.")
    yield
    log.info("Cerrando Jarvis Bridge...")
    try:
        state.telegram_stop.set()
        if state.telegram: state.telegram.stop()
    except Exception:
        pass
    try:
        if state.voice: state.voice.stop()
    except Exception:
        pass
    try:
        if state.scheduler: state.scheduler.stop()
    except Exception:
        pass
    try:
        state.memory.save_session()
    except Exception:
        pass


# ===========================================================================
# FastAPI app
# ===========================================================================

app = FastAPI(
    title="Jarvis Bridge",
    description="Servidor HTTP/WebSocket que expone Jarvis a clientes UI.",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS abierto solo para localhost (Electron carga desde file:// o localhost)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ===========================================================================
# Schemas
# ===========================================================================

class CommandIn(BaseModel):
    text: str = Field(..., min_length=1, description="Texto del usuario")


class CommandOut(BaseModel):
    response: str
    route: str
    classification: str = ""
    tool_name: Optional[str] = None
    tool_params: Optional[dict] = None
    tool_calls: list = Field(default_factory=list)
    model_used: Optional[str] = None
    error: Optional[str] = None


class StateOut(BaseModel):
    provider: str
    model: str
    light_model: str
    uptime_s: float
    rag_enabled: bool
    rag_chunks: int
    voice_available: bool = False
    voice_listening: bool = False


# ===========================================================================
# Endpoints REST
# ===========================================================================

@app.get("/api/health")
async def health():
    return {"ok": True, "uptime_s": time.time() - state.started_at}


@app.post("/api/voice/tts_ended")
async def voice_tts_ended():
    """Notificado por el frontend cuando termina de reproducir el audio TTS.
    Libera el STT (que estaba pausado mientras sonaba el audio) y emite
    el evento speaking:false al orbe para que vuelva a su estado natural."""
    if state.voice and state.voice.available:
        state.voice.tts_ended_notify()
    return {"ok": True}


@app.post("/api/voice/toggle")
async def voice_toggle():
    """Alterna pausa/reanuda del microfono. Retorna el nuevo estado."""
    if state.voice is None or not state.voice.available:
        return {"available": False, "listening": False}
    if state.voice.is_paused:
        state.voice.resume()
        listening = True
    else:
        state.voice.pause()
        listening = False
    return {"available": True, "listening": listening}


@app.get("/api/state", response_model=StateOut)
async def get_state():
    pm = state.provider_manager
    if pm is None:
        raise HTTPException(500, "provider manager not initialized")
    v = state.voice
    return StateOut(
        provider=pm.current_provider_name,
        model=Config.OLLAMA_MODEL,
        light_model=Config.OLLAMA_LIGHT_MODEL,
        uptime_s=time.time() - state.started_at,
        rag_enabled=state.knowledge is not None,
        rag_chunks=getattr(state.knowledge, "total_chunks", 0) if state.knowledge else 0,
        voice_available=(v is not None and v.available),
        voice_listening=(v is not None and v.available and not v.is_paused),
    )


@app.post("/api/command", response_model=CommandOut)
async def post_command(payload: CommandIn):
    """Procesa un comando de texto. Bloqueante por diseño — si tarda mucho,
    los eventos intermedios se pueden observar por WebSocket.
    """
    if state.processor is None:
        raise HTTPException(500, "processor not initialized")

    bus = state.event_bus
    loop = asyncio.get_event_loop()

    def _on_event(ev: dict):
        ev = {**ev, "ts": datetime.now().isoformat()}
        # thread-safe publish
        loop.call_soon_threadsafe(bus.publish, ev)

    # Ejecutar el procesamiento en un hilo para no bloquear el event loop
    result = await asyncio.to_thread(
        state.processor.process, payload.text, _on_event
    )

    # Emitir evento final al WS bus
    bus.publish({
        "type": "response",
        "text": result.response,
        "route": result.route,
        "classification": result.classification,
        "model_used": result.model_used,
        "error": result.error,
        "ts": datetime.now().isoformat(),
    })

    # TTS: Jarvis habla las respuestas, pero NUNCA los errores.
    if result.response and not result.error and state.voice and state.voice.available and not state.voice.is_paused:
        asyncio.create_task(asyncio.to_thread(state.voice.speak, result.response))

    return CommandOut(
        response=result.response,
        route=result.route,
        classification=result.classification,
        tool_name=result.tool_name,
        tool_params=result.tool_params,
        tool_calls=result.tool_calls,
        model_used=result.model_used,
        error=result.error,
    )


# ===========================================================================
# WebSocket
# ===========================================================================

@app.websocket("/ws/events")
async def ws_events(ws: WebSocket):
    await ws.accept()
    q = state.event_bus.subscribe()
    try:
        await ws.send_json({"type": "connected", "ts": datetime.now().isoformat()})

        # Entregar el saludo al PRIMER cliente que conecte (una vez por
        # sesion del bridge, igual que el CLI).
        # IMPORTANTE: enviamos el audio DIRECTO a este WS (no por el
        # event_bus) para que si hay multiples conexiones simultaneas
        # (React StrictMode en dev), el saludo se escuche una sola vez.
        if not state.greeting_delivered and state.greeting_text:
            state.greeting_delivered = True
            greeting = state.greeting_text
            # 1. Mensaje al chat (solo a este WS)
            await ws.send_json({
                "type": "response",
                "text": greeting,
                "source": "greeting",
                "ts": datetime.now().isoformat(),
            })
            # 2. Generar el audio TTS y enviarlo SOLO a este WS
            if state.voice and state.voice.available and not state.voice.is_paused:
                try:
                    # Generacion en hilo (no bloquear el event loop)
                    result = await asyncio.to_thread(state.voice._tts.generate_audio, greeting)
                    if result:
                        import base64
                        audio_bytes, fmt = result
                        await ws.send_json({
                            "type": "tts_audio",
                            "format": fmt,
                            "data": base64.b64encode(audio_bytes).decode("ascii"),
                            "ts": datetime.now().isoformat(),
                        })
                        # Pausar el STT durante el TTS del saludo
                        if state.voice._stt:
                            state.voice._stt.pause()
                        state.voice.emit({"type": "speaking", "value": True})
                        # Safety timeout por si el frontend no confirma fin
                        state.voice._schedule_tts_safety_timeout(greeting)
                except Exception as e:
                    log.warning(f"Greeting TTS fallo: {e}")

        while True:
            event = await q.get()
            await ws.send_json(event)
    except WebSocketDisconnect:
        pass
    except Exception as e:
        log.warning(f"WebSocket error: {e}")
    finally:
        state.event_bus.unsubscribe(q)


# ===========================================================================
# Entry point
# ===========================================================================

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1", help="Bind host")
    parser.add_argument("--port", type=int, default=17891, help="Bind port")
    parser.add_argument("--reload", action="store_true", help="Auto-reload en dev")
    args = parser.parse_args()

    uvicorn.run(
        "bridge.server:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
        log_level="info",
    )


if __name__ == "__main__":
    main()
