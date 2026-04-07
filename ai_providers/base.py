from abc import ABC, abstractmethod


class AIProvider(ABC):
    """Clase base para todos los proveedores de IA."""

    @property
    @abstractmethod
    def name(self) -> str:
        pass

    @abstractmethod
    def is_available(self) -> bool:
        pass

    @abstractmethod
    def chat(self, messages: list, system_prompt: str) -> str:
        pass
