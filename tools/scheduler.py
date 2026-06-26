"""Background scheduler for timed CoS agent tasks."""

from __future__ import annotations

import threading
import time
from datetime import datetime, timedelta, timezone
from typing import Callable

from tools.logger import log_event


class SimpleScheduler:
    """Lightweight scheduler. Checks every 60 seconds for jobs to fire."""

    def __init__(self) -> None:
        self._jobs: list[dict] = []
        self._lock = threading.Lock()
        self._thread: threading.Thread | None = None

    def add_daily(self, hour: int, minute: int, job: Callable, name: str) -> None:
        """Fire `job` every day at `hour`:`minute` local Pacific time (UTC-7)."""
        with self._lock:
            self._jobs.append({
                "type": "daily",
                "hour": hour,
                "minute": minute,
                "job": job,
                "name": name,
                "last_fired": None,
            })

    def add_interval(self, seconds: int, job: Callable, name: str) -> None:
        """Fire `job` every `seconds` seconds."""
        with self._lock:
            self._jobs.append({
                "type": "interval",
                "seconds": seconds,
                "job": job,
                "name": name,
                "last_fired": None,
            })

    def _should_fire_daily(self, job: dict, now_pacific: datetime) -> bool:
        if now_pacific.hour != job["hour"] or now_pacific.minute != job["minute"]:
            return False
        last = job["last_fired"]
        if last is None:
            return True
        return (now_pacific - last).total_seconds() > 3600  # dedupe within same hour

    def _should_fire_interval(self, job: dict, now: datetime) -> bool:
        last = job["last_fired"]
        if last is None:
            return True
        return (now - last).total_seconds() >= job["seconds"]

    def _run(self) -> None:
        while True:
            now_utc = datetime.now(tz=timezone.utc)
            pacific_offset = timedelta(hours=-7)  # PDT
            now_pacific = now_utc + pacific_offset

            with self._lock:
                for job in self._jobs:
                    try:
                        should_fire = False
                        if job["type"] == "daily":
                            should_fire = self._should_fire_daily(job, now_pacific)
                        elif job["type"] == "interval":
                            should_fire = self._should_fire_interval(job, now_utc)

                        if should_fire:
                            log_event(
                                "scheduler",
                                job["name"],
                                "start",
                                file=__file__,
                                function="_run",
                            )
                            job["job"]()
                            job["last_fired"] = now_pacific if job["type"] == "daily" else now_utc
                            log_event(
                                "scheduler",
                                job["name"],
                                "success",
                                file=__file__,
                                function="_run",
                            )
                    except Exception as exc:
                        log_event(
                            "scheduler",
                            job["name"],
                            "failure",
                            detail=str(exc),
                            exc_info=exc,
                            file=__file__,
                            function="_run",
                        )

            time.sleep(60)

    def start(self) -> threading.Thread:
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        return self._thread
