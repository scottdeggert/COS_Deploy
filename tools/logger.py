"""Structured JSON logging for CoS Agent events."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

LOG_PATH = Path(__file__).resolve().parent.parent / "logs" / "cos_agent.log"


def log_event(
    agent: str,
    action: str,
    status: str,
    detail: str = "",
    contact_id: str = "",
) -> None:
    """Write one JSON log line. Never raises."""
    try:
        LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "agent": agent,
            "action": action,
            "status": status,
            "detail": detail,
            "contact_id": contact_id,
        }
        with open(LOG_PATH, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")
    except Exception:
        pass
