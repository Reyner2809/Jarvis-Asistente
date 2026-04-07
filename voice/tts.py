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

    def _speak_edge_tts(self, text: str):
        try:
            voice = EDGE_TTS_VOICES.get(self._voice_lang, "es-VE-SebastianNeural")

            with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tmp:
                tmp_path = tmp.name

            asyncio.run(self._generate_edge_audio(text, voice, tmp_path))
            self._play_audio(tmp_path)

        except Exception as e:
            console.print(f"  [yellow]Error de voz (edge-tts): {e}[/yellow]")
            if self._pyttsx_engine is None:
                self._init_pyttsx()
            if self._pyttsx_engine:
                self._speak_pyttsx(text)
        finally:
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
            # Usar PowerShell para reproducir audio en Windows
            ps_cmd = (
                f'$player = New-Object System.Media.SoundPlayer "{file_path}"; '
                f'$player.PlaySync(); $player.Dispose()'
            )
            # edge-tts genera MP3, PowerShell SoundPlayer solo soporta WAV
            # Usar ffplay si esta disponible, sino convertir con PowerShell
            try:
                subprocess.run(
                    ["ffplay", "-nodisp", "-autoexit", "-loglevel", "quiet", file_path],
                    check=True,
                    creationflags=subprocess.CREATE_NO_WINDOW,
                )
            except FileNotFoundError:
                # Fallback: usar el modulo playsound o Windows Media Player
                try:
                    # Usar Windows Media Player via COM
                    ps_script = f'''
Add-Type -AssemblyName presentationCore
$mediaPlayer = New-Object System.Windows.Media.MediaPlayer
$mediaPlayer.Open([System.Uri]::new("{file_path}"))
$mediaPlayer.Play()
Start-Sleep -Milliseconds 500
while ($mediaPlayer.NaturalDuration.HasTimeSpan -and $mediaPlayer.Position -lt $mediaPlayer.NaturalDuration.TimeSpan) {{
    Start-Sleep -Milliseconds 100
}}
Start-Sleep -Milliseconds 200
$mediaPlayer.Close()
'''
                    subprocess.run(
                        ["powershell", "-NoProfile", "-Command", ps_script],
                        check=True,
                        creationflags=subprocess.CREATE_NO_WINDOW,
                    )
                except Exception:
                    console.print("  [yellow]No se pudo reproducir audio. Instala ffmpeg para mejor experiencia.[/yellow]")
        else:
            # Linux/Mac
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
