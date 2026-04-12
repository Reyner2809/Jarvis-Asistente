"""
Integracion de Telegram con Jarvis.

Permite hablarle a Jarvis (texto o voz) desde Telegram, sin depender del
microfono del PC. Cada usuario despliega su propio bot con su propio token,
asi que esta integracion es totalmente multiusuario sin configuracion compartida.

Arquitectura:
    - Un thread polleando Telegram (telebot.infinity_polling).
    - Cada mensaje autorizado se inyecta en el input_queue de main.py como
      una 3-tupla: ("telegram", text, chat_id).
    - El loop principal de main.py procesa el mensaje exactamente igual que
      uno de teclado, y al responder usa send_reply(chat_id, response) si
      la fuente fue telegram.
"""
import logging
import os
import queue
import re
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path

from rich.console import Console

console = Console()
log = logging.getLogger("jarvis.telegram")


class TelegramIO:
    """
    Adaptador de Telegram para Jarvis.

    Vida util tipica:
        tg = TelegramIO(input_queue)
        if tg.initialize():
            tg.start()
        ...
        tg.send_reply(chat_id, "respuesta")
        ...
        tg.stop()
    """

    def __init__(self, input_queue: "queue.Queue", voice_engine=None):
        self.input_queue = input_queue
        self.voice_engine = voice_engine
        self.token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
        self.allowed_users = {
            int(uid.strip())
            for uid in os.getenv("TELEGRAM_ALLOWED_USERS", "").split(",")
            if uid.strip().isdigit()
        }
        self.enable_voice = os.getenv("TELEGRAM_ENABLE_VOICE", "true").strip().lower() in (
            "1", "true", "yes", "si", "sí",
        )
        self.voice_language = os.getenv("VOICE_LANGUAGE", "es")
        self._stt_lang_code = "es-ES" if self.voice_language == "es" else "en-US"

        self.bot = None
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()
        self._available = False

    # -------------------------------------------------------------------------
    # Lifecycle
    # -------------------------------------------------------------------------
    def initialize(self) -> bool:
        """
        Carga telebot, valida configuracion y registra los handlers.
        Devuelve True si Telegram queda listo, False si esta deshabilitado o
        si falta alguna dependencia (en cuyo caso Jarvis sigue funcionando
        sin Telegram).
        """
        if not self.token:
            log.debug("Telegram deshabilitado: TELEGRAM_BOT_TOKEN vacio")
            return False

        if not self.allowed_users:
            console.print(
                "  [yellow]Telegram: TELEGRAM_BOT_TOKEN definido pero "
                "TELEGRAM_ALLOWED_USERS vacio. Por seguridad NO se activa.[/yellow]"
            )
            console.print(
                "  [yellow]  Habla con @userinfobot en Telegram para obtener tu "
                "ID y agregarlo al .env[/yellow]"
            )
            return False

        try:
            import telebot  # type: ignore
        except ImportError:
            console.print(
                "  [yellow]Telegram: pyTelegramBotAPI no instalado. "
                "Ejecuta: pip install pyTelegramBotAPI[/yellow]"
            )
            return False

        try:
            self.bot = telebot.TeleBot(self.token, parse_mode=None)
            # Validar el token contra la API
            me = self.bot.get_me()
            log.info("Bot Telegram conectado: @%s (id=%s)", me.username, me.id)
        except Exception as e:
            console.print(f"  [yellow]Telegram: token invalido o sin red ({e})[/yellow]")
            self.bot = None
            return False

        self._register_handlers()
        self._available = True
        return True

    def start(self) -> None:
        """Lanza el thread de polling. No-op si no esta inicializado."""
        if not self._available:
            return
        self._stop.clear()
        self._thread = threading.Thread(
            target=self._poll_loop,
            name="jarvis-telegram-poll",
            daemon=True,
        )
        self._thread.start()

    def stop(self) -> None:
        """Detiene el polling de forma ordenada."""
        self._stop.set()
        if self.bot is not None:
            try:
                self.bot.stop_polling()
            except Exception:
                pass
        if self._thread is not None and self._thread.is_alive():
            self._thread.join(timeout=3)
        self._thread = None

    @property
    def is_available(self) -> bool:
        return self._available

    @property
    def bot_username(self) -> str | None:
        if self.bot is None:
            return None
        try:
            return self.bot.get_me().username
        except Exception:
            return None

    # -------------------------------------------------------------------------
    # API publica para que main.py responda al usuario
    # -------------------------------------------------------------------------
    def send_reply(self, chat_id: int, text: str) -> bool:
        """Envia un mensaje al chat indicado. Resistente a errores."""
        if self.bot is None or not text:
            return False
        try:
            # Telegram limita a 4096 chars por mensaje. Trocear si es necesario.
            for chunk in self._chunk_text(text, 3900):
                self.bot.send_message(chat_id, chunk)
            return True
        except Exception as e:
            log.error("Error enviando reply Telegram a %s: %s", chat_id, e)
            return False

    def send_voice_reply(self, chat_id: int, text: str) -> bool:
        """
        Genera TTS del texto y lo envia como voice message (OGG/Opus).
        Si la sintesis o conversion fallan, cae a send_reply de texto.
        """
        if self.bot is None or not text:
            return False

        if self.voice_engine is None:
            log.debug("send_voice_reply sin voice_engine -> fallback texto")
            return self.send_reply(chat_id, text)

        mp3_path = None
        ogg_path = None
        try:
            with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tmp:
                mp3_path = tmp.name

            if not self.voice_engine.synthesize_to_file(text, mp3_path):
                log.warning("TTS fallo, enviando respuesta de texto")
                return self.send_reply(chat_id, text)

            ogg_path = mp3_path.rsplit(".", 1)[0] + ".ogg"
            try:
                kwargs = {"capture_output": True, "check": True}
                if sys.platform == "win32":
                    kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW
                subprocess.run(
                    ["ffmpeg", "-y", "-loglevel", "error",
                     "-i", mp3_path,
                     "-c:a", "libopus", "-b:a", "32k",
                     "-ar", "48000", "-ac", "1",
                     ogg_path],
                    **kwargs,
                )
            except (FileNotFoundError, subprocess.CalledProcessError) as e:
                log.warning("ffmpeg mp3->ogg fallo (%s), enviando texto", e)
                return self.send_reply(chat_id, text)

            try:
                with open(ogg_path, "rb") as f:
                    self.bot.send_voice(chat_id, f)
                return True
            except Exception as e:
                log.error("send_voice fallo: %s, enviando texto", e)
                return self.send_reply(chat_id, text)
        finally:
            for p in (mp3_path, ogg_path):
                if p:
                    try:
                        os.unlink(p)
                    except OSError:
                        pass

    @staticmethod
    def _chunk_text(text: str, size: int) -> list[str]:
        if len(text) <= size:
            return [text]
        chunks = []
        for i in range(0, len(text), size):
            chunks.append(text[i:i + size])
        return chunks

    # -------------------------------------------------------------------------
    # Polling loop
    # -------------------------------------------------------------------------
    def _poll_loop(self) -> None:
        log.info("Polling de Telegram iniciado")
        while not self._stop.is_set():
            try:
                self.bot.infinity_polling(
                    timeout=20,
                    long_polling_timeout=15,
                    skip_pending=True,
                )
                # infinity_polling solo retorna si stop_polling fue llamado
                break
            except Exception as e:
                if self._stop.is_set():
                    break
                log.warning("Error en polling Telegram, reintentando en 5s: %s", e)
                time.sleep(5)
        log.info("Polling de Telegram detenido")

    # -------------------------------------------------------------------------
    # Handlers
    # -------------------------------------------------------------------------
    def _register_handlers(self) -> None:
        bot = self.bot
        assert bot is not None

        @bot.message_handler(commands=["start", "help", "ayuda"])
        def cmd_start(message):
            user = message.from_user
            if not self._is_authorized(message):
                bot.reply_to(
                    message,
                    "Acceso denegado.\n\n"
                    f"Tu user ID es `{user.id}`. Pide al admin que lo agregue "
                    "a TELEGRAM_ALLOWED_USERS en el .env de Jarvis.",
                )
                self._log_denied(message)
                return
            assistant_name = os.getenv("ASSISTANT_NAME", "Jarvis")
            bot.reply_to(
                message,
                f"{assistant_name} a su servicio, senor.\n\n"
                "Puede enviarme mensajes de texto o de voz y los procesare "
                "como si los dijera al microfono del PC.\n\n"
                "Comandos disponibles:\n"
                "/whoami - muestra tu user ID\n"
                "/help - muestra esta ayuda",
            )

        @bot.message_handler(commands=["whoami", "id"])
        def cmd_whoami(message):
            # No requiere auth: util para que el admin obtenga su ID la primera vez
            user = message.from_user
            bot.reply_to(
                message,
                f"User ID: {user.id}\n"
                f"Username: @{user.username or '(sin username)'}",
            )

        @bot.message_handler(content_types=["text"])
        def on_text(message):
            if not self._is_authorized(message):
                self._log_denied(message)
                bot.reply_to(message, "Acceso denegado.")
                return
            text = (message.text or "").strip()
            if not text:
                return
            log.info("Texto user=%s: %r", message.from_user.id, text)
            self._enqueue(text, message.chat.id, is_voice=False)

        @bot.message_handler(content_types=["voice", "audio"])
        def on_voice(message):
            if not self._is_authorized(message):
                self._log_denied(message)
                bot.reply_to(message, "Acceso denegado.")
                return
            log.info("Voz user=%s", message.from_user.id)

            if not self.enable_voice:
                bot.reply_to(
                    message,
                    "El soporte de voz esta deshabilitado en este Jarvis. "
                    "Envia el mensaje en texto.",
                )
                return

            try:
                text = self._transcribe_voice(message)
            except RuntimeError as e:
                log.warning("Transcripcion fallida: %s", e)
                bot.reply_to(message, f"No pude transcribir el audio: {e}")
                return
            except Exception as e:
                log.exception("Error transcribiendo voz")
                bot.reply_to(message, f"Error procesando el audio: {e}")
                return

            if not text:
                bot.reply_to(message, "No entendi nada del audio. Intenta de nuevo.")
                return

            log.info("Transcripcion: %r", text)
            try:
                bot.reply_to(message, f'Escuche: "{text}"')
            except Exception:
                pass
            self._enqueue(text, message.chat.id, is_voice=True)

    # -------------------------------------------------------------------------
    # Helpers internos
    # -------------------------------------------------------------------------
    def _is_authorized(self, message) -> bool:
        return (
            message.from_user is not None
            and message.from_user.id in self.allowed_users
        )

    def _log_denied(self, message) -> None:
        user = message.from_user
        log.warning(
            "ACCESO DENEGADO id=%s username=%s text=%r",
            user.id if user else "?",
            user.username if user else "?",
            getattr(message, "text", None),
        )

    def _enqueue(self, text: str, chat_id: int, is_voice: bool = False) -> None:
        """
        Inyecta el texto al input_queue del main loop como mensaje de Telegram.
        is_voice indica si el mensaje original fue un audio (para que Jarvis
        responda con voz en vez de texto).
        """
        try:
            self.input_queue.put(("telegram", text, chat_id, is_voice))
        except Exception as e:
            log.error("No pude encolar mensaje de Telegram: %s", e)

    # -------------------------------------------------------------------------
    # Transcripcion de voz (Google Web Speech via SpeechRecognition)
    # -------------------------------------------------------------------------
    def _transcribe_voice(self, message) -> str:
        try:
            import speech_recognition as sr  # type: ignore
        except ImportError:
            raise RuntimeError(
                "SpeechRecognition no esta instalado. Ejecuta: pip install SpeechRecognition"
            )

        bot = self.bot
        assert bot is not None

        file_id = (
            message.voice.file_id
            if message.content_type == "voice"
            else message.audio.file_id
        )
        file_info = bot.get_file(file_id)
        audio_bytes = bot.download_file(file_info.file_path)

        with tempfile.NamedTemporaryFile(suffix=".oga", delete=False) as f:
            f.write(audio_bytes)
            oga_path = f.name
        wav_path = oga_path.rsplit(".", 1)[0] + ".wav"

        try:
            try:
                kwargs = {"capture_output": True, "check": True}
                if sys.platform == "win32":
                    kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW
                subprocess.run(
                    ["ffmpeg", "-y", "-loglevel", "error",
                     "-i", oga_path, "-ar", "16000", "-ac", "1", wav_path],
                    **kwargs,
                )
            except FileNotFoundError:
                raise RuntimeError(
                    "ffmpeg no esta instalado. Instala ffmpeg para soporte de voz "
                    "(Windows: descarga de ffmpeg.org, Linux: apt install ffmpeg)."
                )
            except subprocess.CalledProcessError as e:
                err = (e.stderr or b"").decode(errors="ignore").strip()
                raise RuntimeError(f"ffmpeg fallo: {err or 'codigo ' + str(e.returncode)}")

            recognizer = sr.Recognizer()
            with sr.AudioFile(wav_path) as source:
                audio_data = recognizer.record(source)
            try:
                return recognizer.recognize_google(audio_data, language=self._stt_lang_code)
            except sr.UnknownValueError:
                return ""
            except sr.RequestError as e:
                raise RuntimeError(f"Google STT fallo: {e}")
        finally:
            for p in (oga_path, wav_path):
                try:
                    os.unlink(p)
                except OSError:
                    pass
