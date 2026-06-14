"""Structured JSON logging for CoS Agent events."""

from __future__ import annotations

import json
import traceback
from datetime import datetime, timezone
from pathlib import Path

LOG_PATH = Path(__file__).resolve().parent.parent / "logs" / "cos_agent.log"


def log_event(
    agent: str,
    action: str,
    status: str,
    detail: str = "",
    contact_id: str = "",
    file: str = "",
    function: str = "",
    exc_info: BaseException | None = None,
) -> None:
    """Write one JSON log line. Never raises."""
    try:
        resolved_file = file
        resolved_function = function
        exc_info_line: str | None = None

        if exc_info is not None:
            if exc_info.__traceback__ is not None:
                frames = traceback.extract_tb(exc_info.__traceback__)
                if frames:
                    last_frame = frames[-1]
                    if not resolved_file:
                        resolved_file = last_frame.filename
                    if not resolved_function:
                        resolved_function = last_frame.name

            tb_lines = traceback.format_exception(
                type(exc_info), exc_info, exc_info.__traceback__
            )
            if tb_lines:
                exc_info_line = tb_lines[-1].strip()
            else:
                exc_info_line = str(exc_info)

        LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "agent": agent,
            "action": action,
            "status": status,
            "detail": detail,
            "contact_id": contact_id,
            "file": resolved_file,
            "function": resolved_function,
        }
        if exc_info_line is not None:
            entry["exc_info"] = exc_info_line
        with open(LOG_PATH, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")
    except Exception:
        pass
