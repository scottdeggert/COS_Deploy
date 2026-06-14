"""Continuous log monitor — tails cos_agent.log and alerts operator on errors."""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from collections import deque
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
_TOOLS_DIR = str(Path(__file__).resolve().parent)
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
# Running as tools/watchdog.py puts tools/ on sys.path and shadows stdlib calendar.
sys.path = [p for p in sys.path if p not in ("", _TOOLS_DIR)]

from tools.logger import LOG_PATH
from tools.telegram import send_operator_alert

POLL_INTERVAL = 5
DEDUP_WINDOW_SECONDS = 300
UNKNOWN_THRESHOLD = 3
UNKNOWN_WINDOW_SECONDS = 600

CLIENT_ID = os.environ.get("CLIENT_ID", "unknown-client")

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
        if self.log_path.exists():
            with open(self.log_path, "r", encoding="utf-8", errors="replace") as handle:
                handle.seek(0, os.SEEK_END)
                self._position = handle.tell()

        while True:
            try:
                for line in self._read_new_lines():
                    self._process_line(line)
            except Exception as exc:
                if self.dry_run:
                    print(f"watchdog error: {exc}", file=sys.stderr)
            time.sleep(POLL_INTERVAL)


def main() -> None:
    try:
        from dotenv import load_dotenv

        load_dotenv()
    except ImportError:
        pass

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
