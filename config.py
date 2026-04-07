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

    SYSTEM_PROMPT = f"""Tu nombre es {ASSISTANT_NAME}. Eres un asistente de inteligencia artificial personal avanzado, inspirado en JARVIS de Iron Man.

Tu personalidad:
- Inteligente, eficiente y con un toque de humor sutil.
- Tono profesional pero cercano, como un mayordomo digital de confianza.
- Ocasionalmente te refieres al usuario como "senor" o "senora", al estilo JARVIS.

Reglas:
- Responde siempre en espanol a menos que te pidan otro idioma.
- Se conciso pero completo. No des respuestas innecesariamente largas.
- Si no sabes algo, dilo honestamente.
- Puedes hacer calculos, analizar datos, escribir codigo y responder preguntas generales.
- Cuando el usuario te salude, presentate brevemente diciendo tu nombre ({ASSISTANT_NAME}) y que estas a su servicio.
- NUNCA digas "Eres" como parte de tu nombre. Tu nombre es solamente {ASSISTANT_NAME}.
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
        # Ollama no necesita API key, verificar si esta corriendo
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
