"""
Motor de voz (TTS) de Jarvis — cascada de calidad.

Estrategia de prioridad:
  1. edge-tts           (ONLINE, voz neural de Microsoft, la mejor calidad)
  2. Piper TTS          (OFFLINE, voz neural local — suena natural y grave)
  3. pyttsx3 (SAPI)     (OFFLINE fallback si no hay modelo Piper — robotico pero funciona)

Jarvis funciona 100% offline si los modelos Piper estan descargados en
voice/piper_voices/. El instalador se encarga de bajarlos.
"""

import asyncio
import os
import sys
import tempfile
import time
from rich.console import Console
from config import Config

console = Console()

EDGE_TTS_VOICES = {
    "es": "es-VE-SebastianNeural",
    "en": "en-US-GuyNeural",
}

# Modelos Piper por idioma — archivos descargados por el instalador.
# "sharvard" para ES: voz masculina grave, ideal para mayordomo estilo JARVIS.
# "ryan" para EN: voz masculina americana clara.
PIPER_VOICES = {
    "es": "es_ES-sharvard-medium",
    "en": "en_US-ryan-medium",
}
PIPER_VOICES_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "piper_voices")

# Si edge-tts falla, cuantos segundos evitamos reintentarlo
EDGE_TTS_COOLDOWN_S = 60


