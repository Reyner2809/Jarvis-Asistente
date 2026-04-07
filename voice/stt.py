import speech_recognition as sr
from rich.console import Console
from config import Config

console = Console()

LANGUAGE_CODES = {
    "es": "es-ES",
    "en": "en-US",
}


class SpeechToText:
    """Motor de reconocimiento de voz usando el microfono."""

    def __init__(self):
        self._recognizer = sr.Recognizer()
        self._microphone = None
        self._language = LANGUAGE_CODES.get(Config.VOICE_LANGUAGE, "es-ES")
        self._enabled = False
        self._wake_word = Config.ASSISTANT_NAME.lower()

        # Ajustes de sensibilidad
        self._recognizer.energy_threshold = 300
        self._recognizer.dynamic_energy_threshold = True
        self._recognizer.pause_threshold = 1.0

    def initialize(self) -> bool:
        try:
            self._microphone = sr.Microphone()
            # Calibrar microfono con ruido ambiente
            with self._microphone as source:
                console.print("  [cyan]Calibrando microfono...[/cyan]", end="")
                self._recognizer.adjust_for_ambient_noise(source, duration=2)
                console.print(" [green]listo[/green]")

            console.print(f"  [cyan]Reconocimiento de voz:[/cyan] Activo")
            console.print(f"  [cyan]Idioma:[/cyan] {self._language}")
            console.print(f"  [cyan]Palabra clave:[/cyan] \"{self._wake_word}\"")
            return True

        except OSError as e:
            console.print(f"  [yellow]No se detecto microfono: {e}[/yellow]")
            console.print(f"  [yellow]El modo voz no estara disponible.[/yellow]")
            return False
        except Exception as e:
            console.print(f"  [yellow]Error inicializando microfono: {e}[/yellow]")
            return False

    @property
    def is_enabled(self) -> bool:
        return self._enabled

    def toggle(self) -> bool:
        if self._microphone is None:
            console.print("[red]No hay microfono disponible.[/red]")
            return False

        self._enabled = not self._enabled
        state = "activado" if self._enabled else "desactivado"
        console.print(f"[cyan]Modo escucha {state}[/cyan]")

        if self._enabled:
            console.print(f'[dim]Di "{self._wake_word}" para activarme o habla directamente.[/dim]')
            console.print(f'[dim]Presiona Enter sin texto para escuchar. Escribe para usar texto.[/dim]')

        return self._enabled

    def listen(self, timeout: int = 8, phrase_limit: int = 30) -> str | None:
        """Escucha el microfono y retorna el texto reconocido."""
        if not self._enabled or self._microphone is None:
            return None

        try:
            with self._microphone as source:
                console.print("[bold cyan]  Escuchando...[/bold cyan] ", end="")
                audio = self._recognizer.listen(
                    source,
                    timeout=timeout,
                    phrase_time_limit=phrase_limit,
                )

            console.print("[yellow]procesando...[/yellow]")

            # Usar Google Speech Recognition (gratis, sin API key)
            text = self._recognizer.recognize_google(
                audio,
                language=self._language,
            )

            console.print(f'  [green]Escuche:[/green] "{text}"')
            return text

        except sr.WaitTimeoutError:
            console.print("[dim]no se detecto voz[/dim]")
            return None
        except sr.UnknownValueError:
            console.print("[yellow]no entendi, repite por favor[/yellow]")
            return None
        except sr.RequestError as e:
            console.print(f"[red]Error de reconocimiento: {e}[/red]")
            return None
        except Exception as e:
            console.print(f"[red]Error: {e}[/red]")
            return None

    def listen_continuous(self, callback, stop_event):
        """Escucha continuamente en segundo plano (para modo wake word futuro)."""
        if not self._enabled or self._microphone is None:
            return

        stop_listening = self._recognizer.listen_in_background(
            self._microphone,
            lambda rec, audio: self._background_callback(rec, audio, callback),
            phrase_time_limit=30,
        )

        stop_event.wait()
        stop_listening(wait_for_stop=False)

    def _background_callback(self, recognizer, audio, callback):
        try:
            text = recognizer.recognize_google(audio, language=self._language)
            if text:
                callback(text)
        except (sr.UnknownValueError, sr.RequestError):
            pass
