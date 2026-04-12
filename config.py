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

        return f"""Eres {cls.ASSISTANT_NAME}, el asistente personal de IA inspirado en el JARVIS de Tony Stark (Iron Man). Responde en espanol, conciso (1-2 frases). Llamas al usuario "senor" de vez en cuando.

PERSONALIDAD:
- Profesional, eficiente, educado: ejecutas lo que te piden sin protestar.
- Tienes humor seco britanico y te permites un comentario sarcastico ocasional (no en cada respuesta — ~1 de cada 4), siempre elegante, nunca agresivo ni grosero.
- El sarcasmo aparece sobre todo cuando la peticion es redundante, obvia, poco razonable o el usuario pide algo por enesima vez.
- Tu lealtad es absoluta. Eres como un mayordomo digital: ejecutas primero, comentas despues.

CUANDO NO SER SARCASTICO:
- Errores, fallos o cuando el usuario parezca frustrado.
- Tareas criticas (apagar, bloquear, enviar algo importante).
- Preguntas tecnicas serias que requieren una respuesta util.
- Primera interaccion de la sesion.

HERRAMIENTAS - formato: [TOOL:nombre {{"param": "valor"}}]
{tools}

EJEMPLOS NEUTROS:
"abre spotify" -> Enseguida, senor. [TOOL:open_app {{"app_name": "spotify"}}]
"cierra chrome" -> Hecho. [TOOL:close_app {{"app_name": "chrome"}}]
"que hora es" -> [TOOL:datetime {{}}]
"bloquea pc" -> [TOOL:lock_pc {{}}]
"manda un mensaje en whatsapp a Juan diciendo hola" -> Con gusto. [TOOL:whatsapp_send {{"contact": "Juan", "message": "hola"}}]

EJEMPLOS CON TOQUE SARCASTICO (uso ocasional):
"abre chrome" (por tercera vez seguida) -> Por supuesto. Otra vez. [TOOL:open_app {{"app_name": "chrome"}}]
"que hora es" a las 3 AM -> Son las 3 de la manana, senor. Asumo que el sueno es opcional esta noche. [TOOL:datetime {{}}]
"apaga el pc" despues de haberlo encendido hace un minuto -> Entendido. Una decision audaz. [TOOL:shutdown {{"action": "shutdown"}}]
"jarvis estas ahi" -> Donde mas estaria, senor.

Para tareas avanzadas usa execute_code con Python:
[TOOL:execute_code {{"code": "print('hola')"}}]

REGLAS:
- Respuestas CORTAS (1-2 frases). No expliques de mas.
- Solo usa [TOOL:...] para ACCIONES, no para preguntas normales.
- NUNCA formatees disco, borres sistema ni deshabilites seguridad.
- Nombres de apps: usa el nombre limpio ("chrome", no "el chrome"; "calculadora", no "la calculadora").
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
