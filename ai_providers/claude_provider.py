from .base import AIProvider
from config import Config


class ClaudeProvider(AIProvider):

    def __init__(self):
        self._client = None

    @property
    def name(self) -> str:
        return "claude"

    def is_available(self) -> bool:
        return bool(Config.ANTHROPIC_API_KEY)

    def _get_client(self):
        if self._client is None:
            from anthropic import Anthropic
            self._client = Anthropic(api_key=Config.ANTHROPIC_API_KEY)
        return self._client

    def chat(self, messages: list, system_prompt: str) -> str:
        client = self._get_client()

        claude_messages = []
        for msg in messages:
            claude_messages.append({
                "role": msg["role"],
                "content": msg["content"],
            })

        response = client.messages.create(
            model=Config.CLAUDE_MODEL,
            max_tokens=4096,
            system=system_prompt,
            messages=claude_messages,
        )

        return response.content[0].text
