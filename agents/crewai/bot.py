"""Telegram polling loop connecting inbound messages to CoS Agent brief generation."""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from crew import run_brief
from tools.fub import get_contact_by_id
from tools.health import run_health_check
from tools.logger import log_event
from tools.telegram import CHAT_ID, extract_message, get_updates, send_message, send_operator_alert

BRIEF_PATTERN = re.compile(r"^(?:/)?brief\s+(\d+)$", re.IGNORECASE)
GREETING_PATTERN = re.compile(r"^(?:hello|hi)$", re.IGNORECASE)
POLL_TIMEOUT = 30
BRIEF_ERROR_MSG = (
    "I ran into a problem pulling that brief. Check FUB directly: "
    "https://app.followupboss.com"
)
UNKNOWN_MSG = "I didn't get that. Try: brief 12345"
GREETING_REPLY = "Chief of Staff here. Send me a FUB contact ID and I'll pull a brief."

REQUIRED_ENV_VARS = (
    "FUB_API_KEY",
    "ANTHROPIC_API_KEY",
    "TELEGRAM_BOT_TOKEN",
    "TELEGRAM_CHAT_ID",
)


def startup_check() -> None:
    """Verify required env vars and optional FUB connectivity before polling."""
    for key in REQUIRED_ENV_VARS:
        value = os.environ.get(key, "")
        if not value:
            log_event("health", "startup", "failure", detail=f"missing {key}")
            send_operator_alert(f"CoS Agent failed to start — missing env var: {key}")
            raise SystemExit(f"CoS Agent failed to start — missing env var: {key}")
        log_event("health", "startup", "success", detail=f"{key} set")

    health_contact_id = os.environ.get("HEALTH_CHECK_CONTACT_ID", "").strip()
    if health_contact_id:
        log_event(
            "health",
            "startup",
            "start",
            detail="fub connectivity check",
            contact_id=health_contact_id,
        )
        try:
            get_contact_by_id(health_contact_id)
            log_event(
                "health",
                "startup",
                "success",
                detail="fub connectivity check",
                contact_id=health_contact_id,
            )
        except Exception as exc:
            log_event(
                "health",
                "startup",
                "failure",
                detail=f"fub connectivity check: {exc}",
                contact_id=health_contact_id,
            )
            send_operator_alert(
                f"CoS Agent failed to start — FUB connectivity check failed: {exc}"
            )
            raise SystemExit(
                f"CoS Agent failed to start — FUB connectivity check failed: {exc}"
            )
    else:
        log_event("health", "startup", "success", detail="fub check skipped")

    log_event("health", "startup", "success")


def _handle_message(client_id: str, text: str) -> str:
    if GREETING_PATTERN.match(text.strip()):
        return GREETING_REPLY

    brief_match = BRIEF_PATTERN.match(text.strip())
    if brief_match:
        contact_id = brief_match.group(1)
        log_event("bot", "brief_requested", "start", contact_id=contact_id)
        log_event("cos_agent", "run_brief", "start", contact_id=contact_id)
        try:
            result = run_brief(client_id, contact_id)
            log_event("cos_agent", "run_brief", "success", contact_id=contact_id)
            run_health_check(
                "brief",
                {
                    "status": "success",
                    "agent": "brief_generator",
                    "action": "generate_brief",
                    "contact_id": contact_id,
                },
            )
            return result
        except Exception as exc:
            run_health_check(
                "brief",
                {
                    "status": "failure",
                    "agent": "brief_generator",
                    "action": "generate_brief",
                    "detail": str(exc),
                    "contact_id": contact_id,
                },
            )
            log_event(
                "cos_agent",
                "run_brief",
                "failure",
                detail=str(exc),
                contact_id=contact_id,
            )
            return BRIEF_ERROR_MSG

    return UNKNOWN_MSG


def run_bot(client_id: str) -> None:
    """Poll Telegram indefinitely and route messages to CoS Agent."""
    startup_check()
    log_event("cos_agent", "bot_start", "start")
    send_message("Chief of Staff is online.")
    log_event("cos_agent", "bot_start", "success", detail="CoS Agent is online.")

    offset = 0
    configured_chat_id = str(CHAT_ID)

    try:
        while True:
            updates = get_updates(offset=offset, timeout=POLL_TIMEOUT)
            for update in updates:
                update_id = update.get("update_id", 0)
                offset = update_id + 1

                message = extract_message(update)
                if not message:
                    continue

                chat_id = message["chat_id"]
                if chat_id != configured_chat_id:
                    continue

                text = message["text"]
                log_event(
                    "telegram",
                    "inbound",
                    "success",
                    detail=text,
                    contact_id="",
                )

                reply = _handle_message(client_id, text)

                send_message(reply, chat_id=chat_id)
                log_event(
                    "telegram",
                    "outbound",
                    "success",
                    detail=reply[:200],
                    contact_id="",
                )
    except KeyboardInterrupt:
        log_event("cos_agent", "bot_stop", "start", detail="keyboard interrupt")
        send_message("Chief of Staff going offline.")
        log_event("cos_agent", "bot_stop", "success", detail="CoS Agent going offline.")
