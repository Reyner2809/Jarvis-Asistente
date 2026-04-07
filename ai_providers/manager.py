from rich.console import Console
from .claude_provider import ClaudeProvider
from .openai_provider import OpenAIProvider
from .gemini_provider import GeminiProvider
from .ollama_provider import OllamaProvider
from config import Config

console = Console()


class ProviderManager:
    """Gestiona los proveedores de IA con fallback automatico."""

    def __init__(self):
        self._providers = {
            "claude": ClaudeProvider(),
            "openai": OpenAIProvider(),
            "gemini": GeminiProvider(),
            "ollama": OllamaProvider(),
        }
        self._current = None
        self._fallback_order = ["claude", "openai", "gemini", "ollama"]

    @property
    def current_provider_name(self) -> str:
        if self._current:
            return self._current.name
        return "ninguno"

    def initialize(self) -> bool:
        preferred = Config.get_preferred_provider()
        if preferred is None:
            console.print(
                "[bold red]ERROR: No hay proveedores disponibles.[/bold red]\n"
                "Configura al menos una API key en .env o instala Ollama."
            )
            return False

        self._current = self._providers[preferred]

        available = Config.get_available_providers()
        self._fallback_order = [preferred] + [p for p in self._fallback_order if p != preferred and p in available]

        console.print(f"  [cyan]Proveedor activo:[/cyan] {preferred.upper()}")
        console.print(f"  [cyan]Fallback:[/cyan] {' -> '.join(p.upper() for p in self._fallback_order)}")

        return True

    def chat(self, messages: list, system_prompt: str) -> str:
        last_error = None

        for provider_name in self._fallback_order:
            provider = self._providers[provider_name]
            if not provider.is_available():
                continue

            try:
                if provider != self._current:
                    console.print(
                        f"  [yellow]Cambiando a {provider_name.upper()}...[/yellow]"
                    )
                    self._current = provider

                return provider.chat(messages, system_prompt)

            except Exception as e:
                last_error = e
                console.print(
                    f"  [red]Error con {provider_name.upper()}: {e}[/red]"
                )
                continue

        raise ConnectionError(
            f"Todos los proveedores fallaron. Ultimo error: {last_error}"
        )

    def switch_provider(self, provider_name: str) -> bool:
        provider_name = provider_name.lower()
        if provider_name not in self._providers:
            console.print(f"[red]Proveedor '{provider_name}' no existe. Usa: claude, openai, gemini, ollama[/red]")
            return False

        provider = self._providers[provider_name]
        if not provider.is_available():
            console.print(f"[red]{provider_name.upper()} no esta disponible. Verifica la API key o que Ollama este corriendo.[/red]")
            return False

        self._current = provider
        self._fallback_order = [provider_name] + [p for p in self._fallback_order if p != provider_name]
        console.print(f"[green]Proveedor cambiado a {provider_name.upper()}[/green]")
        return True
