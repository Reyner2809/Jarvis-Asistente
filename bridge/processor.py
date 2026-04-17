"""
JarvisProcessor: encapsula la logica de ruteo de un input del usuario
(fast_commands -> intent_router -> internet -> chat/agent).

Mismo comportamiento que el loop principal de main.py, pero extraido en una
funcion/clase reutilizable para que el bridge HTTP la use sin duplicar logica
ni acoplarse a console/voz/telegram.

El CLI (main.py) NO se toca: este modulo es self-contained.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Callable, Optional

from config import Config


# ===========================================================================
# Clasificador heuristico — espejo del de main.py para mantener paridad.
# Si el comportamiento diverge en el futuro, centralizar aqui.
# ===========================================================================

_HEAVY_TASK_RE = re.compile(
    r"\b("
    r"analiza(?:me)?|analizalo|analizala|analizar|analisis|"
    r"hazme\s+(?:un|una)\s+(?:script|codigo|programa|funcion|ensayo|articulo|redaccion|carta|correo|email|resumen\s+(?:largo|detallado|completo)|comparacion|tabla|plan|plantilla|presentacion)|"
    r"escribeme\s+(?:un|una)\s+(?:script|codigo|programa|funcion|ensayo|articulo|carta|correo|email|poema|cancion|historia|cuento|plan)|"
    r"(?:pasa|dame|generame|crea(?:me)?)\s+(?:un|una)\s+(?:script|codigo|programa|funcion|snippet|ejemplo\s+de\s+codigo)|"
    r"corrigeme|corrige\s+(?:este|el|la|mi)|debug(?:uea|gea)?|depura|arregla\s+(?:este|el|la|mi|mi\s+codigo)|"
    r"revisa\s+(?:mi|este|el|la)\s+(?:codigo|script|error|funcion|programa)|"
    r"como\s+funciona(?:n)?\s+(?:un|una|el|la|los|las)|"
    r"por\s*que\s+(?:sucede|pasa|es|ocurre)|"
    r"explicame\s+(?:a\s+fondo|en\s+detalle|detalladamente|el\s+concepto|como\s+funciona|por\s*que)|"
    r"que\s+es\s+(?:un|una|el\s+concepto)|"
    r"investiga(?:me)?|investigar|compara(?:me)?(?:\s+entre)?|"
    r"resume\s+(?:este|el|ese|mi)\s+(?:documento|archivo|pdf|texto|file)|"
    r"resumeme\s+(?:este|el|ese|mi)"
    r")\b",
    re.IGNORECASE,
)

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

_INTERNET_PATTERNS = [
    r"noticia|noticias|que\s+(?:esta|está)\s+pasando|que\s+(?:ha|hay)\s+pasado",
    r"clima|(?:que|cómo)\s+(?:tal\s+)?(?:el\s+)?(?:tiempo|temperatura)|va\s+a\s+llover|pronostico",
    r"precio\s+de|cotizacion|(?:cuanto|cuánto)\s+(?:vale|cuesta)|dolar|bitcoin|bolsa",
    r"resultado|marcador|(?:quien|quién)\s+(?:gano|ganó)|partido\s+de|score",
    r"hoy\s+(?:en|que)|esta\s+semana|actualmente|actual|reciente|ultimo|última|últim",
    r"(?:busca|buscame|dime)\s+(?:informacion|info)\s+(?:sobre|de|del)",
    r"(?:que|qué)\s+(?:sabes|hay)\s+(?:sobre|de|del|acerca)",
    r"(?:investiga|averigua|encuentra)\s+(?:sobre|de|del|acerca|info)",
    r"(?:investiga|averigua|encuentra|consulta)\s+(?:que|qué|cual|cuál|como|cómo|cuando|cuándo|donde|dónde|por\s*que|porqué|quien|quién|cuanto|cuánto|con\s+(?:que|qué)|en\s+(?:que|qué)|de\s+(?:que|qué)|para\s+(?:que|qué))",
    r"(?:investiga|averigua|encuentra|busca|buscame|dime|consulta)\s+(?:en\s+)?(?:internet|la\s+web|google|la\s+red)",
    r"(?:quien|quién)\s+es\s+(?:el|la)\s+(?:presidente|primer\s+ministro)",
    r"(?:cuando|cuándo)\s+(?:es|sera|será)\s+(?:el|la|los|las)",
]
_internet_re = re.compile("|".join(_INTERNET_PATTERNS), re.IGNORECASE)


def classify_input(text: str) -> str:
    """Clasifica: 'heavy' | 'action' | 'simple'."""
    t = text.strip()
    if _HEAVY_TASK_RE.search(t):
        return "heavy"
    if _ACTION_VERB_RE.match(t):
        return "action"
    return "simple"


def needs_internet(text: str) -> bool:
    return bool(_internet_re.search(text))


# ===========================================================================
# Resultado del procesamiento
# ===========================================================================

@dataclass
class ProcessResult:
    response: str = ""
    route: str = ""        # 'fast' | 'intent_router' | 'internet' | 'chat' | 'agent' | 'error'
    classification: str = ""  # 'heavy' | 'action' | 'simple'
    tool_name: Optional[str] = None
    tool_params: Optional[dict] = None
    tool_calls: list = field(default_factory=list)  # para agent loop
    model_used: Optional[str] = None
    error: Optional[str] = None


# ===========================================================================
# Procesador principal
# ===========================================================================

class JarvisProcessor:
    """
    Procesa un input del usuario. Mantiene referencias a los managers que
    ya existen en el sistema (no los duplica). Es seguro compartir la
    misma instancia entre el bridge HTTP y el CLI (a futuro), aunque
    actualmente cada uno puede tener la suya.
    """

    def __init__(
        self,
        provider_manager,
        fast_cmd,
        intent_router,
        tool_executor,
        memory,
        user_memory,
        knowledge=None,
    ):
        self.provider_manager = provider_manager
        self.fast_cmd = fast_cmd
        self.intent_router = intent_router
        self.tool_executor = tool_executor
        self.memory = memory
        self.user_memory = user_memory
        self.knowledge = knowledge

    def _build_rag_context(self, user_input: str) -> Optional[str]:
        """Igual que _build_rag_context en main.py."""
        if self.knowledge is None or getattr(self.knowledge, "total_chunks", 0) == 0:
            return None
        _doc_meta_re = re.compile(
            r"(?:resum|resume|resumen|resumeme|resumelo|resumela|resumir)"
            r"|(?:de\s+que\s+(?:trata|habla|va|se\s+trata))"
            r"|(?:que\s+(?:dice|contiene|tiene|trae))\s+(?:el|ese|este|mi|lo|la)?\s*(?:documento|archivo|doc|pdf|texto|file)"
            r"|(?:analiza|analisis)\s+(?:del?|el|ese|este|mi|lo)?\s*(?:documento|archivo)"
            r"|(?:lo\s+que\s+(?:te\s+)?(?:cargue|subi|envie|mande))",
            re.IGNORECASE,
        )
        if _doc_meta_re.search(user_input):
            full = self.knowledge.get_all_content()
            if full:
                return full
        return self.knowledge.build_context(user_input, top_k=5)

    def process(
        self,
        text: str,
        on_event: Optional[Callable[[dict], None]] = None,
    ) -> ProcessResult:
        """
        Ruta un input del usuario por el pipeline y devuelve el resultado.

        on_event(dict): callback opcional para eventos en tiempo real. Tipos:
          - {"type": "route", "route": "fast|intent|internet|chat|agent"}
          - {"type": "classification", "value": "action|heavy|simple"}
          - {"type": "tool_call", "step": n, "name": str, "args": dict}
          - {"type": "thinking"} / {"type": "searching"}
        """
        result = ProcessResult()

        if not text or not text.strip():
            result.error = "empty input"
            return result

        # Extraer hechos personales del input (como hace main.py)
        try:
            self.user_memory.extract_facts(text)
        except Exception:
            pass

        # === FAST PATH: regex puro, instantaneo ===
        try:
            handled, fast_response = self.fast_cmd.try_execute(text)
            if handled:
                result.response = fast_response
                result.route = "fast"
                self.memory.add_message("user", text)
                self.memory.add_message("assistant", fast_response)
                if on_event:
                    on_event({"type": "route", "route": "fast"})
                return result
        except Exception as e:
            if on_event:
                on_event({"type": "warn", "msg": f"fast_cmd fallo: {e}"})

        # === CLASIFICAR ===
        cls = classify_input(text)
        result.classification = cls
        if on_event:
            on_event({"type": "classification", "value": cls})

        # === INTENT ROUTER (para acciones) ===
        _looks_like_question = bool(re.match(
            r'^(?:que|qué|como|cómo|cuando|cuándo|donde|dónde|por\s*que|porqué|'
            r'cual|cuál|cuanto|cuánto|quien|quién|explicame|cuentame|dime\s+(?:un|algo)|'
            r'sabes|puedes\s+(?:explicar|decir|contar))\b',
            text.lower(),
        ))
        _is_compound_task = (cls == "heavy") and bool(re.search(
            r'\by\s+(?:dime|crea|crealas|crealo|ponlas|ponlo|manda|mandame|mandale|'
            r'enviale|envia|enviame|resume|resumelo|resumeme|guarda|guardalo|analiza)\b',
            text.lower(),
        ))

        intent = None
        if cls == "action" or (not _looks_like_question and not _is_compound_task and cls != "heavy"):
            try:
                intent = self.intent_router.classify(text)
            except Exception as e:
                if on_event:
                    on_event({"type": "warn", "msg": f"intent_router fallo: {e}"})

        if intent is not None:
            tool_name = intent["tool"]
            params = intent["params"]
            result.route = "intent_router"
            result.tool_name = tool_name
            result.tool_params = params
            if on_event:
                on_event({"type": "route", "route": "intent_router"})
                on_event({"type": "tool_call", "step": 0, "name": tool_name, "args": params})
            try:
                exec_result = self.tool_executor._execute_tool(tool_name, params)
                result.response = exec_result.get("message", "Hecho, senor.")
                self.memory.add_message("user", text)
                self.memory.add_message("assistant", result.response)
                return result
            except Exception as e:
                result.error = f"tool execution failed: {e}"
                return result

        # === INTERNET PATH ===
        if needs_internet(text):
            if on_event:
                on_event({"type": "route", "route": "internet"})
                on_event({"type": "searching"})
            self.memory.add_message("user", text)
            try:
                response = self.provider_manager.search_and_answer(text)
                if response:
                    result.response = response
                    result.route = "internet"
                    self.memory.add_message("assistant", response)
                    return result
                # si no hubo resultados, caer al agent path con advertencia
                self.memory.messages.pop()
            except Exception as e:
                result.error = f"internet search failed: {e}"
                self.memory.messages.pop()

        # === CHAT / AGENT PATH ===
        # Inyectar memoria + RAG
        context_parts = []
        mem_ctx = self.user_memory.build_context() if self.user_memory else None
        if mem_ctx:
            context_parts.append(mem_ctx)
        rag_ctx = self._build_rag_context(text)
        if rag_ctx:
            context_parts.append(rag_ctx)
        augmented = (
            "\n\n".join(context_parts) + "\n\nPREGUNTA DEL USUARIO: " + text
            if context_parts else text
        )
        self.memory.add_message("user", augmented)

        # Modelo: pesado solo para tareas 'heavy'; ligero para el resto
        if cls == "heavy":
            model_override = None
            max_steps = Config.MAX_AGENT_STEPS
        else:
            model_override = Config.OLLAMA_LIGHT_MODEL
            max_steps = Config.MAX_AGENT_STEPS_LIGHT

        result.model_used = model_override or Config.OLLAMA_MODEL

        system_prompt = Config.get_system_prompt()

        try:
            if _looks_like_question or cls == "simple":
                # Chat sin tools (rapido)
                result.route = "chat"
                if on_event:
                    on_event({"type": "route", "route": "chat"})
                    on_event({"type": "thinking"})
                response = self.provider_manager.chat(
                    self.memory.get_context_messages(),
                    system_prompt,
                    model_override=model_override,
                )
            else:
                # Agent loop con tools
                result.route = "agent"
                if on_event:
                    on_event({"type": "route", "route": "agent"})
                    on_event({"type": "thinking"})
                from tools.executor import get_tools_schema, execute_tool_call

                def _on_tool(step, name, args):
                    result.tool_calls.append({"step": step, "name": name, "args": args})
                    if on_event:
                        on_event({"type": "tool_call", "step": step, "name": name, "args": args})

                response = self.provider_manager.agent_chat(
                    messages=self.memory.get_context_messages(),
                    system_prompt=system_prompt,
                    tools_schema=get_tools_schema(),
                    execute_fn=execute_tool_call,
                    max_steps=max_steps,
                    on_tool_call=_on_tool,
                    model_override=model_override,
                )

            result.response = response or ""
            if response:
                self.memory.add_message("assistant", response)
            return result

        except Exception as e:
            # Limpiar el ultimo user message fallido para no contaminar memoria
            try:
                self.memory.messages.pop()
            except Exception:
                pass
            result.error = str(e)
            result.response = ""
            return result
