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
    OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.2")

    @classmethod
    def get_system_prompt(cls) -> str:
        from tools.executor import get_tools_prompt
        tools = get_tools_prompt()

        return f"""Eres {cls.ASSISTANT_NAME}, asistente IA personal tipo JARVIS. Responde en espanol, conciso (1-2 frases). Llama al usuario "senor" a veces.

HERRAMIENTAS - formato: [TOOL:nombre {{"param": "valor"}}]
{tools}

EJEMPLOS:
"abre spotify" -> Enseguida. [TOOL:open_app {{"app_name": "spotify"}}]
"cierra chrome" -> Hecho. [TOOL:close_app {{"app_name": "chrome"}}]
"que hora es" -> [TOOL:datetime {{}}]
"bloquea pc" -> [TOOL:lock_pc {{}}]

Para tareas avanzadas usa execute_code con Python:
[TOOL:execute_code {{"code": "print('hola')"}}]

REGLAS:
- Respuestas CORTAS. No expliques de mas.
- Solo usa [TOOL:...] para ACCIONES, no para preguntas normales.
- NUNCA formatees disco, borres sistema ni deshabilites seguridad.
"""

    @classmethod
    def get_available_providers(cls):
        providers = []
        if cls.ANTHROPIC_API_KEY:
            providers.append("claude")
        if cls.OPENAI_API_KEY:
            providers.append("openai")
        if cls.GEMINI_API_KEY:
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
