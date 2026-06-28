"""SimpleScheduler with JSON-backed last_run persistence.

Reads job configuration from clients/{client_id}/scheduler_config.json.
Persists last_run timestamps to logs/scheduler_state.json so jobs
do not re-fire after a process restart within the same window.

Scheduled jobs call tools/ directly. They do not go through RoutedIntent.
"""

from __future__ import annotations

import json
import threading
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Callable

from app.config import CLIENT_ID, CLIENTS_DIR, LOGS_DIR
from tools.logger import log_event

_STATE_PATH = LOGS_DIR / "scheduler_state.json"
_CONFIG_PATH = CLIENTS_DIR / CLIENT_ID / "scheduler_config.json"


def _load_config() -> dict:
    with _CONFIG_PATH.open(encoding="utf-8") as f:
        return json.load(f)


def _load_state() -> dict:
    if not _STATE_PATH.exists():
        return {"briefed_appointment_ids": [], "last_morning_digest_hour": -1}
    try:
        with _STATE_PATH.open(encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {"briefed_appointment_ids": [], "last_morning_digest_hour": -1}


def _save_state(state: dict) -> None:
    _STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    with _STATE_PATH.open("w", encoding="utf-8") as f:
        json.dump(state, f)


class SimpleScheduler:
    """Daemon thread scheduler. Reads config from tenant directory."""

    def __init__(self) -> None:
        self._daily_jobs: list[dict] = []
        self._interval_jobs: list[dict] = []
        self._thread: threading.Thread | None = None

    def add_daily(self, *, hour: int, minute: int, job: Callable, name: str) -> None:
        self._daily_jobs.append({
            "hour": hour, "minute": minute, "job": job, "name": name
        })

    def add_interval(self, *, seconds: int, job: Callable, name: str) -> None:
        self._interval_jobs.append({
            "seconds": seconds, "job": job, "name": name,
            "next_run": time.monotonic() + seconds,
        })

    def start(self) -> None:
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def _loop(self) -> None:
        while True:
            try:
                self._tick()
            except Exception as exc:
                log_event(
                    "scheduler", "tick", "failure",
                    detail=str(exc), exc_info=exc,
                    file=__file__, function="_loop",
                )
            time.sleep(60)

    def _tick(self) -> None:
        config = _load_config()
        offset = config["morning_digest"]["timezone_offset_hours"]
        now_local = datetime.now(tz=timezone.utc) + timedelta(hours=offset)
        state = _load_state()

        for job_def in self._daily_jobs:
            if (
                now_local.hour == job_def["hour"]
                and now_local.minute < job_def["minute"] + 5
                and state.get("last_morning_digest_hour") != now_local.hour
            ):
                log_event(
                    "scheduler", job_def["name"], "start",
                    file=__file__, function="_tick",
                )
                try:
                    job_def["job"]()
                    state["last_morning_digest_hour"] = now_local.hour
                    _save_state(state)
                    log_event(
                        "scheduler", job_def["name"], "success",
                        file=__file__, function="_tick",
                    )
                except Exception as exc:
                    log_event(
                        "scheduler", job_def["name"], "failure",
                        detail=str(exc), exc_info=exc,
                        file=__file__, function="_tick",
                    )

        for job_def in self._interval_jobs:
            if time.monotonic() >= job_def["next_run"]:
                log_event(
                    "scheduler", job_def["name"], "start",
                    file=__file__, function="_tick",
                )
                try:
                    job_def["job"](state)
                    _save_state(state)
                    log_event(
                        "scheduler", job_def["name"], "success",
                        file=__file__, function="_tick",
                    )
                except Exception as exc:
                    log_event(
                        "scheduler", job_def["name"], "failure",
                        detail=str(exc), exc_info=exc,
                        file=__file__, function="_tick",
                    )
                finally:
                    job_def["next_run"] = time.monotonic() + job_def["seconds"]
