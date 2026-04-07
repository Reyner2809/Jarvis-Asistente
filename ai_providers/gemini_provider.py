from .base import AIProvider
from config import Config


class GeminiProvider(AIProvider):

    def __init__(self):
        self._client = None

    @property
    def name(self) -> str:
        return "gemini"

    def is_available(self) -> bool:
        return bool(Config.GEMINI_API_KEY)

    def _get_client(self):
        if self._client is None:
            from google import genai
            self._client = genai.Client(api_key=Config.GEMINI_API_KEY)
        return self._client

    def chat(self, messages: list, system_prompt: str) -> str:
        client = self._get_client()

        # Construir historial para Gemini
        contents = []
        for msg in messages:
            role = "user" if msg["role"] == "user" else "model"
            contents.append({"role": role, "parts": [{"text": msg["content"]}]})

        response = client.models.generate_content(
            model=Config.GEMINI_MODEL,
            contents=contents,
            config={
                "system_instruction": system_prompt,
                "max_output_tokens": 4096,
            },
        )

        return response.text
