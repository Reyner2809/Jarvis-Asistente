import queue
import time
import threading
import speech_recognition as sr
from rich.console import Console
from config import Config

console = Console()

LANGUAGE_CODES = {
    "es": "es-ES",
    "en": "en-US",
}

# Variantes de como Google puede transcribir "Jarvis" en español
WAKE_WORD_VARIANTS = [
    "jarvis", "yarbis", "jarbis", "yarvis", "llarbis",
    "jarbi", "yarbi", "jarbes", "jarves", "yarbis",
    "charvis", "charbis", "garvis", "garbis",
    "jar vis", "jar bis",
]

# Segundos que permanece en escucha activa despues de decir "Jarvis"
ACTIVE_LISTEN_TIMEOUT = 10


class SpeechToText:
    """Motor de reconocimiento de voz con wake word 'Jarvis'."""

    def __init__(self):
        self._recognizer = sr.Recognizer()
        self._microphone = None
        self._language = LANGUAGE_CODES.get(Config.VOICE_LANGUAGE, "es-ES")
        self._available = False
        self._listening = False
        self._paused = False
        self._queue = queue.Queue()
        self._wake_word = Config.ASSISTANT_NAME.lower()
        self._debug = False  # No mostrar todo lo que escucha

        # Estado de escucha activa: tras decir "Jarvis", acepta comandos sin wake word
        self._active_until = 0.0

        # Hilo de escucha propio (en vez de listen_in_background)
        self._listener_thread = None
        self._stop_event = threading.Event()

        # Ajustes de sensibilidad — optimizados para baja latencia.
        # pause_threshold mas corto (0.6s) hace que el reconocimiento dispare
        # mas rapido cuando el usuario termina de hablar, recortando ~0.6s
        # del tiempo total entre comando y ejecucion.
        self._recognizer.energy_threshold = 200
        self._recognizer.dynamic_energy_threshold = True
        self._recognizer.dynamic_energy_adjustment_damping = 0.15
        self._recognizer.pause_threshold = 0.6
        self._recognizer.non_speaking_duration = 0.4

    def initialize(self) -> bool:
        try:
            self._microphone = sr.Microphone()
            with self._microphone as source:
                console.print("  [cyan]Calibrando microfono...[/cyan]", end="")
                self._recognizer.adjust_for_ambient_noise(source, duration=2)
                console.print(" [green]listo[/green]")

            console.print(f"  [cyan]Reconocimiento de voz:[/cyan] Disponible")
            console.print(f"  [cyan]Palabra clave:[/cyan] \"{self._wake_word}\"")
            console.print(f"  [cyan]Idioma:[/cyan] {self._language}")
            self._available = True
            return True

        except OSError as e:
            console.print(f"  [yellow]No se detecto microfono: {e}[/yellow]")
            return False
        except Exception as e:
            console.print(f"  [yellow]Error inicializando microfono: {e}[/yellow]")
            return False

    @property
    def is_enabled(self) -> bool:
        return self._listening

    @property
    def is_available(self) -> bool:
        return self._available

    def set_debug(self, enabled: bool):
        self._debug = enabled

    def activate_listening(self):
        """Activa escucha temporal sin wake word (tras decir 'Jarvis')."""
        self._active_until = time.time() + ACTIVE_LISTEN_TIMEOUT

    def deactivate_listening(self):
        """Desactiva escucha activa."""
        self._active_until = 0.0

    @property
    def is_active_listening(self) -> bool:
        return time.time() < self._active_until

    def start_listening(self):
        if not self._available or self._listening:
            return

        self._listening = True
        self._paused = False
        self._stop_event.clear()

        self._listener_thread = threading.Thread(
            target=self._listen_loop,
            daemon=True,
        )
        self._listener_thread.start()

    def _listen_loop(self):
        """Hilo de escucha continua con auto-restart en caso de error."""
        while not self._stop_event.is_set():
            try:
                with self._microphone as source:
                    while not self._stop_event.is_set():
                        if self._paused:
                            time.sleep(0.1)
                            continue

                        try:
                            audio = self._recognizer.listen(
                                source,
                                timeout=2,
                                phrase_time_limit=15,
                            )
                        except sr.WaitTimeoutError:
                            # No se detecto voz en 2s, reintentar
                            continue

                        if self._paused:
                            continue

                        # Procesar audio en un hilo separado para no bloquear
                        threading.Thread(
                            target=self._process_audio,
                            args=(audio,),
                            daemon=True,
                        ).start()

            except Exception as e:
                # El microfono fallo - esperar un poco y reintentar
                if not self._stop_event.is_set():
                    if self._debug:
                        console.print(f"\n  [yellow]Mic error, reintentando: {e}[/yellow]")
                    time.sleep(1)
                    # Recalibrar microfono
                    try:
                        self._microphone = sr.Microphone()
                        with self._microphone as source:
                            self._recognizer.adjust_for_ambient_noise(source, duration=1)
                    except Exception:
                        time.sleep(2)

    def _process_audio(self, audio):
        """Procesa un fragmento de audio: transcribe y busca wake word."""
        try:
            text = self._recognizer.recognize_google(audio, language=self._language)
            if not text or not text.strip():
                return

            text = text.strip()
            text_lower = text.lower()

            # Debug: mostrar lo que escucha
            if self._debug:
                console.print(f"\n  [dim][mic] \"{text}\"[/dim]", end="")

            # Buscar wake word
            end_pos = self._find_wake_word(text_lower)

            if end_pos != -1:
                # Detectó "Jarvis" - extraer comando despues de la wake word
                command = text[end_pos:].strip()
                command = command.lstrip(",.:;!? ")

                if command:
                    # "Jarvis, haz algo" -> enviar el comando
                    self._active_until = 0.0
                    self._queue.put(command)
                else:
                    # Solo dijo "Jarvis" -> señal de wake
                    self._queue.put("__WAKE__")
                return

            # Si estamos en escucha activa (post-wake), aceptar sin wake word
            if self.is_active_listening:
                self._active_until = 0.0
                self._queue.put(text)
                return

            # No dijo "jarvis" y no esta en escucha activa -> ignorar

        except sr.UnknownValueError:
            pass
        except sr.RequestError:
            pass
        except Exception:
            pass

    def stop_listening(self):
        self._stop_event.set()
        self._listening = False
        if self._listener_thread and self._listener_thread.is_alive():
            self._listener_thread.join(timeout=3)
        self._listener_thread = None

    def pause(self):
        self._paused = True

    def resume(self):
        self._paused = False

    def get_speech(self, timeout: float = 0.1) -> str | None:
        try:
            return self._queue.get(timeout=timeout)
        except queue.Empty:
            return None

    def _find_wake_word(self, text_lower: str) -> int:
        """Busca la wake word en el texto. Retorna la posicion del final de la wake word, o -1."""
        if self._wake_word in text_lower:
            idx = text_lower.find(self._wake_word)
            return idx + len(self._wake_word)

        for variant in WAKE_WORD_VARIANTS:
            if variant in text_lower:
                idx = text_lower.find(variant)
                return idx + len(variant)

        return -1

    @staticmethod
    def is_wake_word(text: str) -> bool:
        """Verifica si un texto es solo la wake word (para uso desde main)."""
        import re
        clean = re.sub(
            r'^(?:jarvis|hey\s+jarvis|oye\s+jarvis|oye|hey)[,.\s]*$',
            '', text.strip(), flags=re.IGNORECASE
        )
        return clean == ""
