"""Telegram polling loop connecting inbound messages to CoS Agent brief generation."""

from __future__ import annotations

import os
import re
import subprocess
import sys
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from crew import run_brief
from tools.fub import get_contact_by_id, search_contacts
from tools.health import run_health_check
from tools.logger import log_event
from tools.telegram import CHAT_ID, extract_message, get_updates, send_message, send_operator_alert

BRIEF_ID_PATTERN = re.compile(r"^(?:/)?brief\s+(\d+)$", re.IGNORECASE)
BRIEF_NAME_PATTERN = re.compile(
    r"^(?:/)?brief\s+([A-Za-z][A-Za-z\s\-'\.]{1,50})$", re.IGNORECASE
)
GREETING_PATTERN = re.compile(r"^(?:hello|hi)$", re.IGNORECASE)
IDENTITY_PATTERN = re.compile(
    r"^(who are you|what are you|what do you do|what can you do|do you do anything else).*$",
    re.IGNORECASE,
)
HELP_PATTERN = re.compile(r"^(help|commands|options|\?)$", re.IGNORECASE)
POLL_TIMEOUT = 30
BRIEF_ERROR_MSG = (
    "I ran into a problem pulling that brief. Check FUB directly: "
    "https://app.followupboss.com"
)
UNKNOWN_MSG = "I didn't get that. Try: brief 31735 or brief Scott Eggert"
GREETING_REPLY = "Chief of Staff here. Send me a contact ID or name and I'll pull a brief."
IDENTITY_REPLY = "I'm Ben's Chief of Staff. Right now I pull pre-appointment briefs on contacts. Send me a name or contact ID and I'll get you what I know."
HELP_REPLY = "Here's what I can do:\n• brief [name] — pull a contact brief by name\n• brief [ID] — pull a contact brief by FUB ID\n• hello — check that I'm online"

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
            log_event(
                "health",
                "startup",
                "failure",
                detail=f"missing {key}",
                file=__file__,
                function="startup_check",
            )
            send_operator_alert(f"CoS Agent failed to start — missing env var: {key}")
            raise SystemExit(f"CoS Agent failed to start — missing env var: {key}")
        log_event(
            "health",
            "startup",
            "success",
            detail=f"{key} set",
            file=__file__,
            function="startup_check",
        )

    health_contact_id = os.environ.get("HEALTH_CHECK_CONTACT_ID", "").strip()
    if health_contact_id:
        log_event(
            "health",
            "startup",
            "start",
            detail="fub connectivity check",
            contact_id=health_contact_id,
            file=__file__,
            function="startup_check",
        )
        try:
            get_contact_by_id(health_contact_id)
            log_event(
                "health",
                "startup",
                "success",
                detail="fub connectivity check",
                contact_id=health_contact_id,
                file=__file__,
                function="startup_check",
            )
        except Exception as exc:
            log_event(
                "health",
                "startup",
                "failure",
                detail=f"fub connectivity check: {exc}",
                contact_id=health_contact_id,
                exc_info=exc,
            )
            send_operator_alert(
                f"CoS Agent failed to start — FUB connectivity check failed: {exc}"
            )
            raise SystemExit(
                f"CoS Agent failed to start — FUB connectivity check failed: {exc}"
            )
    else:
        log_event(
            "health",
            "startup",
            "success",
            detail="fub check skipped",
            file=__file__,
            function="startup_check",
        )

    log_event(
        "health",
        "startup",
        "success",
        file=__file__,
        function="startup_check",
    )


