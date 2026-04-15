import time
from rich.console import Console
from .claude_provider import ClaudeProvider
from .openai_provider import OpenAIProvider
from .gemini_provider import GeminiProvider
from .ollama_provider import OllamaProvider
from config import Config

console = Console()

# Cuanto tiempo (segundos) marcamos un provider como "en cooldown" tras 429
_RATELIMIT_COOLDOWN_SEC = 300  # 5 min


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
        # provider_name -> timestamp hasta cuando esta en cooldown
        self._cooldown_until: dict[str, float] = {}

    def _is_in_cooldown(self, name: str) -> bool:
        until = self._cooldown_until.get(name, 0)
        return time.time() < until

    def _put_in_cooldown(self, name: str, reason: str = "rate-limit"):
        self._cooldown_until[name] = time.time() + _RATELIMIT_COOLDOWN_SEC
        console.print(f"  [yellow]{name.upper()} en cooldown {_RATELIMIT_COOLDOWN_SEC}s ({reason})[/yellow]")

    @staticmethod
    def _is_quota_error(err: Exception) -> bool:
        """Detecta errores de rate-limit / quota / 429."""
        msg = str(err).lower()
        return any(s in msg for s in ("429", "quota", "rate", "resource_exhausted", "too many"))

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

    def chat(self, messages: list, system_prompt: str, stream_callback=None, model_override: str | None = None) -> str:
        last_error = None

        for provider_name in self._fallback_order:
            provider = self._providers[provider_name]
            if not provider.is_available():
                continue
            if self._is_in_cooldown(provider_name):
                continue

            try:
                if provider != self._current:
                    console.print(
                        f"  [yellow]Cambiando a {provider_name.upper()}...[/yellow]"
                    )
                    self._current = provider

                # Pasar model_override solo a proveedores que lo soporten
                # (actualmente Ollama). El resto ignora el parametro.
                chat_params = provider.chat.__code__.co_varnames if hasattr(provider.chat, '__code__') else ()
                kwargs = {}
                if stream_callback and 'stream_callback' in chat_params:
                    kwargs['stream_callback'] = stream_callback
                if model_override and 'model_override' in chat_params:
                    kwargs['model_override'] = model_override
                return provider.chat(messages, system_prompt, **kwargs)

            except Exception as e:
                last_error = e
                if self._is_quota_error(e):
                    self._put_in_cooldown(provider_name, "429/quota")
                else:
                    console.print(
                        f"  [red]Error con {provider_name.upper()}: {e}[/red]"
                    )
                continue

        raise ConnectionError(
            f"Todos los proveedores fallaron. Ultimo error: {last_error}"
        )

    def search_and_answer(self, question: str) -> str | None:
        """Busca en internet con DuckDuckGo y resume con la IA activa."""
        from tools.web_search import search_internet
        from config import Config

        results = search_internet(question)
        if not results:
            return None

        # Construir prompt para que la IA resuma los resultados
        search_prompt = (
            f"Eres {Config.ASSISTANT_NAME}, asistente IA personal. "
            "El usuario hizo una pregunta que requiere informacion actual de internet. "
            "A continuacion estan los resultados de busqueda. "
            "Resume la informacion relevante en espanol, se conciso (2-4 frases max). "
            "Llama al usuario 'senor' a veces. "
            "NO digas 'segun los resultados' ni 'encontre en internet', responde como si supieras la info."
        )

        messages = [
            {"role": "user", "content": f"Pregunta: {question}\n\nResultados de internet:\n{results}"},
        ]

        # Usar el proveedor activo (Ollama u otro) para resumir
        last_error = None
        for provider_name in self._fallback_order:
            provider = self._providers[provider_name]
            if not provider.is_available():
                continue
            if self._is_in_cooldown(provider_name):
                continue
            try:
                return provider.chat(messages, search_prompt)
            except Exception as e:
                last_error = e
                if self._is_quota_error(e):
                    self._put_in_cooldown(provider_name, "429/quota")
                continue

        return None

    def agent_chat(
        self, messages, system_prompt, tools_schema,
        execute_fn=None, max_steps=5, on_tool_call=None, stream_callback=None,
        model_override: str | None = None,
    ) -> str:
        """Agent Loop: LLM con function calling nativo y multi-paso."""
        last_error = None
        for provider_name in self._fallback_order:
            provider = self._providers[provider_name]
            if not provider.is_available():
                continue
            if not hasattr(provider, "agent_chat"):
                continue
            if self._is_in_cooldown(provider_name):
                continue
            try:
                if provider != self._current:
                    console.print(f"  [yellow]Cambiando a {provider_name.upper()}...[/yellow]")
                    self._current = provider
                # Pasar model_override solo si el proveedor lo soporta
                ac_params = provider.agent_chat.__code__.co_varnames if hasattr(provider.agent_chat, '__code__') else ()
                if model_override and 'model_override' in ac_params:
                    return provider.agent_chat(
                        messages, system_prompt, tools_schema,
                        execute_fn, max_steps, on_tool_call, stream_callback,
                        model_override=model_override,
                    )
                return provider.agent_chat(
                    messages, system_prompt, tools_schema,
                    execute_fn, max_steps, on_tool_call, stream_callback,
                )
            except Exception as e:
                last_error = e
                if self._is_quota_error(e):
                    self._put_in_cooldown(provider_name, "429/quota")
                else:
                    console.print(f"  [red]Error con {provider_name.upper()}: {e}[/red]")
                continue
        raise ConnectionError(f"Agent loop fallo en todos los proveedores: {last_error}")

    def analyze_image(self, image_path: str, prompt: str = "") -> str | None:
        """Analiza una imagen con el proveedor activo (requiere modelo multimodal)."""
        for provider_name in self._fallback_order:
            provider = self._providers[provider_name]
            if not provider.is_available():
                continue
            if not hasattr(provider, "analyze_image"):
                continue
            try:
                return provider.analyze_image(image_path, prompt)
            except Exception as e:
                console.print(f"  [red]Error analizando imagen con {provider_name.upper()}: {e}[/red]")
                continue
        return None

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
