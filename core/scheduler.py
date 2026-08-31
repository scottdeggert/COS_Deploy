"""SimpleScheduler with JSON-backed last_run persistence.

Reads job configuration from clients/{client_id}/scheduler_config.json.
Persists last_run timestamps to logs/scheduler_state.json so jobs
do not re-fire after a process restart within the same window.

Scheduled jobs call tools/ directly. They do not go through RoutedIntent.
"""

from __future__ import annotations

import json
import os
import random
import tempfile
import threading
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Callable
from zoneinfo import ZoneInfo

from app.config import CLIENT_ID, CLIENTS_DIR, LOGS_DIR, TELEGRAM_CHAT_ID, TELEGRAM_MONITOR_CHAT_ID
from handlers.brief import run_brief_for_contact
from tools.appointments import (
    format_appointment_summary,
    format_morning_digest_new_bookings,
    get_contact_id_from_appointment,
    get_upcoming_appointments,
)
from tools.activity_feed import format_morning_digest_recent_activity
from tools.google_calendar import (
    fetch_today_calendar_events,
    format_calendar_event_line,
    format_morning_digest_schedule_lines,
)
from tools.hot_leads import get_hot_leads_going_cold
from tools.logger import log_event
from tools.telegram import send_long_message, send_message, send_operator_alert

_STATE_PATH = LOGS_DIR / "scheduler_state.json"
_CONFIG_PATH = CLIENTS_DIR / CLIENT_ID / "scheduler_config.json"

# Fallback schedule when scheduler_config.json is unavailable (deadman + config miss).
DEFAULT_MORNING_DIGEST_HOUR = 8
DEFAULT_MORNING_DIGEST_MINUTE = 30
DEFAULT_PRE_APPOINTMENT_INTERVAL_SECONDS = 900
DEFAULT_TIMEZONE = "America/Los_Angeles"
_PACIFIC = ZoneInfo(DEFAULT_TIMEZONE)


def _pacific_now() -> datetime:
    """Current time in America/Los_Angeles."""
    return datetime.now(tz=_PACIFIC)


def _pacific_today() -> str:
    """Today's calendar date in America/Los_Angeles (YYYY-MM-DD)."""
    return _pacific_now().strftime("%Y-%m-%d")


def _morning_digest_schedule(config: dict, now_pacific: datetime) -> tuple[datetime, datetime]:
    """Return (scheduled_time, catch_up_cutoff) for today in Pacific."""
    digest_cfg = config["morning_digest"]
    hour = int(digest_cfg["hour"])
    minute = int(digest_cfg["minute"])
    catch_up_hours = int(digest_cfg.get("catch_up_hours", 2))
    day_start = now_pacific.replace(hour=0, minute=0, second=0, microsecond=0)
    scheduled = day_start.replace(hour=hour, minute=minute)
    cutoff = scheduled + timedelta(hours=catch_up_hours)
    return scheduled, cutoff


DEFAULT_STATE = {
    "briefed_appointment_ids": [],
    "last_morning_digest_date": "",
    "last_morning_digest_hour": -1,
    "last_morning_digest_greeting": "",
}


def _fresh_state() -> dict:
    """Return a deep copy of DEFAULT_STATE."""
    return json.loads(json.dumps(DEFAULT_STATE))


def _load_config() -> dict:
    with _CONFIG_PATH.open(encoding="utf-8") as f:
        return json.load(f)


