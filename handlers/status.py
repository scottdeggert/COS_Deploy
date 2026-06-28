"""Status command handler -- returns recent log tail."""

from __future__ import annotations

from app.config import LOGS_DIR
from app.schemas import HandlerResult
from tools.logger import log_event
from tools.telegram import send_operator_alert

FALLBACK_MESSAGE = "Could not read the status log right now."


def handle_status(lines: int = 50) -> HandlerResult:
    """Return recent log lines as a HandlerResult."""
    log_event(
        "status", "get_log", "start",
        file=__file__, function="handle_status",
    )
    log_path = LOGS_DIR / "cos_agent.log"
    try:
        if not log_path.exists():
            return HandlerResult(
                success=True,
                telegram_output="No log file found.",
            )
        with log_path.open(encoding="utf-8") as f:
            all_lines = f.readlines()
        tail = all_lines[-lines:]
        output = "".join(tail)[:3800]
        log_event(
            "status", "get_log", "success",
            file=__file__, function="handle_status",
        )
        return HandlerResult(success=True, telegram_output=output)
    except Exception as exc:
        log_event(
            "status", "get_log", "failure",
            detail=str(exc), exc_info=exc,
            file=__file__, function="handle_status",
        )
        send_operator_alert(f"Status handler failed: {exc}")
        return HandlerResult(
            success=False,
            telegram_output=FALLBACK_MESSAGE,
            error_details=str(exc),
        )
