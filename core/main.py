"""CoS Agent entry point.

Wires transport, router, handlers, and scheduler together.
This file orchestrates; it contains no business logic.

Usage:
    python -m core.main
"""

from __future__ import annotations

import json

from app.config import CLIENT_ID, CLIENTS_DIR
from app.schemas import InboundCallback, InboundMessage
from core.router import ConversationBuffer, classify_intent
from core.scheduler import SimpleScheduler, morning_digest, pre_appointment_check
from core.transport import poll
from handlers import brief, generative, hot_leads, lead_alert, status
from tools.logger import log_event
from tools.telegram import send_operator_alert

_buffer = ConversationBuffer()


def _route_message(message: InboundMessage) -> str | None:
    """Classify intent and dispatch to handler. Return reply string or None."""
    intent = classify_intent(message, _buffer)

    if intent.intent_type == "greeting":
        return generative.handle_greeting(intent).telegram_output

    if intent.intent_type == "identity_query":
        return generative.handle_identity(intent).telegram_output

    if intent.intent_type == "help_request":
        return generative.handle_help(intent).telegram_output

    if intent.intent_type == "brief_request":
        result = brief.handle(intent)
        return result.telegram_output

    if intent.intent_type in ("hot_leads", "hot_leads_list"):
        result = hot_leads.handle(intent)
        return result.telegram_output

    if intent.intent_type in ("draft_outreach", "draft_communication"):
        result = generative.handle(intent)
        return result.telegram_output

    if intent.intent_type == "status_check":
        lines = int(intent.entity or 50)
        result = status.handle_status(lines)
        return result.telegram_output

    return generative.handle_fallback(intent).telegram_output


def _route_callback(callback: InboundCallback) -> str | None:
    """Route inline keyboard button presses to lead_alert handler."""
    result = lead_alert.handle_callback(callback)
    return result.telegram_output if result.telegram_output else None


def _build_scheduled_jobs(scheduler: SimpleScheduler) -> None:
    """Register all scheduled jobs. Job functions call tools/ directly."""
    config_path = CLIENTS_DIR / CLIENT_ID / "scheduler_config.json"
    with config_path.open(encoding="utf-8") as f:
        sched_config = json.load(f)

    digest_hour = sched_config["morning_digest"]["hour"]
    digest_minute = sched_config["morning_digest"]["minute"]
    appt_interval = sched_config["pre_appointment_check"]["interval_seconds"]

    scheduler.add_daily(
        hour=digest_hour, minute=digest_minute,
        job=morning_digest, name="morning_digest",
    )
    scheduler.add_interval(
        seconds=appt_interval,
        job=pre_appointment_check, name="pre_appointment_check",
    )


def main() -> None:
    """Start the CoS agent."""
    from app.config import HEALTH_CHECK_CONTACT_ID
    from tools.fub import get_contact_by_id

    log_event("cos_agent", "startup", "start", file=__file__, function="main")

    # Startup health check
    if HEALTH_CHECK_CONTACT_ID:
        try:
            get_contact_by_id(HEALTH_CHECK_CONTACT_ID)
            log_event(
                "cos_agent", "startup", "success",
                detail="FUB connectivity confirmed",
                file=__file__, function="main",
            )
        except Exception as exc:
            send_operator_alert(f"CoS Agent startup failed -- FUB check: {exc}")
            raise SystemExit(f"FUB connectivity check failed: {exc}")

    send_operator_alert("CoS Agent is online.")
    log_event("cos_agent", "startup", "success", file=__file__, function="main")

    # Start scheduler
    scheduler = SimpleScheduler()
    _build_scheduled_jobs(scheduler)
    scheduler.start()

    # Start buffer (already initialized at module level)
    log_event(
        "cos_agent", "buffer", "start",
        detail="ConversationBuffer loaded",
        file=__file__, function="main",
    )

    # Start polling loop (blocks)
    try:
        poll(on_message=_route_message, on_callback=_route_callback)
    except KeyboardInterrupt:
        send_operator_alert("CoS Agent going offline.")
        log_event("cos_agent", "shutdown", "success", file=__file__, function="main")


if __name__ == "__main__":
    main()
