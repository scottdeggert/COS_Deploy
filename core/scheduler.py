"""SimpleScheduler with JSON-backed last_run persistence.

Reads job configuration from clients/{client_id}/scheduler_config.json.
Persists last_run timestamps to logs/scheduler_state.json so jobs
do not re-fire after a process restart within the same window.

Scheduled jobs call tools/ directly. They do not go through RoutedIntent.
"""

from __future__ import annotations

import json
import random
import threading
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Callable

from app.config import CLIENT_ID, CLIENTS_DIR, LOGS_DIR, TELEGRAM_CHAT_ID, TELEGRAM_MONITOR_CHAT_ID
from handlers.brief import run_brief_for_contact
from tools.appointments import (
    format_appointment_summary,
    get_contact_id_from_appointment,
    get_upcoming_appointments,
)
from tools.hot_leads import get_hot_leads_going_cold
from tools.logger import log_event
from tools.telegram import send_long_message, send_message, send_operator_alert

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


def morning_digest() -> None:
    now_pacific = datetime.now(tz=timezone.utc) + timedelta(hours=-7)
    day_name = now_pacific.strftime("%A")
    greetings = [
        "Good morning, Ben.",
        "Morning, Ben. Here's your day.",
        "Buenos dias, Ben.",
        f"Happy {day_name}, Ben.",
        "Good morning, Ben. Another day in Lamorinda.",
    ]
    lines = [random.choice(greetings), ""]

    appointments = get_upcoming_appointments(hours_ahead=18)
    if appointments:
        lines.append("Today's appointments:")
        for appt in appointments:
            summary = format_appointment_summary(appt)
            contact_id = get_contact_id_from_appointment(appt)
            if contact_id:
                summary += f"\n  Send: brief {contact_id} for a full brief"
            lines.append(f"* {summary}")
    else:
        lines.append("No appointments in FUB today.")

    lines.append("")

    cold = get_hot_leads_going_cold(days_silent=14)
    if cold:
        lines.append(
            f"One thing worth knowing: you have {len(cold)} lead"
            f"{'s' if len(cold) != 1 else ''} tagged Hot 90 Days with no "
            f"activity in the last 14 days. They're warm and going cold. "
            f"Reply \"hot leads\" to see the list."
        )
    else:
        lines.append("Your Hot 90 Days leads are all active. Nothing going cold.")

    digest_text = "\n".join(lines)
    send_long_message(digest_text, chat_id=str(TELEGRAM_CHAT_ID))

    if TELEGRAM_MONITOR_CHAT_ID:
        send_long_message(digest_text, chat_id=str(TELEGRAM_MONITOR_CHAT_ID))


def pre_appointment_check(state: dict) -> None:
    appointments = get_upcoming_appointments(hours_ahead=2)
    now = datetime.now(tz=timezone.utc)
    briefed_ids: list = state.setdefault("briefed_appointment_ids", [])

    for appt in appointments:
        start_str = appt.get("start", "")
        try:
            start = datetime.fromisoformat(start_str.replace("Z", "+00:00"))
        except ValueError:
            continue

        minutes_until = (start - now).total_seconds() / 60
        if minutes_until > 120 or minutes_until < 90:
            continue

        appt_id = appt.get("id")
        if appt_id in briefed_ids:
            continue
        briefed_ids.append(appt_id)

        contact_id = get_contact_id_from_appointment(appt)
        if not contact_id:
            title = appt.get("title", "your next appointment")
            send_message(
                f"Heads up -- {title} starts in about 2 hours. "
                "No contact linked in FUB so I can't pull a brief automatically. "
                "Send me a name or ID if you want one.",
                chat_id=str(TELEGRAM_CHAT_ID),
            )
            continue

        try:
            brief_text = run_brief_for_contact(CLIENT_ID, contact_id)
            title = appt.get("title", "upcoming appointment")
            send_long_message(
                f"2-hour brief for {title}:\n\n{brief_text}",
                chat_id=str(TELEGRAM_CHAT_ID),
            )
        except Exception as exc:
            log_event(
                "scheduler", "pre_appointment_brief", "failure",
                detail=str(exc), contact_id=contact_id, exc_info=exc,
                file=__file__, function="pre_appointment_check",
            )
            send_operator_alert(
                f"Pre-appointment brief failed for contact {contact_id}: {exc}"
            )


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
