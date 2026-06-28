"""CoS Agent entry point.

Wires transport, router, handlers, and scheduler together.
This file orchestrates; it contains no business logic.

Usage:
    python -m core.main
"""

from __future__ import annotations

import re

from app.config import CLIENT_ID
from app.schemas import InboundCallback, InboundMessage, RoutedIntent
from core.router import ConversationBuffer, classify_intent
from core.scheduler import SimpleScheduler
from core.transport import poll
from handlers import brief, generative, hot_leads, lead_alert, status
from tools.logger import log_event
from tools.telegram import send_long_message, send_operator_alert

STATUS_PATTERN = re.compile(r"^(?:/)?status(?:\s+(\d+))?$", re.IGNORECASE)

GREETING_REPLY = "Chief of Staff here. Send me a contact ID or name and I'll pull a brief."
IDENTITY_REPLY = (
    "I'm Ben's Chief of Staff. I pull pre-appointment briefs, draft emails in your voice, "
    "and monitor your pipeline. Send me a name or contact ID to get started."
)
HELP_REPLY = (
    "Here's what I can do:\n"
    "* brief [name] or [ID] -- pull a contact brief\n"
    "* draft an email to [name] about [topic]\n"
    "* hot leads -- see your warm pipeline going cold\n"
    "* status -- check recent agent log"
)
UNKNOWN_REPLY = (
    "I didn't catch that. Try asking me to draft an email, "
    "pull up a contact, or check your hot leads."
)

_buffer = ConversationBuffer()


def _route_message(message: InboundMessage) -> str | None:
    """Classify intent and dispatch to handler. Return reply string or None."""

    # Status command bypasses classifier
    status_match = STATUS_PATTERN.match(message.raw_text.strip())
    if status_match:
        lines = int(status_match.group(1) or 50)
        result = status.handle_status(lines)
        return result.telegram_output

    # Classify via Haiku
    intent = classify_intent(message, _buffer)

    if intent.intent_type == "greeting":
        return GREETING_REPLY

    if intent.intent_type == "identity_query":
        return IDENTITY_REPLY

    if intent.intent_type == "help_request":
        return HELP_REPLY

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
        result = status.handle_status(50)
        return result.telegram_output

    return UNKNOWN_REPLY


def _route_callback(callback: InboundCallback) -> str | None:
    """Route inline keyboard button presses to lead_alert handler."""
    result = lead_alert.handle_callback(callback)
    return result.telegram_output if result.telegram_output else None


def _build_scheduled_jobs(scheduler: SimpleScheduler) -> None:
    """Register all scheduled jobs. Job functions call tools/ directly."""
    import json
    import random
    from datetime import datetime, timedelta, timezone

    from app.config import CLIENTS_DIR, TELEGRAM_CHAT_ID
    from tools.appointments import (
        format_appointment_summary,
        get_contact_id_from_appointment,
        get_upcoming_appointments,
    )
    from tools.hot_leads import get_hot_leads_going_cold
    from tools.telegram import send_long_message, send_message

    config_path = CLIENTS_DIR / CLIENT_ID / "scheduler_config.json"
    with config_path.open(encoding="utf-8") as f:
        sched_config = json.load(f)

    digest_hour = sched_config["morning_digest"]["hour"]
    digest_minute = sched_config["morning_digest"]["minute"]
    appt_interval = sched_config["pre_appointment_check"]["interval_seconds"]

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

        send_long_message("\n".join(lines), chat_id=str(TELEGRAM_CHAT_ID))

    def pre_appointment_check(state: dict) -> None:
        from agents.crewai.crew import run_brief as _run_brief

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
                brief_text = _run_brief(CLIENT_ID, contact_id)
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
