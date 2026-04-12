"""
Sistema de recordatorios y tareas programadas para Jarvis.

Permite al usuario programar avisos futuros que se ejecutan automaticamente:
- "recuerdame a las 5pm que tengo reunion"
- "en 30 minutos avisame que saque la comida"
- "manana a las 9am dime las noticias"

Persistencia en data/scheduled_tasks.json — sobrevive reinicios.
Inspirado en el sistema cron de OpenClaw.
"""

import json
import logging
import os
import threading
import time
import uuid
from datetime import datetime, timedelta

log = logging.getLogger("jarvis.scheduler")

_DATA_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "data",
)
_TASKS_FILE = os.path.join(_DATA_DIR, "scheduled_tasks.json")


class TaskScheduler:
    """Scheduler de tareas con persistencia JSON y loop en background."""

    def __init__(self, telegram_io=None, console_callback=None, check_interval: int = 10):
        self._telegram_io = telegram_io
        self._console_callback = console_callback
        self._check_interval = check_interval
        self._tasks: list[dict] = []
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()
        self._lock = threading.Lock()
        self._file = _TASKS_FILE

    def initialize(self) -> bool:
        os.makedirs(os.path.dirname(self._file), exist_ok=True)
        self._load()
        log.info("Scheduler: %d tarea(s) programadas", len(self._tasks))
        return True

    def start(self):
        """Inicia el loop de verificacion en background."""
        self._stop.clear()
        self._thread = threading.Thread(
            target=self._scheduler_loop,
            name="jarvis-scheduler",
            daemon=True,
        )
        self._thread.start()

    def stop(self):
        self._stop.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=3)

    # ------------------------------------------------------------------
    # CRUD de tareas
    # ------------------------------------------------------------------

    def add_task(
        self,
        message: str,
        run_at: datetime,
        channel: str = "console",
        chat_id: int | None = None,
        repeat: dict | None = None,
    ) -> dict:
        """
        Programa una tarea (unica o recurrente).
        Args:
            message: texto del recordatorio
            run_at: cuando ejecutar (datetime)
            channel: "telegram" o "console"
            chat_id: ID de chat de Telegram (si channel=telegram)
            repeat: None para unica, o dict con tipo de repeticion:
                    {"type": "daily", "time": "09:00"}
                    {"type": "weekly", "days": [0,1,2,3,4], "time": "09:00"}  (0=lunes)
                    {"type": "hourly"}
                    {"type": "every", "minutes": 120}
        Returns: dict con id, message, run_at, repeat
        """
        task = {
            "id": uuid.uuid4().hex[:8],
            "message": message,
            "run_at": run_at.isoformat(),
            "channel": channel,
            "chat_id": chat_id,
            "repeat": repeat,
            "created": datetime.now().isoformat(),
        }

        with self._lock:
            self._tasks.append(task)
            self._save()

        repeat_label = ""
        if repeat:
            repeat_label = f" (recurrente: {repeat['type']})"

        log.info("Tarea programada: '%s' para %s%s", message, run_at.strftime("%Y-%m-%d %H:%M"), repeat_label)
        return {
            "id": task["id"],
            "message": message,
            "run_at": run_at.strftime("%Y-%m-%d %H:%M"),
            "repeat": repeat,
        }

    def remove_task(self, task_id: str) -> bool:
        with self._lock:
            before = len(self._tasks)
            self._tasks = [t for t in self._tasks if t["id"] != task_id]
            if len(self._tasks) < before:
                self._save()
                return True
        return False

    def list_tasks(self) -> list[dict]:
        with self._lock:
            return list(self._tasks)

    @property
    def count(self) -> int:
        return len(self._tasks)

    # ------------------------------------------------------------------
    # Helpers para parsear tiempos naturales
    # ------------------------------------------------------------------

    @staticmethod
    def parse_recurring(text: str) -> tuple[datetime | None, dict | None]:
        """
        Parsea patrones recurrentes. Devuelve (primera_ejecucion, repeat_config)
        o (None, None) si no es recurrente.

        Patrones:
        - "todos los dias a las 9am"
        - "cada dia a las 9am"
        - "cada lunes a las 8am"
        - "de lunes a viernes a las 9am"
        - "cada 2 horas"
        - "cada 30 minutos"
        - "cada hora"
        """
        import re
        text = text.lower().strip()
        now = datetime.now()

        DAY_MAP = {
            "lunes": 0, "martes": 1, "miercoles": 2, "miércoles": 2,
            "jueves": 3, "viernes": 4, "sabado": 5, "sábado": 5, "domingo": 6,
        }

        # "todos los dias / cada dia + a las HH:MM/Xam/Xpm"
        if re.search(r"(?:todos\s+los\s+d[ií]as?|cada\s+d[ií]a)", text):
            time_match = re.search(r'(?:a\s+las?\s+)?(\d{1,2})(?::(\d{2}))?\s*(am|pm)?', text)
            if time_match:
                hour = int(time_match.group(1))
                minute = int(time_match.group(2) or 0)
                period = time_match.group(3)
                if period == "pm" and hour != 12:
                    hour += 12
                elif period == "am" and hour == 12:
                    hour = 0
                first = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
                if first <= now:
                    first += timedelta(days=1)
                return first, {"type": "daily", "time": f"{hour:02d}:{minute:02d}"}

        # "de lunes a viernes a las X"
        m = re.search(r"de\s+(\w+)\s+a\s+(\w+)", text)
        if m:
            day_from = DAY_MAP.get(m.group(1))
            day_to = DAY_MAP.get(m.group(2))
            if day_from is not None and day_to is not None:
                days = list(range(day_from, day_to + 1))
                time_match = re.search(r'(?:a\s+las?\s+)?(\d{1,2})(?::(\d{2}))?\s*(am|pm)?', text)
                hour, minute = 9, 0
                if time_match:
                    hour = int(time_match.group(1))
                    minute = int(time_match.group(2) or 0)
                    period = time_match.group(3)
                    if period == "pm" and hour != 12:
                        hour += 12
                first = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
                while first <= now or first.weekday() not in days:
                    first += timedelta(days=1)
                return first, {"type": "weekly", "days": days, "time": f"{hour:02d}:{minute:02d}"}

        # "cada lunes/martes/... a las X"
        for day_name, day_num in DAY_MAP.items():
            if re.search(rf"cada\s+{day_name}", text):
                time_match = re.search(r'(?:a\s+las?\s+)?(\d{1,2})(?::(\d{2}))?\s*(am|pm)?', text)
                hour, minute = 9, 0
                if time_match:
                    hour = int(time_match.group(1))
                    minute = int(time_match.group(2) or 0)
                    period = time_match.group(3)
                    if period == "pm" and hour != 12:
                        hour += 12
                first = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
                while first <= now or first.weekday() != day_num:
                    first += timedelta(days=1)
                return first, {"type": "weekly", "days": [day_num], "time": f"{hour:02d}:{minute:02d}"}

        # "cada X horas" / "cada hora"
        m = re.search(r"cada\s+(\d+)\s*horas?", text)
        if m:
            hours = int(m.group(1))
            first = now + timedelta(hours=hours)
            return first, {"type": "every", "minutes": hours * 60}

        if re.search(r"cada\s+hora\b", text):
            return now + timedelta(hours=1), {"type": "hourly"}

        # "cada X minutos"
        m = re.search(r"cada\s+(\d+)\s*minutos?", text)
        if m:
            mins = int(m.group(1))
            return now + timedelta(minutes=mins), {"type": "every", "minutes": mins}

        return None, None

    @staticmethod
    def parse_relative_time(text: str) -> datetime | None:
        """Parsea 'en 30 minutos', 'en 2 horas', 'en 1 hora y media'."""
        import re
        text = text.lower().strip()

        # "en X minutos/horas/segundos"
        m = re.search(r'(\d+)\s*(?:minutos?|min)', text)
        if m:
            return datetime.now() + timedelta(minutes=int(m.group(1)))

        m = re.search(r'(\d+)\s*(?:horas?|hr|h)\b', text)
        if m:
            extra_min = 0
            if "media" in text or "30" in text:
                extra_min = 30
            return datetime.now() + timedelta(hours=int(m.group(1)), minutes=extra_min)

        m = re.search(r'(\d+)\s*(?:segundos?|seg|s)\b', text)
        if m:
            return datetime.now() + timedelta(seconds=int(m.group(1)))

        # "media hora"
        if "media hora" in text:
            return datetime.now() + timedelta(minutes=30)

        return None

    @staticmethod
    def parse_absolute_time(text: str) -> datetime | None:
        """Parsea 'a las 5pm', 'a las 14:30', 'manana a las 9am'."""
        import re
        text = text.lower().strip()
        now = datetime.now()

        # "a las HH:MM" (24h)
        m = re.search(r'(?:a\s+las?\s+)?(\d{1,2}):(\d{2})', text)
        if m:
            hour, minute = int(m.group(1)), int(m.group(2))
            target = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
            if target <= now:
                target += timedelta(days=1)
            if "mañana" in text or "manana" in text:
                if target.date() == now.date():
                    target += timedelta(days=1)
            return target

        # "a las Xpm/am"
        m = re.search(r'(?:a\s+las?\s+)?(\d{1,2})\s*(am|pm|a\.m\.|p\.m\.)', text)
        if m:
            hour = int(m.group(1))
            period = m.group(2).replace(".", "")
            if period == "pm" and hour != 12:
                hour += 12
            elif period == "am" and hour == 12:
                hour = 0
            target = now.replace(hour=hour, minute=0, second=0, microsecond=0)
            if target <= now:
                target += timedelta(days=1)
            if "mañana" in text or "manana" in text:
                if target.date() == now.date():
                    target += timedelta(days=1)
            return target

        # "a las X" (sin am/pm, asume siguiente ocurrencia)
        m = re.search(r'a\s+las?\s+(\d{1,2})(?:\b|$)', text)
        if m:
            hour = int(m.group(1))
            if hour <= 12 and "noche" in text:
                hour += 12
            target = now.replace(hour=hour, minute=0, second=0, microsecond=0)
            if target <= now:
                target += timedelta(days=1)
            return target

        return None

    # ------------------------------------------------------------------
    # Loop de ejecucion
    # ------------------------------------------------------------------

    def _scheduler_loop(self):
        log.info("Scheduler loop iniciado (intervalo: %ds)", self._check_interval)
        while not self._stop.is_set():
            self._check_and_execute()
            self._stop.wait(self._check_interval)
        log.info("Scheduler loop detenido")

    def _check_and_execute(self):
        now = datetime.now()
        to_execute = []

        with self._lock:
            remaining = []
            for task in self._tasks:
                try:
                    run_at = datetime.fromisoformat(task["run_at"])
                except (ValueError, KeyError):
                    continue

                if run_at <= now:
                    to_execute.append(task)
                    # Si es recurrente, reprogramar en vez de borrar
                    repeat = task.get("repeat")
                    if repeat:
                        next_run = self._calculate_next_run(run_at, repeat)
                        if next_run:
                            task["run_at"] = next_run.isoformat()
                            remaining.append(task)
                    # Si no es recurrente, se borra (no se agrega a remaining)
                else:
                    remaining.append(task)

            if to_execute:
                self._tasks = remaining
                self._save()

        for task in to_execute:
            self._deliver(task)

    @staticmethod
    def _calculate_next_run(last_run: datetime, repeat: dict) -> datetime | None:
        """Calcula la siguiente ejecucion de una tarea recurrente."""
        repeat_type = repeat.get("type", "")

        if repeat_type == "daily":
            return last_run + timedelta(days=1)

        elif repeat_type == "weekly":
            days = repeat.get("days", [0, 1, 2, 3, 4])  # default: lunes a viernes
            next_run = last_run + timedelta(days=1)
            # Buscar el proximo dia permitido
            for _ in range(7):
                if next_run.weekday() in days:
                    return next_run
                next_run += timedelta(days=1)
            return last_run + timedelta(weeks=1)

        elif repeat_type == "hourly":
            return last_run + timedelta(hours=1)

        elif repeat_type == "every":
            minutes = repeat.get("minutes", 60)
            return last_run + timedelta(minutes=minutes)

        return None

    def _deliver(self, task: dict):
        """Entrega el recordatorio al usuario."""
        msg = f"Recordatorio: {task['message']}"
        channel = task.get("channel", "console")
        chat_id = task.get("chat_id")

        log.info("Ejecutando recordatorio: %s", task["message"])

        if channel == "telegram" and self._telegram_io and chat_id:
            try:
                self._telegram_io.send_reply(chat_id, f"⏰ {msg}")
            except Exception as e:
                log.error("Error enviando recordatorio por Telegram: %s", e)

        if self._console_callback:
            try:
                self._console_callback(msg)
            except Exception:
                pass

    # ------------------------------------------------------------------
    # Persistencia
    # ------------------------------------------------------------------

    def _load(self):
        if os.path.exists(self._file):
            try:
                with open(self._file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                self._tasks = data if isinstance(data, list) else data.get("tasks", [])
            except (json.JSONDecodeError, KeyError):
                self._tasks = []
        else:
            self._tasks = []

        # Limpiar tareas ya vencidas que no se ejecutaron (por PC apagada)
        now = datetime.now()
        expired = [t for t in self._tasks if datetime.fromisoformat(t["run_at"]) <= now]
        if expired:
            log.info("Descartando %d recordatorios vencidos (PC estaba apagada)", len(expired))
            self._tasks = [t for t in self._tasks if datetime.fromisoformat(t["run_at"]) > now]
            self._save()

    def _save(self):
        with open(self._file, "w", encoding="utf-8") as f:
            json.dump(self._tasks, f, ensure_ascii=False, indent=2)
