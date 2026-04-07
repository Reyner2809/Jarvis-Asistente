import json
import urllib.request
import urllib.error
from .base import AIProvider
from config import Config


class OllamaProvider(AIProvider):
    """Proveedor local usando Ollama. Gratis, sin API key, sin limites."""

    def __init__(self):
        self._base_url = "http://localhost:11434"

    @property
    def name(self) -> str:
        return "ollama"

    def is_available(self) -> bool:
        try:
            req = urllib.request.Request(f"{self._base_url}/api/tags")
            with urllib.request.urlopen(req, timeout=3) as resp:
                return resp.status == 200
        except Exception:
            return False

    def chat(self, messages: list, system_prompt: str) -> str:
        ollama_messages = [{"role": "system", "content": system_prompt}]
        for msg in messages:
            ollama_messages.append({
                "role": msg["role"],
                "content": msg["content"],
            })

        payload = json.dumps({
            "model": Config.OLLAMA_MODEL,
            "messages": ollama_messages,
            "stream": False,
        }).encode("utf-8")

        req = urllib.request.Request(
            f"{self._base_url}/api/chat",
            data=payload,
            headers={"Content-Type": "application/json"},
        )

        with urllib.request.urlopen(req, timeout=120) as resp:
            data = json.loads(resp.read().decode("utf-8"))

        return data["message"]["content"]
