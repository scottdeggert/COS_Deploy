"""Health reporting for CoS Agent jobs. Operator-facing; never raises."""

from __future__ import annotations

from tools.logger import log_event
from tools.telegram import send_operator_alert


def run_health_check(job_name: str, outcome: dict) -> None:
    """Report job outcome. Failures alert the operator; success is log-only."""
    try:
        status = outcome.get("status")
        if status == "failure":
            action = outcome.get("action", "")
            detail = outcome.get("detail", "")
            message = f"[{job_name}] failed — {action}"
            if detail:
                message += f" — {detail}"
            send_operator_alert(message)
            log_event(
                "health",
                job_name,
                "failure",
                detail=outcome.get("detail", ""),
                contact_id=outcome.get("contact_id", ""),
            )
        elif status == "success":
            log_event(
                "health",
                job_name,
                "success",
                contact_id=outcome.get("contact_id", ""),
            )
    except Exception:
        pass
