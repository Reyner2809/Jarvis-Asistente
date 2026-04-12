import json
import os
from datetime import datetime


MEMORY_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
HISTORY_FILE = os.path.join(MEMORY_DIR, "conversation_history.json")
MAX_CONTEXT_MESSAGES = 20


class ConversationMemory:
    """Memoria de conversacion persistente con historial en JSON."""

    def __init__(self):
        self._messages: list = []
        self._session_start = datetime.now().isoformat()
        os.makedirs(MEMORY_DIR, exist_ok=True)

    @property
    def messages(self) -> list:
        return self._messages

    def add_message(self, role: str, content: str):
        self._messages.append({
            "role": role,
            "content": content,
            "timestamp": datetime.now().isoformat(),
        })

        if len(self._messages) > MAX_CONTEXT_MESSAGES:
            self._messages = self._messages[-MAX_CONTEXT_MESSAGES:]

    def get_context_messages(self) -> list:
        """Retorna mensajes formateados para enviar a la IA (sin timestamps)."""
        return [
            {"role": msg["role"], "content": msg["content"]}
            for msg in self._messages
        ]

    def clear(self):
        self._messages = []

    def save_session(self):
        history = []
        if os.path.exists(HISTORY_FILE):
            try:
                with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                    history = json.load(f)
            except (json.JSONDecodeError, IOError):
                history = []

        if self._messages:
            history.append({
                "session_start": self._session_start,
                "session_end": datetime.now().isoformat(),
                "messages": self._messages,
            })

            with open(HISTORY_FILE, "w", encoding="utf-8") as f:
                json.dump(history, f, ensure_ascii=False, indent=2)

    def get_stats(self) -> dict:
        user_msgs = sum(1 for m in self._messages if m["role"] == "user")
        assistant_msgs = sum(1 for m in self._messages if m["role"] == "assistant")
        return {
            "total": len(self._messages),
            "user": user_msgs,
            "assistant": assistant_msgs,
            "session_start": self._session_start,
        }
