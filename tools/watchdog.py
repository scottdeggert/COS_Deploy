"""Continuous log monitor — tails cos_agent.log and alerts operator on errors."""

from __future__ import annotations

import argparse
import fcntl
import json
import os
import re
import sys
import tempfile
import time
from collections import deque
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent.parent
_TOOLS_DIR = str(Path(__file__).resolve().parent)
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
# Running as tools/watchdog.py puts tools/ on sys.path and shadows stdlib calendar.
sys.path = [p for p in sys.path if p not in ("", _TOOLS_DIR)]

from app.config import CLIENT_ID, CLIENTS_DIR, LOGS_DIR
from tools.logger import LOG_PATH, log_event
from tools.telegram import send_operator_alert

WATCHDOG_LOCK_PATH = LOGS_DIR / "watchdog.lock"
DEADMAN_STATE_PATH = LOGS_DIR / "deadman_alert_state.json"
SCHEDULER_STATE_PATH = LOGS_DIR / "scheduler_state.json"

POLL_INTERVAL = 5
DEADMAN_CHECK_INTERVAL = 60
DEDUP_WINDOW_SECONDS = 300
UNKNOWN_THRESHOLD = 3
UNKNOWN_WINDOW_SECONDS = 600

# Mirror of DEFAULT_* in core/scheduler.py. Kept here so watchdog does not
# import the scheduler module (handlers, FUB, CrewAI) into this process.
_FALLBACK_DIGEST_HOUR = 8
_FALLBACK_DIGEST_MINUTE = 30
_FALLBACK_PRE_APPT_INTERVAL_SECONDS = 900
_PACIFIC = ZoneInfo("America/Los_Angeles")
# After this Pacific time with no success for today's Pacific date, alert once.
_FALLBACK_DIGEST_BACKSTOP_HOUR = 10
_FALLBACK_DIGEST_BACKSTOP_MINUTE = 0

SUGGESTED_ACTIONS = {
    "LLM_ERROR": "Check OpenRouter quota and retry logic in crew.py",
    "FUB_ERROR": "Check FUB API credentials and rate limits. Verify contact ID.",
    "TELEGRAM_ERROR": "Restart polling loop. Check TELEGRAM_BOT_TOKEN in .env",
    "TOOL_ERROR": "Check tool implementation status. May be a stub.",
    "AGENT_ERROR": "Restart crew task. Check agents.yaml for model assignment.",
    "UNKNOWN_ERROR": "Review log manually. Pattern not recognized.",
}

CLASS_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    (
        "LLM_ERROR",
        re.compile(
            r"openrouter|rate limit|LLM|inference|model",
            re.IGNORECASE,
        ),
    ),
    (
        "FUB_ERROR",
        re.compile(r"FUB|followupboss|fub_api", re.IGNORECASE),
    ),
    (
        "TELEGRAM_ERROR",
        re.compile(r"telegram|polling", re.IGNORECASE),
    ),
    (
        "TOOL_ERROR",
        re.compile(r"NotImplementedError|tool execution", re.IGNORECASE),
    ),
    (
        "AGENT_ERROR",
        re.compile(r"CrewAI|crew|supervisor|max iterations", re.IGNORECASE),
    ),
]

ERROR_LEVEL_PATTERN = re.compile(r"\bERROR\b", re.IGNORECASE)
FILE_FUNCTION_PATTERN = re.compile(
    r"(?P<file>[\w./\\-]+\.py):(?P<function>[\w.<>\[\]]+)"
)

SKIP_AGENTS = {"monitoring", "watchdog"}


def _load_schedule_windows() -> dict:
    """Job schedule knobs from scheduler_config.json, else defaults."""
    config_path = CLIENTS_DIR / CLIENT_ID / "scheduler_config.json"
    try:
        with config_path.open(encoding="utf-8") as f:
            config = json.load(f)
        digest = config.get("morning_digest") or {}
        pre = config.get("pre_appointment_check") or {}
        return {
            "morning_digest": {
                "hour": int(digest.get("hour", _FALLBACK_DIGEST_HOUR)),
                "minute": int(digest.get("minute", _FALLBACK_DIGEST_MINUTE)),
                "backstop_hour": int(
                    digest.get(
                        "deadman_backstop_hour", _FALLBACK_DIGEST_BACKSTOP_HOUR
                    )
                ),
                "backstop_minute": int(
                    digest.get(
                        "deadman_backstop_minute", _FALLBACK_DIGEST_BACKSTOP_MINUTE
                    )
                ),
            },
            "pre_appointment_check": {
                "interval_seconds": int(
                    pre.get("interval_seconds", _FALLBACK_PRE_APPT_INTERVAL_SECONDS)
                ),
            },
        }
    except (FileNotFoundError, json.JSONDecodeError, TypeError, ValueError, OSError):
        return {
            "morning_digest": {
                "hour": _FALLBACK_DIGEST_HOUR,
                "minute": _FALLBACK_DIGEST_MINUTE,
                "backstop_hour": _FALLBACK_DIGEST_BACKSTOP_HOUR,
                "backstop_minute": _FALLBACK_DIGEST_BACKSTOP_MINUTE,
            },
            "pre_appointment_check": {
                "interval_seconds": _FALLBACK_PRE_APPT_INTERVAL_SECONDS,
            },
        }


