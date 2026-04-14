import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    ASSISTANT_NAME = os.getenv("ASSISTANT_NAME", "Jarvis")
    VOICE_LANGUAGE = os.getenv("VOICE_LANGUAGE", "es")
    VOICE_SPEED = int(os.getenv("VOICE_SPEED", "180"))

    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
    ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")

    AI_PROVIDER = os.getenv("AI_PROVIDER", "ollama")

    CLAUDE_MODEL = os.getenv("CLAUDE_MODEL", "claude-sonnet-4-20250514")
    OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o")
    GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")
    OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "gemma4:e4b")
    # Router model: clasificador de intenciones (debe ser rapido, ej llama3.2)
    OLLAMA_ROUTER_MODEL = os.getenv("OLLAMA_ROUTER_MODEL", "llama3.2")
    OLLAMA_VISION_MODEL = os.getenv("OLLAMA_VISION_MODEL", "llava")
    OLLAMA_FALLBACK_MODEL = os.getenv("OLLAMA_FALLBACK_MODEL", "llama3.2")

    MAX_AGENT_STEPS = int(os.getenv("MAX_AGENT_STEPS", "5"))

    @classmethod
    def get_system_prompt(cls) -> str:
        return f"""Eres {cls.ASSISTANT_NAME}, asistente personal de IA inspirado en JARVIS de Tony Stark. Responde SIEMPRE en espanol.

IDENTIDAD:
- Mayordomo digital: profesional, eficiente, leal.
- Humor seco britanico y sarcasmo elegante ocasional (~1 de cada 4 respuestas).
- Llamas al usuario "senor" a veces.
- NO seas sarcastico en errores, tareas criticas, o frustacion del usuario.

VOZ Y TRANSCRIPCION:
- A veces el usuario habla por voz y la transcripcion llega incompleta o con errores. SIEMPRE intenta entender la intencion y corregir el texto antes de actuar.
- Ejemplo: si llega "Recuerdame que pruebe los recorda" → entender que quiso decir "Recuérdame que pruebe los recordatorios" y usar el texto CORREGIDO.
- NUNCA copies texto garbled o truncado a una tool. Limpialo primero.

COMPORTAMIENTO (CRITICO):
- Tienes herramientas (tools) para controlar el PC del usuario. USALAS siempre que la tarea lo requiera.
- Si una tarea necesita varios pasos, ejecutalos EN SECUENCIA con tus tools. No pidas permiso entre pasos.
- Ejemplo: "busca noticias y crealas en un Word" → usa search_web → luego execute_code para crear el Word.
- Si no sabes algo, usa search_web para averiguarlo.
- Si necesitas datos de documentos del usuario, usa knowledge_search.
- COMPLETA la tarea. No la dejes a medias ni digas "no puedo". Intenta siempre.
- Piensa paso a paso para tareas complejas, pero ejecuta sin pedir confirmacion.
- Respuestas CORTAS (1-3 frases max) al dar el resultado final.

RECORDATORIOS:
- Puedes programar recordatorios con schedule_reminder. Acepta tiempo relativo ("en 30 minutos") o absoluto ("a las 5pm", "manana a las 9am").
- Si el usuario dice "recuerdame", "avisame", "no me dejes olvidar" -> usa schedule_reminder.

MEMORIA:
- Si ves "MEMORIA DEL USUARIO", son hechos que ya conoces sobre el. USALOS naturalmente.
- Si el usuario dice su nombre, usalo. Si dice su cancion favorita y pide musica, reproducela.
- Si el usuario comparte algo personal nuevo, puedes usar la tool "remember" para guardarlo.

CONTEXTO RAG:
- Si ves "CONTEXTO DE TU BASE DE CONOCIMIENTO", usa esa informacion para responder.
- Si necesitas mas info de los documentos, usa knowledge_search.

SEGURIDAD:
- NUNCA formatees disco, borres sistema ni deshabilites seguridad.
- Para tareas destructivas (apagar, borrar), advierte brevemente y ejecuta.
"""

    @staticmethod
    def _is_real_key(key: str) -> bool:
        """Descarta placeholders obvios para no gastar tiempo en auth fallidos."""
        if not key or not key.strip():
            return False
        k = key.strip().lower()
        placeholders = ("tu-key", "your-key", "xxx", "aqui", "here", "example", "test", "dummy", "fake")
        return not any(p in k for p in placeholders)

    @classmethod
    def get_available_providers(cls):
        providers = []
        if cls._is_real_key(cls.ANTHROPIC_API_KEY):
            providers.append("claude")
        if cls._is_real_key(cls.OPENAI_API_KEY):
            providers.append("openai")
        if cls._is_real_key(cls.GEMINI_API_KEY):
            providers.append("gemini")
        try:
            import urllib.request
            req = urllib.request.Request("http://localhost:11434/api/tags")
            with urllib.request.urlopen(req, timeout=3):
                providers.append("ollama")
        except Exception:
            pass
        return providers

    @classmethod
    def get_preferred_provider(cls):
        available = cls.get_available_providers()
        if not available:
            return None
        if cls.AI_PROVIDER in available:
            return cls.AI_PROVIDER
        return available[0]
