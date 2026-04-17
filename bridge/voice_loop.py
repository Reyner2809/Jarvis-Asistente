"""
VoiceLoop: captura el microfono via voice.stt.SpeechToText, detecta la wake
word "Jarvis", transcribe el comando, lo procesa con JarvisProcessor y emite
eventos al event_bus para que la UI los reciba por WebSocket.

Corre en un hilo background del bridge. Si no hay microfono disponible, el
bridge sigue funcionando normalmente (solo por teclado / API).

Flujo de eventos emitidos:
    {"type": "voice_status", "value": "off" | "listening" | "paused"}
    {"type": "wake_detected"}
    {"type": "transcribed", "text": str}     <- se agrega como "Usted" en el chat
    (+ los que ya emite el processor: thinking, tool_call, response, ...)
    {"type": "speaking", "value": True|False}  <- cuando TTS esta hablando
"""

from __future__ import annotations

import logging
import threading
import time
from typing import Callable, Optional

log = logging.getLogger("jarvis.bridge.voice")


class VoiceLoop:
    def __init__(self, processor, event_bus_publish: Callable[[dict], None]):
        self.processor = processor
        self.emit = event_bus_publish

        self._stt = None
        self._tts = None
        self._thread: Optional[threading.Thread] = None
        self._stop = threading.Event()
        self._paused = threading.Event()
        self._available = False
        # Anti-duplicado: guarda el ultimo texto procesado + timestamp
        self._last_text = ""
        self._last_text_at = 0.0

    def initialize(self) -> bool:
        """Intenta inicializar STT y TTS. Retorna True si al menos STT anduvo."""
        # STT
        try:
            from voice.stt import SpeechToText
            self._stt = SpeechToText()
            if not self._stt.initialize():
                log.warning("STT no disponible (sin microfono?)")
                self._stt = None
                return False
            self._available = True
        except Exception as e:
            log.warning(f"STT fallo: {e}")
            return False

        # TTS (opcional — si falla, seguimos sin voz de salida)
        try:
            from voice.tts import VoiceEngine
            self._tts = VoiceEngine()
            self._tts.initialize()
            log.info("TTS inicializado")
        except Exception as e:
            log.warning(f"TTS no disponible: {e}")
            self._tts = None

        return True

    def start(self):
        """Arranca el hilo de escucha."""
        if not self._available:
            return
        self._stop.clear()
        self._stt.start_listening()
        self._thread = threading.Thread(target=self._loop, daemon=True, name="jarvis-voice-loop")
        self._thread.start()
        self.emit({"type": "voice_status", "value": "listening"})
        log.info("Voice loop activo")

    def stop(self):
        if self._thread:
            self._stop.set()
            try: self._stt.stop_listening()
            except Exception: pass
            self._thread.join(timeout=2)
            self._thread = None
        self.emit({"type": "voice_status", "value": "off"})

    def pause(self):
        """Pausa el STT temporalmente (toggle mic, TTS hablando, etc.)."""
        if self._stt: self._stt.pause()
        self._paused.set()
        self.emit({"type": "voice_status", "value": "paused"})

    def resume(self):
        if self._stt: self._stt.resume()
        self._paused.clear()
        self.emit({"type": "voice_status", "value": "listening"})

    @property
    def available(self) -> bool:
        return self._available

    @property
    def is_paused(self) -> bool:
        return self._paused.is_set()

    # -----------------------------------------------------------------------
    # Loop principal
    # -----------------------------------------------------------------------

    def _loop(self):
        while not self._stop.is_set():
            text = self._stt.get_speech(timeout=0.1)
            if text is None:
                continue

            if text == "__WAKE__":
                self._stt.activate_listening()
                self.emit({"type": "wake_detected"})
                continue

            # Anti-duplicado: si texto similar llega dentro de 3s, ignorar.
            # Normaliza a minusculas y sin espacios extra para atrapar variantes
            # como "Abre YouTube" vs "abre youtube" que Google STT puede devolver
            # en reconocimientos consecutivos del mismo audio residual.
            now = time.time()
            text_norm = text.strip().lower()
            if text_norm == self._last_text and (now - self._last_text_at) < 3.0:
                log.debug(f"Duplicado ignorado: '{text}'")
                continue
            self._last_text = text_norm
            self._last_text_at = now

            # PAUSAR el mic ANTES de procesar para evitar que durante el
            # procesamiento + inicio del TTS el mic siga capturando (eco,
            # audio residual). El mic se reanuda cuando speak() termina
            # o si no hay nada que hablar, lo reanudamos explicitamente.
            if self._stt:
                self._stt.pause()

            self.emit({"type": "transcribed", "text": text})
            try:
                result = self.processor.process(
                    text,
                    on_event=lambda ev: self.emit({**ev, "source": "voice"}),
                )
            except Exception as e:
                log.error(f"processor.process fallo: {e}")
                self.emit({"type": "error", "message": str(e)})
                # Reanudar mic ya que no hay speak que lo haga
                if self._stt:
                    self._stt.resume()
                continue

            if result.response and not result.error:
                # speak() pausa y reanuda el mic internamente
                threading.Thread(
                    target=self.speak,
                    args=(result.response,),
                    daemon=True,
                ).start()
            else:
                # Error o sin respuesta -> emitir error al frontend, no hablar
                if result.error:
                    self.emit({"type": "error", "message": result.error})
                if self._stt:
                    self._stt.resume()

    def speak(self, text: str):
        """Habla un texto. Genera el audio localmente con el TTS y lo envia al
        frontend via WebSocket (evento 'tts_audio') para que lo reproduzca
        alli y pueda analizar la amplitud en tiempo real para animar el orbe.

        El STT se pausa mientras el frontend reproduce (para no capturarse a
        si mismo). El frontend notifica el fin via POST /api/voice/tts_ended,
        que reanuda el STT.

        Respeta el mute: si el mic esta pausado (boton 🔊), no habla.
        """
        if not self._tts or not text:
            return
        if self.is_paused:
            return  # mute total

        # Pausar STT a bajo nivel (sin emitir voice_status para que el orbe
        # mantenga el estado 'speaking' limpio)
        if self._stt:
            self._stt.pause()

        self.emit({"type": "speaking", "value": True})

        # Generar audio bytes
        try:
            result = self._tts.generate_audio(text)
        except Exception as e:
            log.warning(f"generate_audio fallo: {e}")
            result = None

        if result is None:
            # No pudimos generar -> fallback a hablar localmente
            log.warning("Sin audio generado; reproducciendo localmente (sin reactividad)")
            try:
                self._tts.speak(text)
            except Exception:
                pass
            self.emit({"type": "speaking", "value": False})
            if self._stt:
                self._stt.resume()
            return

        audio_bytes, fmt = result
        import base64
        self.emit({
            "type": "tts_audio",
            "format": fmt,
            "data": base64.b64encode(audio_bytes).decode("ascii"),
        })
        # Estado speaking y mic pausado: se liberan cuando el frontend
        # llame a /api/voice/tts_ended. Como safety-net, ponemos un timeout:
        # si el frontend no responde en N segundos, liberamos igual.
        self._schedule_tts_safety_timeout(text)

    def _schedule_tts_safety_timeout(self, text: str):
        """Si el frontend no confirma fin de TTS tras un tiempo razonable,
        liberamos el mic igual. Estimamos por longitud del texto (~14 chars/s)."""
        approx_s = max(3.0, min(60.0, len(text) / 14 + 2.0))
        def _timeout():
            time.sleep(approx_s)
            # Solo libera si sigue en "hablando" (no hubo tts_ended)
            if self._stt and self._stt._paused:
                log.warning("TTS timeout — liberando STT sin confirmacion del frontend")
                self.tts_ended_notify()
        threading.Thread(target=_timeout, daemon=True).start()

    def tts_ended_notify(self):
        """Llamado cuando el frontend termina de reproducir el audio TTS.
        Libera el STT y emite speaking:false."""
        self.emit({"type": "speaking", "value": False})
        time.sleep(0.15)  # pequeno buffer para que no capture cola del audio
        if self._stt:
            self._stt.resume()