def _handle_message(client_id: str, text: str) -> str:
    if GREETING_PATTERN.match(text.strip()):
        return GREETING_REPLY

    if IDENTITY_PATTERN.match(text.strip()):
        return IDENTITY_REPLY
    if HELP_PATTERN.match(text.strip()):
        return HELP_REPLY

    brief_match = BRIEF_ID_PATTERN.match(text.strip())
    if brief_match:
        contact_id = brief_match.group(1)
        log_event(
            "bot",
            "brief_requested",
            "start",
            contact_id=contact_id,
            file=__file__,
            function="_handle_message",
        )
        log_event(
            "cos_agent",
            "run_brief",
            "start",
            contact_id=contact_id,
            file=__file__,
            function="_handle_message",
        )
        try:
            result = run_brief(client_id, contact_id)
            log_event(
                "cos_agent",
                "run_brief",
                "success",
                contact_id=contact_id,
                file=__file__,
                function="_handle_message",
            )
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
                exc_info=exc,
            )
            return BRIEF_ERROR_MSG

    name_match = BRIEF_NAME_PATTERN.match(text.strip())
    if name_match:
        query = name_match.group(1).strip()
        log_event(
            "bot",
            "name_lookup",
            "start",
            detail=query,
            file=__file__,
            function="_handle_message",
        )
        results = search_contacts(query, limit=5)
        if not results:
            return f"No contact found for '{query}'. Check the name or use a contact ID."
        if len(results) > 1:
            lines = [f"Found {len(results)} matches. Which one?"]
            for p in results:
                name = f"{p.get('firstName', '')} {p.get('lastName', '')}".strip()
                cid = str(p.get("id", ""))
                lines.append(f"  brief {cid} — {name}")
            return "\n".join(lines)
        contact = results[0]
        contact_id = str(contact.get("id", ""))
        name = f"{contact.get('firstName', '')} {contact.get('lastName', '')}".strip()
        log_event(
            "bot",
            "name_lookup",
            "success",
            detail=f"{name} → {contact_id}",
            file=__file__,
            function="_handle_message",
        )
        log_event(
            "bot",
            "brief_requested",
            "start",
            contact_id=contact_id,
            file=__file__,
            function="_handle_message",
        )
        log_event(
            "cos_agent",
            "run_brief",
            "start",
            contact_id=contact_id,
            file=__file__,
            function="_handle_message",
        )
        try:
            result = run_brief(client_id, contact_id)
            log_event(
                "cos_agent",
                "run_brief",
                "success",
                contact_id=contact_id,
                file=__file__,
                function="_handle_message",
            )
            return result
        except Exception as exc:
            log_event(
                "cos_agent",
                "run_brief",
                "failure",
                detail=str(exc),
                contact_id=contact_id,
                exc_info=exc,
            )
            return BRIEF_ERROR_MSG

    return UNKNOWN_MSG


def _watchdog_supervisor() -> None:
    """Keep tools/watchdog.py running; restart automatically on crash."""
    while True:
        log_event(
            "monitoring",
            "watchdog",
            "start",
            file=__file__,
            function="_watchdog_supervisor",
        )
        proc = subprocess.Popen(
            [sys.executable, "-m", "tools.watchdog"],
            cwd=str(ROOT),
        )
        proc.wait()
        log_event(
            "monitoring",
            "watchdog",
            "failure",
            detail=f"exit code {proc.returncode}",
            file=__file__,
            function="_watchdog_supervisor",
        )
        time.sleep(2)


def _start_watchdog() -> threading.Thread:
    thread = threading.Thread(target=_watchdog_supervisor, daemon=True)
    thread.start()
    return thread


def run_bot(client_id: str) -> None:
    """Poll Telegram indefinitely and route messages to CoS Agent."""
    startup_check()
    _start_watchdog()
    log_event(
        "cos_agent",
        "bot_start",
        "start",
        file=__file__,
        function="run_bot",
    )
    send_message("Chief of Staff is online.")
    log_event(
        "cos_agent",
        "bot_start",
        "success",
        detail="CoS Agent is online.",
        file=__file__,
        function="run_bot",
    )

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
                    file=__file__,
                    function="run_bot",
                )

                reply = _handle_message(client_id, text)

                send_message(reply, chat_id=chat_id)
                log_event(
                    "telegram",
                    "outbound",
                    "success",
                    detail=reply[:200],
                    contact_id="",
                    file=__file__,
                    function="run_bot",
                )
    except KeyboardInterrupt:
        log_event(
            "cos_agent",
            "bot_stop",
            "start",
            detail="keyboard interrupt",
            file=__file__,
            function="run_bot",
        )
        send_message("Chief of Staff going offline.")
        log_event(
            "cos_agent",
            "bot_stop",
            "success",
            detail="CoS Agent going offline.",
            file=__file__,
            function="run_bot",
        )

if __name__ == "__main__":
    run_bot("ben-olsen")
