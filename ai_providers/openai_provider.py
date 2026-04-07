from .base import AIProvider
from config import Config


class OpenAIProvider(AIProvider):

    def __init__(self):
        self._client = None

    @property
    def name(self) -> str:
        return "openai"

    def is_available(self) -> bool:
        return bool(Config.OPENAI_API_KEY)

    def _get_client(self):
        if self._client is None:
            from openai import OpenAI
            self._client = OpenAI(api_key=Config.OPENAI_API_KEY)
        return self._client

    def chat(self, messages: list, system_prompt: str) -> str:
        client = self._get_client()

        openai_messages = [{"role": "system", "content": system_prompt}]
        for msg in messages:
            openai_messages.append({
                "role": msg["role"],
                "content": msg["content"],
            })

        response = client.chat.completions.create(
            model=Config.OPENAI_MODEL,
            messages=openai_messages,
            max_tokens=4096,
        )

        return response.choices[0].message.content
