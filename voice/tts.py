import asyncio
import tempfile
import os
import subprocess
import sys
from rich.console import Console
from config import Config

console = Console()

EDGE_TTS_VOICES = {
    "es": "es-VE-SebastianNeural",
    "en": "en-US-GuyNeural",
}


class VoiceEngine:
    """Motor de voz con edge-tts (alta calidad) y pyttsx3 (fallback offline)."""

    def __init__(self):
        self._use_edge_tts = True
        self._pyttsx_engine = None
        self._voice_lang = Config.VOICE_LANGUAGE
        self._enabled = True
        self._loop = None

    def initialize(self):
        try:
            import edge_tts  # noqa: F401
            console.print(f"  [cyan]Motor de voz:[/cyan] Edge TTS (alta calidad)")
            console.print(f"  [cyan]Voz:[/cyan] {EDGE_TTS_VOICES.get(self._voice_lang, 'es-VE-SebastianNeural')}")
        except ImportError:
            self._use_edge_tts = False
            console.print(f"  [cyan]Motor de voz:[/cyan] pyttsx3 (offline)")
            self._init_pyttsx()

    def _init_pyttsx(self):
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
            console.print(f"  [yellow]Advertencia: No se pudo inicializar pyttsx3: {e}[/yellow]")
            self._pyttsx_engine = None

    def _get_event_loop(self):
        """Obtiene o crea un event loop reutilizable."""
        if self._loop is None or self._loop.is_closed():
            self._loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self._loop)
        return self._loop

    def toggle(self):
        self._enabled = not self._enabled
        state = "activada" if self._enabled else "desactivada"
        console.print(f"[cyan]Voz {state}[/cyan]")

    @property
    def is_enabled(self) -> bool:
        return self._enabled

    def speak(self, text: str):
        if not self._enabled:
            return

        if self._use_edge_tts:
            self._speak_edge_tts(text)
        elif self._pyttsx_engine:
            self._speak_pyttsx(text)

    def synthesize_to_file(self, text: str, output_path: str) -> bool:
        """
        Genera audio TTS y lo guarda en output_path (mp3) sin reproducirlo.
        Devuelve True si la sintesis funciono, False si no hay motor edge-tts.
        Usado por integraciones externas como Telegram para enviar respuestas
        habladas en lugar de solo texto.
        """
        if not self._use_edge_tts:
            return False
        try:
            voice = EDGE_TTS_VOICES.get(self._voice_lang, "es-VE-SebastianNeural")
            loop = self._get_event_loop()
            loop.run_until_complete(self._generate_edge_audio(text, voice, output_path))
            return os.path.exists(output_path) and os.path.getsize(output_path) > 0
        except Exception as e:
            console.print(f"  [yellow]Error generando audio TTS: {e}[/yellow]")
            return False

    def _speak_edge_tts(self, text: str):
        tmp_path = None
        try:
            voice = EDGE_TTS_VOICES.get(self._voice_lang, "es-VE-SebastianNeural")

            with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tmp:
                tmp_path = tmp.name

            loop = self._get_event_loop()
            loop.run_until_complete(self._generate_edge_audio(text, voice, tmp_path))
            self._play_audio(tmp_path)

        except Exception as e:
            console.print(f"  [yellow]Error de voz (edge-tts): {e}[/yellow]")
            if self._pyttsx_engine is None:
                self._init_pyttsx()
            if self._pyttsx_engine:
                self._speak_pyttsx(text)
        finally:
            if tmp_path:
                try:
                    if os.path.exists(tmp_path):
                        os.unlink(tmp_path)
                except Exception:
                    pass

    async def _generate_edge_audio(self, text: str, voice: str, output_path: str):
        import edge_tts
        communicate = edge_tts.Communicate(text, voice)
        await communicate.save(output_path)

    def _play_audio(self, file_path: str):
        if sys.platform == "win32":
            try:
                subprocess.run(
                    ["ffplay", "-nodisp", "-autoexit", "-loglevel", "quiet", file_path],
                    check=True,
                    creationflags=subprocess.CREATE_NO_WINDOW,
                )
            except FileNotFoundError:
                try:
                    ps_script = f'''
Add-Type -AssemblyName presentationCore
$mediaPlayer = New-Object System.Windows.Media.MediaPlayer
$mediaPlayer.Open([System.Uri]::new("{file_path}"))
Start-Sleep -Milliseconds 300
$mediaPlayer.Play()
while ($mediaPlayer.NaturalDuration.HasTimeSpan -eq $false) {{
    Start-Sleep -Milliseconds 100
}}
while ($mediaPlayer.Position -lt $mediaPlayer.NaturalDuration.TimeSpan) {{
    Start-Sleep -Milliseconds 100
}}
Start-Sleep -Milliseconds 300
$mediaPlayer.Stop()
$mediaPlayer.Close()
'''
                    subprocess.run(
                        ["powershell", "-NoProfile", "-Command", ps_script],
                        check=True,
                        creationflags=subprocess.CREATE_NO_WINDOW,
                    )
                except Exception as e:
                    console.print(f"  [yellow]No se pudo reproducir audio: {e}[/yellow]")
                    console.print("  [yellow]Instala ffmpeg para mejor experiencia: winget install ffmpeg[/yellow]")
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
                except FileNotFoundError:
                    continue
            console.print("  [yellow]No se encontro un reproductor de audio.[/yellow]")

    def _speak_pyttsx(self, text: str):
        try:
            self._pyttsx_engine.say(text)
            self._pyttsx_engine.runAndWait()
        except Exception as e:
            console.print(f"  [yellow]Error de voz (pyttsx3): {e}[/yellow]")