class VoiceEngine:
    """TTS hibrido: edge-tts (online) + Piper (offline neural) + pyttsx3 (offline fallback)."""

    def __init__(self):
        self._edge_available = True
        self._piper_voice = None     # Instancia de piper.PiperVoice
        self._pyttsx_engine = None
        self._voice_lang = Config.VOICE_LANGUAGE
        self._enabled = True
        self._loop = None
        self._edge_disabled_until = 0.0  # cooldown edge-tts tras fallo

    def initialize(self):
        # 1. Edge TTS (online, mejor calidad)
        try:
            import edge_tts  # noqa: F401
        except ImportError:
            self._edge_available = False

        # 2. Piper (offline neural) — inicializar eagerly para fallback instantaneo
        self._init_piper()

        # 3. pyttsx3 (fallback de ultimo recurso)
        self._init_pyttsx()

        # Resumen en consola de la cascada que tenemos
        layers = []
        if self._edge_available: layers.append("Edge TTS (online)")
        if self._piper_voice:    layers.append("Piper (offline neural)")
        if self._pyttsx_engine:  layers.append("pyttsx3 (offline SAPI)")
        console.print(f"  [cyan]Motor de voz:[/cyan] {' -> '.join(layers) if layers else 'ninguno'}")
        if self._edge_available:
            console.print(f"  [cyan]Voz online:[/cyan] {EDGE_TTS_VOICES.get(self._voice_lang, 'es-VE-SebastianNeural')}")
        if self._piper_voice:
            console.print(f"  [cyan]Voz offline:[/cyan] {PIPER_VOICES.get(self._voice_lang, '')}")

    def _init_piper(self):
        """Carga el modelo Piper si esta disponible. ~60MB en memoria una sola vez."""
        if self._piper_voice is not None:
            return
        try:
            from piper import PiperVoice
        except ImportError:
            return

        voice_name = PIPER_VOICES.get(self._voice_lang)
        if not voice_name:
            return
        model_path = os.path.join(PIPER_VOICES_DIR, f"{voice_name}.onnx")
        config_path = os.path.join(PIPER_VOICES_DIR, f"{voice_name}.onnx.json")

        if not (os.path.exists(model_path) and os.path.exists(config_path)):
            # No se descargo el modelo — silencio, fallback a pyttsx3
            return

        try:
            self._piper_voice = PiperVoice.load(model_path, config_path=config_path)
        except Exception as e:
            console.print(f"  [yellow]Piper no pudo cargarse ({e}), usando pyttsx3[/yellow]")
            self._piper_voice = None

    def _init_pyttsx(self):
        if self._pyttsx_engine is not None:
            return
        try:
            import pyttsx3
            self._pyttsx_engine = pyttsx3.init()
            self._pyttsx_engine.setProperty("rate", Config.VOICE_SPEED)
            voices = self._pyttsx_engine.getProperty("voices")
            for voice in voices:
                if self._voice_lang in voice.languages or self._voice_lang in voice.id.lower():
                    self._pyttsx_engine.setProperty("voice", voice.id)
                    break
        except Exception as e:
            console.print(f"  [yellow]Advertencia: No se pudo inicializar pyttsx3 offline: {e}[/yellow]")
            self._pyttsx_engine = None

    def _get_event_loop(self):
        if self._loop is None or self._loop.is_closed():
            self._loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self._loop)
        return self._loop

    def toggle(self):
        self._enabled = not self._enabled
        console.print(f"[cyan]Voz {'activada' if self._enabled else 'desactivada'}[/cyan]")

    @property
    def is_enabled(self) -> bool:
        return self._enabled

    def speak(self, text: str):
        if not self._enabled or not text:
            return

        # Cascada: edge-tts > piper > pyttsx3
        use_edge = (
            self._edge_available
            and time.time() > self._edge_disabled_until
        )
        if use_edge and self._speak_edge_tts(text):
            return  # exito online (mejor calidad)

        # Offline: Piper si esta disponible (voz neural natural)
        if self._piper_voice and self._speak_piper(text):
            return

        # Ultimo recurso: pyttsx3 SAPI
        if self._pyttsx_engine is None:
            self._init_pyttsx()
        if self._pyttsx_engine:
            self._speak_pyttsx(text)

    def synthesize_to_file(self, text: str, output_path: str) -> bool:
        """Genera audio TTS y lo guarda sin reproducir. Usado por Telegram."""
        if not self._edge_available:
            return False
        try:
            voice = EDGE_TTS_VOICES.get(self._voice_lang, "es-VE-SebastianNeural")
            loop = self._get_event_loop()
            loop.run_until_complete(self._generate_edge_audio(text, voice, output_path))
            return os.path.exists(output_path) and os.path.getsize(output_path) > 0
        except Exception as e:
            console.print(f"  [yellow]Error generando audio TTS: {e}[/yellow]")
            return False

    def generate_audio(self, text: str):
        """Genera audio TTS y devuelve (bytes, format).
        Cascada: edge-tts (mp3) -> piper (wav) -> None.
        Usado por el bridge para enviar audio al frontend y que este lo
        reproduzca + analice amplitud para el orbe audio-reactivo.
        """
        import wave as _wave
        # 1. Edge TTS -> mp3
        if self._edge_available and time.time() > self._edge_disabled_until:
            tmp_path = None
            try:
                voice = EDGE_TTS_VOICES.get(self._voice_lang, "es-VE-SebastianNeural")
                with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tmp:
                    tmp_path = tmp.name
                loop = self._get_event_loop()
                loop.run_until_complete(self._generate_edge_audio(text, voice, tmp_path))
                with open(tmp_path, "rb") as f:
                    data = f.read()
                if data:
                    return data, "mp3"
            except Exception as e:
                self._edge_disabled_until = time.time() + EDGE_TTS_COOLDOWN_S
                console.print(f"  [yellow]Edge TTS sin red, usando Piper offline.[/yellow]")
            finally:
                if tmp_path and os.path.exists(tmp_path):
                    try: os.unlink(tmp_path)
                    except Exception: pass

        # 2. Piper -> wav
        if self._piper_voice:
            tmp_path = None
            try:
                with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
                    tmp_path = tmp.name
                with _wave.open(tmp_path, "wb") as wf:
                    self._piper_voice.synthesize_wav(text, wf)
                with open(tmp_path, "rb") as f:
                    data = f.read()
                if data:
                    return data, "wav"
            except Exception as e:
                console.print(f"  [yellow]Piper fallo: {e}[/yellow]")
            finally:
                if tmp_path and os.path.exists(tmp_path):
                    try: os.unlink(tmp_path)
                    except Exception: pass

        # 3. Nada
        return None

    def _speak_edge_tts(self, text: str) -> bool:
        """Intenta hablar con edge-tts. Retorna True si exito, False si fallo.
        Si falla, marca un cooldown offline para no reintentar en proximas
        respuestas (ahorra el timeout HTTP repetido).
        """
        tmp_path = None
        try:
            voice = EDGE_TTS_VOICES.get(self._voice_lang, "es-VE-SebastianNeural")
            with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tmp:
                tmp_path = tmp.name

            loop = self._get_event_loop()
            loop.run_until_complete(self._generate_edge_audio(text, voice, tmp_path))
            self._play_audio(tmp_path)
            return True

        except Exception as e:
            # Casi siempre: sin internet o Microsoft bloqueo momentaneamente
            console.print(f"  [yellow]Edge TTS no disponible ({e}). Usando voz local (sin internet).[/yellow]")
            self._edge_disabled_until = time.time() + EDGE_TTS_COOLDOWN_S
            return False
        finally:
            if tmp_path and os.path.exists(tmp_path):
                try: os.unlink(tmp_path)
                except Exception: pass

    async def _generate_edge_audio(self, text: str, voice: str, output_path: str):
        import edge_tts
        communicate = edge_tts.Communicate(text, voice)
        await communicate.save(output_path)

    def _speak_piper(self, text: str) -> bool:
        """TTS neural offline con Piper. Sintetiza a WAV y reproduce con playsound3.
        Retorna True si fue exitoso, False si hay que caer al siguiente nivel.
        """
        if self._piper_voice is None:
            return False
        tmp_path = None
        try:
            import wave
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
                tmp_path = tmp.name
            with wave.open(tmp_path, "wb") as wf:
                self._piper_voice.synthesize_wav(text, wf)
            self._play_audio(tmp_path)
            return True
        except Exception as e:
            console.print(f"  [yellow]Piper fallo ({e}), usando fallback[/yellow]")
            return False
        finally:
            if tmp_path and os.path.exists(tmp_path):
                try: os.unlink(tmp_path)
                except Exception: pass

    def _play_audio(self, file_path: str):
        """Reproduce audio con playsound3 (Python puro, baja latencia).
        Fallback: ffplay / comandos del SO.
        """
        # Intento primario: playsound3 — ~50ms de latencia de arranque
        try:
            from playsound3 import playsound
            playsound(file_path, block=True)
            return
        except Exception:
            pass

        # Fallback: ffplay si existe
        import subprocess
        if sys.platform == "win32":
            try:
                subprocess.run(
                    ["ffplay", "-nodisp", "-autoexit", "-loglevel", "quiet", file_path],
                    check=True,
                    creationflags=subprocess.CREATE_NO_WINDOW,
                )
                return
            except (FileNotFoundError, subprocess.CalledProcessError):
                pass
        else:
            for player in ["ffplay", "mpv", "aplay", "afplay"]:
                try:
                    cmd = [player]
                    if player == "ffplay":
                        cmd += ["-nodisp", "-autoexit", "-loglevel", "quiet"]
                    elif player == "mpv":
                        cmd += ["--no-video", "--really-quiet"]
                    cmd.append(file_path)
                    subprocess.run(cmd, check=True)
                    return
                except (FileNotFoundError, subprocess.CalledProcessError):
                    continue
        console.print("  [yellow]No se encontro reproductor de audio compatible.[/yellow]")

    def _speak_pyttsx(self, text: str):
        try:
            self._pyttsx_engine.say(text)
            self._pyttsx_engine.runAndWait()
        except Exception as e:
            console.print(f"  [yellow]Error de voz offline (pyttsx3): {e}[/yellow]")