def _load_state() -> dict:
    """Load scheduler_state.json. Never raises; rebuilds defaults on corrupt/missing."""
    try:
        with _STATE_PATH.open(encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        log_event(
            "scheduler",
            "load_state",
            "fallback",
            detail="corrupt or missing state, rebuilt defaults",
            file=__file__,
            function="_load_state",
        )
        state = _fresh_state()
        try:
            _save_state(state)
        except Exception:
            pass
        return state
    except Exception:
        log_event(
            "scheduler",
            "load_state",
            "fallback",
            detail="corrupt or missing state, rebuilt defaults",
            file=__file__,
            function="_load_state",
        )
        return _fresh_state()


def _save_state(state: dict) -> None:
    """Atomically persist state via temp file + fsync + os.replace."""
    _STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(
        dir=str(_STATE_PATH.parent),
        prefix="scheduler_state.",
        suffix=".tmp",
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(state, f)
            f.flush()
            os.fsync(f.fileno())
        os.replace(temp_name, _STATE_PATH)
    except Exception:
        try:
            os.unlink(temp_name)
        except OSError:
            pass
        raise


def _pick_morning_greeting(day_name: str) -> str:
    """Pick a greeting, excluding the previous digest's greeting."""
    state = _load_state()
    last_greeting = str(state.get("last_morning_digest_greeting") or "")
    greetings = [
        "Good morning, Ben.",
        "Morning, Ben. Here's your day.",
        f"Happy {day_name}, Ben.",
        "Good morning, Ben. Another day in Lamorinda.",
    ]
    pool = [greeting for greeting in greetings if greeting != last_greeting]
    if not pool:
        pool = greetings
    return random.choice(pool)


def _appointment_start_pacific(appt: dict) -> datetime | None:
    """Parse FUB appointment start using the same offset as format_appointment_summary."""
    start_str = appt.get("start")
    if not start_str:
        return None
    try:
        start = datetime.fromisoformat(str(start_str).replace("Z", "+00:00"))
        # Match tools/appointments.format_appointment_summary digest display logic.
        pacific_offset = timedelta(hours=-7)  # PDT; adjust to -8 for PST
        local = start + pacific_offset
        return local.replace(tzinfo=_PACIFIC)
    except ValueError:
        return None


def _fub_appointment_duplicates_google_event(
    appt_start: datetime,
    calendar_events: list,
    *,
    window_minutes: int = 15,
) -> bool:
    """True when a timed Google event starts within window_minutes of appt_start."""
    window = timedelta(minutes=window_minutes)
    for event in calendar_events:
        if event.all_day:
            continue
        if abs(event.start - appt_start) <= window:
            return True
    return False


def morning_digest(target_chat_id: str | None = None) -> str:
    now_pacific = datetime.now(tz=_PACIFIC)
    day_name = now_pacific.strftime("%A")
    greeting = _pick_morning_greeting(day_name)
    lines = [greeting, ""]

    appointments = get_upcoming_appointments(hours_ahead=18)
    calendar_events = fetch_today_calendar_events(CLIENT_ID)

    supplemental_fub_lines: list[str] = []
    for appt in appointments:
        appt_start = _appointment_start_pacific(appt)
        if appt_start and _fub_appointment_duplicates_google_event(
            appt_start, calendar_events
        ):
            appt_id = appt.get("id")
            log_event(
                "scheduler",
                "morning_digest_schedule",
                "success",
                detail=(
                    f"suppressed FUB appointment {appt_id} duplicate of "
                    f"Google Calendar event within 15m at {appt_start.isoformat()}"
                ),
                file=__file__,
                function="morning_digest",
            )
            continue

        summary = format_appointment_summary(appt)
        contact_id = get_contact_id_from_appointment(appt)
        if contact_id:
            summary += f"\n  Send: brief {contact_id} for a full brief"
        supplemental_fub_lines.append(f"* {summary}")

    if calendar_events or supplemental_fub_lines:
        lines.append("Today's schedule:")
        for event in calendar_events:
            lines.append(f"* {format_calendar_event_line(event)}")
        lines.extend(supplemental_fub_lines)
    else:
        lines.extend(format_morning_digest_schedule_lines([]))

    new_booking_lines = format_morning_digest_new_bookings()
    if new_booking_lines:
        lines.append("")
        lines.extend(new_booking_lines)

    lines.append("")

    lines.extend(format_morning_digest_recent_activity())
    lines.append("")

    cold = get_hot_leads_going_cold(days_silent=14)
    if cold:
        named = cold[:3]
        overflow = len(cold) - len(named)
        for lead in named:
            name = str(lead.get("name") or "").strip() or "A contact"
            lines.append(
                f"{name} is tagged Hot 90 Days, no activity in 14 days. "
                "Warm and going cold."
            )
        if overflow > 0:
            lines.append(
                f"Plus {overflow} more. "
                'Reply "hot leads" to see the full list.'
            )
    else:
        lines.append("Your Hot 90 Days leads are all active. Nothing going cold.")

    digest_text = "\n".join(lines)
    if target_chat_id:
        send_long_message(digest_text, chat_id=str(target_chat_id))
    else:
        send_long_message(digest_text, chat_id=str(TELEGRAM_CHAT_ID))
        if TELEGRAM_MONITOR_CHAT_ID:
            send_long_message(digest_text, chat_id=str(TELEGRAM_MONITOR_CHAT_ID))

    return greeting


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
        self._skip_logged: dict[str, str] = {}

    def _log_daily_skip(
        self, job_name: str, reason: str, detail: str, today_pacific: str
    ) -> None:
        """Log a non-send daily job decision once per reason per Pacific day."""
        key = f"{job_name}:{reason}:{today_pacific}"
        if self._skip_logged.get(key) == today_pacific:
            return
        self._skip_logged[key] = today_pacific
        log_event(
            "scheduler",
            job_name,
            "success",
            detail=detail,
            file=__file__,
            function="_tick",
        )

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
        # timezone_offset_hours kept in config for backward compatibility only.
        _ = config["morning_digest"].get("timezone_offset_hours")

        now_pacific = _pacific_now()
        today_pacific = now_pacific.strftime("%Y-%m-%d")

        stale_skip_keys = [
            key for key, day in self._skip_logged.items()
            if not key.endswith(f":{today_pacific}")
        ]
        for key in stale_skip_keys:
            del self._skip_logged[key]

        for job_def in self._daily_jobs:
            if job_def["name"] != "morning_digest":
                continue

            scheduled, cutoff = _morning_digest_schedule(config, now_pacific)
            scheduled_label = scheduled.strftime("%H:%M")
            cutoff_label = cutoff.strftime("%H:%M")

            if _load_state().get("last_morning_digest_date") == today_pacific:
                self._log_daily_skip(
                    "morning_digest",
                    "already_sent",
                    f"already sent for {today_pacific}, skipping",
                    today_pacific,
                )
                continue

            if now_pacific < scheduled:
                if now_pacific >= scheduled - timedelta(hours=1):
                    self._log_daily_skip(
                        "morning_digest",
                        "window_not_reached",
                        (
                            f"window not reached for {today_pacific}, "
                            f"scheduled {scheduled_label} Pacific"
                        ),
                        today_pacific,
                    )
                continue

            if now_pacific > cutoff:
                self._log_daily_skip(
                    "morning_digest",
                    "past_cutoff",
                    (
                        f"past catch-up cutoff for {today_pacific}, "
                        f"scheduled {scheduled_label} Pacific, "
                        f"cutoff {cutoff_label} Pacific, skipping"
                    ),
                    today_pacific,
                )
                continue

            log_event(
                "scheduler", job_def["name"], "start",
                file=__file__, function="_tick",
            )
            try:
                result = job_def["job"]()
                state = _load_state()
                state["last_morning_digest_date"] = today_pacific
                state["last_morning_digest_hour"] = now_pacific.hour
                if isinstance(result, str) and result:
                    state["last_morning_digest_greeting"] = result
                _save_state(state)
                log_event(
                    "scheduler", job_def["name"], "success",
                    detail=f"sent for {today_pacific}",
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
                    state = _load_state()
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
