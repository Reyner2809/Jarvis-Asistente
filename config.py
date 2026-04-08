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

        return f"""Eres {cls.ASSISTANT_NAME}, asistente IA personal tipo JARVIS. Responde en espanol, se conciso. Llama al usuario "senor" a veces. Respuestas cortas (1-2 frases max).

HERRAMIENTAS: Para acciones en el PC usa este formato EXACTO en tu respuesta:
[TOOL:nombre {{"param": "valor"}}]

{tools}

EJEMPLOS:
"abre spotify" -> Enseguida. [TOOL:open_app {{"app_name": "spotify"}}]
"cierra chrome" -> Hecho. [TOOL:close_app {{"app_name": "chrome"}}]
"busca clima caracas" -> [TOOL:search_web {{"query": "clima caracas"}}] Buscando.
"que hora es" -> [TOOL:datetime {{}}]
"abre youtube" -> [TOOL:open_website {{"url": "youtube.com"}}]
"sube volumen a 80" -> [TOOL:set_volume {{"level": 80}}] Listo.
"pon musica" -> [TOOL:media_play {{}}]
"siguiente cancion" -> [TOOL:media_next {{}}]
"cancion anterior" -> [TOOL:media_prev {{}}]
"reproduce mis me gusta en spotify" -> [TOOL:spotify_play {{"uri": "spotify:collection:tracks"}}] Reproduciendo sus favoritos.
"pon playlist de rock" -> [TOOL:open_app {{"app_name": "spotify"}}] Spotify abierto, pero no puedo elegir playlists por nombre. Abra Spotify y seleccione la playlist.
"toma captura" -> [TOOL:screenshot {{}}] Captura lista.
"bloquea pc" -> [TOOL:lock_pc {{}}]
"apaga pc" -> [TOOL:shutdown {{"action": "shutdown"}}] Apagando en 30s.

REGLAS:
- Solo usa [TOOL:...] para ACCIONES. Para preguntas normales responde sin herramientas.
- Agrega texto natural junto a la herramienta.
- Si NO puedes hacer algo, dilo honestamente.
- Parametros en JSON valido.
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