def _load_deadman_state() -> dict:
    try:
        with DEADMAN_STATE_PATH.open(encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return {}


def _save_deadman_state(state: dict) -> None:
    DEADMAN_STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(
        dir=str(DEADMAN_STATE_PATH.parent),
        prefix="deadman_alert_state.",
        suffix=".tmp",
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(state, f)
            f.flush()
            os.fsync(f.fileno())
        os.replace(temp_name, DEADMAN_STATE_PATH)
    except Exception:
        try:
            os.unlink(temp_name)
        except OSError:
            pass


def _parse_log_timestamp(value: str) -> datetime | None:
    try:
        ts = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    if ts.tzinfo is None:
        return ts.replace(tzinfo=timezone.utc)
    return ts


def _to_pacific(ts: datetime) -> datetime:
    """Convert any aware/naive-as-UTC timestamp to America/Los_Angeles."""
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    return ts.astimezone(_PACIFIC)


def _format_pacific_hhmm(hour: int, minute: int) -> str:
    ampm = "AM" if hour < 12 else "PM"
    hour12 = hour % 12 or 12
    return f"{hour12}:{minute:02d} {ampm}"


def _morning_digest_sent_on_pacific_date(pacific_date) -> bool:
    """True when scheduler_state.json records a digest send on pacific_date.

    Requires last_morning_digest_date to match. Hollow scheduler success log
    lines without a state write do not satisfy this check.
    """
    try:
        with SCHEDULER_STATE_PATH.open(encoding="utf-8") as handle:
            state = json.load(handle)
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return False
    if not isinstance(state, dict):
        return False
    return str(state.get("last_morning_digest_date") or "") == pacific_date.isoformat()


def _has_scheduler_success_on_pacific_date(action: str, pacific_date) -> bool:
    """True if a scheduler success for action falls on pacific_date (LA calendar day)."""
    if not LOG_PATH.exists():
        return False

    try:
        with LOG_PATH.open("r", encoding="utf-8", errors="replace") as handle:
            for line in handle:
                stripped = line.strip()
                if not stripped:
                    continue
                try:
                    entry = json.loads(stripped)
                except json.JSONDecodeError:
                    continue
                if entry.get("agent") != "scheduler":
                    continue
                if entry.get("action") != action:
                    continue
                if str(entry.get("status", "")).lower() != "success":
                    continue
                ts = _parse_log_timestamp(str(entry.get("timestamp", "")))
                if ts is None:
                    continue
                if _to_pacific(ts).date() == pacific_date:
                    return True
    except OSError:
        return False
    return False


def _find_scheduler_successes(
    action: str,
    window_start: datetime,
    window_end: datetime,
) -> list[datetime]:
    """Return UTC timestamps of scheduler success events for action in window.

    Used by pre_appointment_check stall detection only.
    """
    if not LOG_PATH.exists():
        return []

    matches: list[datetime] = []
    try:
        with LOG_PATH.open("r", encoding="utf-8", errors="replace") as handle:
            for line in handle:
                stripped = line.strip()
                if not stripped:
                    continue
                try:
                    entry = json.loads(stripped)
                except json.JSONDecodeError:
                    continue
                if entry.get("agent") != "scheduler":
                    continue
                if entry.get("action") != action:
                    continue
                if str(entry.get("status", "")).lower() != "success":
                    continue
                ts = _parse_log_timestamp(str(entry.get("timestamp", "")))
                if ts is None:
                    continue
                if window_start <= ts <= window_end:
                    matches.append(ts)
    except OSError:
        return []
    return matches


def check_deadman_switches(dry_run: bool = False) -> list[str]:
    """Alert operator if a scheduled job has no success for today's Pacific date.

    morning_digest: success on today's LA date -> confirm log, no alert.
    No success and past backstop -> one alert + fallback log.
    No success before backstop -> silent (not yet, not failed).

    One alert per job per day via logs/deadman_alert_state.json.
    Returns alert messages sent (or that would be sent in dry_run).
    """
    now_pacific = datetime.now(_PACIFIC)
    pacific_date = now_pacific.date()
    today = pacific_date.isoformat()
    today_start_pacific = now_pacific.replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    windows = _load_schedule_windows()
    deadman_state = _load_deadman_state()
    sent: list[str] = []
    state_dirty = False

    # --- morning_digest: Pacific calendar day + backstop deadline ---
    digest = windows["morning_digest"]
    backstop = today_start_pacific.replace(
        hour=digest["backstop_hour"],
        minute=digest["backstop_minute"],
    )
    digest_ok = _morning_digest_sent_on_pacific_date(pacific_date)

    if digest_ok:
        if deadman_state.get("morning_digest_confirmed") != today:
            detail = f"morning_digest confirmed for {today}"
            if dry_run:
                print(f"deadman_check success: {detail}", flush=True)
            else:
                log_event(
                    "watchdog",
                    "deadman_check",
                    "success",
                    detail=detail,
                    file=__file__,
                    function="check_deadman_switches",
                )
            deadman_state["morning_digest_confirmed"] = today
            state_dirty = True
    elif now_pacific >= backstop:
        if deadman_state.get("morning_digest") != today:
            hhmm = _format_pacific_hhmm(
                digest["backstop_hour"], digest["backstop_minute"]
            )
            message = (
                f"Morning digest did not run today. "
                f"No success logged for {today} Pacific by {hhmm} Pacific. "
                f"Check the scheduler and logs/scheduler_state.json."
            )
            if dry_run:
                print(message, flush=True)
            else:
                send_operator_alert(message)
                log_event(
                    "watchdog",
                    "deadman_check",
                    "fallback",
                    detail=f"morning_digest missing for {today}",
                    file=__file__,
                    function="check_deadman_switches",
                )
            deadman_state["morning_digest"] = today
            state_dirty = True
            sent.append(message)
    # else: before backstop with no success yet -- silent

    # --- pre_appointment_check: recurring; expect success within 2x interval ---
    pre = windows["pre_appointment_check"]
    interval = pre["interval_seconds"]
    grace = interval  # allow one full missed cycle before alerting
    stall_limit = interval + grace
    first_deadline = today_start_pacific + timedelta(seconds=stall_limit)
    if now_pacific >= first_deadline and deadman_state.get("pre_appointment_check") != today:
        window_start_utc = today_start_pacific.astimezone(timezone.utc)
        window_end_utc = now_pacific.astimezone(timezone.utc)
        successes = _find_scheduler_successes(
            "pre_appointment_check", window_start_utc, window_end_utc
        )
        latest = max(successes) if successes else None
        stalled = False
        if latest is None:
            stalled = True
        else:
            age_seconds = (
                now_pacific.astimezone(timezone.utc) - latest
            ).total_seconds()
            if age_seconds > stall_limit:
                stalled = True
        if stalled:
            message = (
                "Pre-appointment check has not logged a success recently. "
                "The scheduler may be wedged. Check cos-agent."
            )
            if dry_run:
                print(message, flush=True)
            else:
                send_operator_alert(message)
            deadman_state["pre_appointment_check"] = today
            state_dirty = True
            sent.append(message)

    if state_dirty and not dry_run:
        try:
            _save_deadman_state(deadman_state)
        except Exception:
            pass
    return sent


def classify_error(message: str) -> str:
    for error_class, pattern in CLASS_PATTERNS:
        if pattern.search(message):
            return error_class
    return "UNKNOWN_ERROR"


def is_error_line(line: str) -> bool:
    stripped = line.strip()
    if not stripped:
        return False

    try:
        entry = json.loads(stripped)
    except json.JSONDecodeError:
        return bool(ERROR_LEVEL_PATTERN.search(stripped))

    if entry.get("agent") in SKIP_AGENTS:
        return False

    # COS_DIAGNOSTIC_MODE probes tag log lines so watchdog does not page the operator
    if entry.get("diagnostic") is True:
        return False

    status = str(entry.get("status", "")).lower()
    return status == "failure" or bool(ERROR_LEVEL_PATTERN.search(stripped))


def parse_log_line(line: str) -> tuple[str, str, str, str, str]:
    """Return timestamp, raw_message, file, function, searchable_text."""
    stripped = line.strip()
    timestamp = datetime.now(timezone.utc).isoformat()
    raw_message = stripped
    file_name = "unknown"
    function_name = "unknown"
    searchable = stripped

    try:
        entry = json.loads(stripped)
        timestamp = str(entry.get("timestamp", timestamp))
        agent = entry.get("agent", "")
        action = entry.get("action", "")
        status = entry.get("status", "")
        detail = entry.get("detail", "")
        contact_id = entry.get("contact_id", "")
        raw_message = (
            f"agent={agent} action={action} status={status} "
            f"detail={detail} contact_id={contact_id}"
        ).strip()
        searchable = f"{agent} {action} {status} {detail} {contact_id}"
    except json.JSONDecodeError:
        pass

    match = FILE_FUNCTION_PATTERN.search(stripped)
    if match:
        file_name = match.group("file")
        function_name = match.group("function")

    return timestamp, raw_message, file_name, function_name, searchable


def format_alert(
    error_class: str,
    timestamp: str,
    file_name: str,
    function_name: str,
    raw_message: str,
    context_lines: list[str],
) -> str:
    while len(context_lines) < 3:
        context_lines.append("(none)")

    lines = [
        f"🚨 [{CLIENT_ID}] — {error_class}",
        "",
        f"Time: {timestamp}",
        f"File: {file_name}:{function_name}",
        f"Message: {raw_message}",
        "",
        "Last 3 lines:",
        f"→ {context_lines[0]}",
        f"→ {context_lines[1]}",
        f"→ {context_lines[2]}",
        "",
        f"Suggested action: {SUGGESTED_ACTIONS[error_class]}",
    ]
    return "\n".join(lines)


class Watchdog:
    def __init__(self, dry_run: bool = False) -> None:
        self.dry_run = dry_run
        self.log_path = LOG_PATH
        self.last_alerted: dict[str, float] = {}
        self.unknown_timestamps: deque[float] = deque()
        self.recent_lines: deque[str] = deque(maxlen=3)
        self._position = 0
        self._last_deadman_check = 0.0

    def _should_alert(self, error_class: str, now: float) -> bool:
        last = self.last_alerted.get(error_class)
        if last is not None and (now - last) < DEDUP_WINDOW_SECONDS:
            return False

        if error_class != "UNKNOWN_ERROR":
            return True

        self.unknown_timestamps.append(now)
        cutoff = now - UNKNOWN_WINDOW_SECONDS
        while self.unknown_timestamps and self.unknown_timestamps[0] < cutoff:
            self.unknown_timestamps.popleft()

        if len(self.unknown_timestamps) < UNKNOWN_THRESHOLD:
            return False

        self.unknown_timestamps.clear()
        return True

    def _send_alert(self, message: str) -> None:
        if self.dry_run:
            print(message, flush=True)
            print("-" * 60, flush=True)
            return
        send_operator_alert(message)

    def _handle_error_line(self, line: str) -> None:
        timestamp, raw_message, file_name, function_name, searchable = parse_log_line(
            line
        )
        error_class = classify_error(searchable)
        now = time.time()

        if not self._should_alert(error_class, now):
            return

        self.last_alerted[error_class] = now
        context = list(self.recent_lines)
        alert = format_alert(
            error_class,
            timestamp,
            file_name,
            function_name,
            raw_message,
            context,
        )
        self._send_alert(alert)

    def _read_new_lines(self) -> list[str]:
        if not self.log_path.exists():
            self._position = 0
            return []

        with open(self.log_path, "rb") as handle:
            handle.seek(0, os.SEEK_END)
            end_pos = handle.tell()

            if end_pos < self._position:
                self._position = 0

            handle.seek(self._position)
            chunk_bytes = handle.read()
            new_pos = handle.tell()

        if not chunk_bytes:
            return []

        if not chunk_bytes.endswith(b"\n"):
            last_newline = chunk_bytes.rfind(b"\n")
            if last_newline == -1:
                return []
            chunk_bytes = chunk_bytes[: last_newline + 1]
            self._position += len(chunk_bytes)
        else:
            self._position = new_pos

        return chunk_bytes.decode("utf-8", errors="replace").splitlines()

    def _process_line(self, line: str) -> None:
        if is_error_line(line):
            self._handle_error_line(line)
        self.recent_lines.append(line.strip())

    def run(self) -> None:
        WATCHDOG_LOCK_PATH.parent.mkdir(parents=True, exist_ok=True)
        lock_handle = open(WATCHDOG_LOCK_PATH, "w", encoding="utf-8")
        try:
            fcntl.flock(lock_handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return

        if self.log_path.exists():
            with open(self.log_path, "r", encoding="utf-8", errors="replace") as handle:
                handle.seek(0, os.SEEK_END)
                self._position = handle.tell()

        while True:
            try:
                for line in self._read_new_lines():
                    self._process_line(line)
                now_mono = time.monotonic()
                if now_mono - self._last_deadman_check >= DEADMAN_CHECK_INTERVAL:
                    self._last_deadman_check = now_mono
                    check_deadman_switches(dry_run=self.dry_run)
            except Exception as exc:
                if self.dry_run:
                    print(f"watchdog error: {exc}", file=sys.stderr)
            time.sleep(POLL_INTERVAL)


def main() -> None:
    parser = argparse.ArgumentParser(description="Monitor cos_agent.log for errors.")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print alerts to stdout instead of sending Telegram.",
    )
    args = parser.parse_args()
    Watchdog(dry_run=args.dry_run).run()


if __name__ == "__main__":
    main()
