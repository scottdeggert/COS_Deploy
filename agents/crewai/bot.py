"""Telegram polling loop connecting inbound messages to CoS Agent brief generation."""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from crew import run_brief
from tools.fub import (
    SearchContactsDisambiguationResult,
    _contact_summary,
    _person_display_name,
    get_contact_by_id,
    search_contacts,
)
from tools.fub_write import add_note_to_contact, enroll_in_action_plan
from tools.health import run_health_check
from tools.logger import log_event
from tools.telegram import (
    BOT_TOKEN,
    CHAT_ID,
    TELEGRAM_API,
    extract_message,
    get_updates,
    send_inline_message,
    send_message,
    send_operator_alert,
    session as telegram_session,
)

LEAD_ALERT_STATE_PATH = ROOT / "logs" / "lead_alert_state.json"

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


def _load_lead_alert_state() -> dict[str, Any]:
    if not LEAD_ALERT_STATE_PATH.exists():
        return {"drafts": {}, "contacts": {}, "responded": []}
    try:
        with LEAD_ALERT_STATE_PATH.open(encoding="utf-8") as handle:
            return json.load(handle)
    except (json.JSONDecodeError, OSError):
        return {"drafts": {}, "contacts": {}, "responded": []}


def _save_lead_alert_state(state: dict[str, Any]) -> None:
    LEAD_ALERT_STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    with LEAD_ALERT_STATE_PATH.open("w", encoding="utf-8") as handle:
        json.dump(state, handle)


def _get_lead_draft(contact_id: str) -> tuple[str, str]:
    state = _load_lead_alert_state()
    draft = state.get("drafts", {}).get(contact_id, {})
    if isinstance(draft, dict):
        return draft.get("draft_email", ""), draft.get("draft_subject", "")
    return str(draft), ""


def _get_lead_contact(contact_id: str) -> dict[str, str]:
    state = _load_lead_alert_state()
    contact = state.get("contacts", {}).get(contact_id, {})
    if contact:
        return contact
    person = get_contact_by_id(contact_id)
    phones = person.get("phones") or []
    phone = ""
    if isinstance(phones, list) and phones:
        value = phones[0].get("value") if isinstance(phones[0], dict) else phones[0]
        phone = str(value or "")
    return {
        "first_name": str(person.get("firstName", "")),
        "last_name": str(person.get("lastName", "")),
        "phone": phone,
        "source": str(person.get("source", "")),
    }


def _mark_lead_responded(contact_id: str) -> None:
    state = _load_lead_alert_state()
    responded = state.setdefault("responded", [])
    if contact_id not in responded:
        responded.append(contact_id)
    _save_lead_alert_state(state)


def _answer_callback_query(callback_query_id: str) -> None:
    if not callback_query_id:
        return
    url = f"{TELEGRAM_API}/bot{BOT_TOKEN}/answerCallbackQuery"
    payload = {"callback_query_id": callback_query_id}
    try:
        telegram_session.post(url, json=payload, timeout=10)
    except Exception:
        pass


def _drain_stale_updates() -> int:
    """Acknowledge queued updates on startup without executing callbacks or sends."""
    offset = 0
    while True:
        updates = get_updates(offset=offset, timeout=0)
        if not updates:
            break
        for update in updates:
            offset = update.get("update_id", 0) + 1
            callback_query = update.get("callback_query")
            if callback_query:
                _answer_callback_query(callback_query.get("id", ""))
    return offset


def _handle_callback(client_id: str, callback_query: dict) -> None:
    """Route inline keyboard actions for lead alert cards."""
    data = callback_query.get("data", "")
    message = callback_query.get("message", {})
    chat = message.get("chat", {})
    chat_id = str(chat.get("id", ""))

    if not data or ":" not in data:
        return

    action, contact_id = data.split(":", 1)
    contact_info = _get_lead_contact(contact_id)
    first_name = contact_info.get("first_name", "")
    action_plan_id = contact_info.get("action_plan_id")

    if action == "approve":
        if action_plan_id:
            try:
                enroll_in_action_plan(contact_id, int(action_plan_id))
            except Exception as exc:
                log_event(
                    "lead_alert",
                    "approve",
                    "failure",
                    detail=str(exc),
                    contact_id=contact_id,
                    exc_info=exc,
                    file=__file__,
                    function="_handle_callback",
                )
                send_message(
                    "Action plan enrollment failed. Check FUB manually.",
                    chat_id=chat_id,
                )
                return
            send_message(
                f"Sequence started for {first_name}. FUB will send Day 1 email.",
                chat_id=chat_id,
            )
            add_note_to_contact(
                contact_id,
                "Lead Alert: Ben approved. Action plan enrolled by CoS agent.",
            )
            _mark_lead_responded(contact_id)
        else:
            send_message(
                "No sequence mapped for this lead source. Check FUB manually.",
                chat_id=chat_id,
            )
            add_note_to_contact(
                contact_id,
                "Lead Alert: Ben approved but no action plan mapped for source.",
            )
        log_event(
            "lead_alert",
            "approve",
            "success",
            contact_id=contact_id,
            file=__file__,
            function="_handle_callback",
        )
        return

    if action == "brief_pick":
        try:
            result = _run_brief_for_contact(client_id, contact_id)
            send_message(result, chat_id=chat_id)
        except Exception as exc:
            log_event(
                "bot",
                "brief_pick",
                "failure",
                detail=str(exc),
                contact_id=contact_id,
                exc_info=exc,
                file=__file__,
                function="_handle_callback",
            )
            send_message(BRIEF_ERROR_MSG, chat_id=chat_id)
        else:
            log_event(
                "bot",
                "brief_pick",
                "success",
                contact_id=contact_id,
                file=__file__,
                function="_handle_callback",
            )
        return

    if action == "call":
        phone = contact_info.get("phone", "")
        phone_digits = re.sub(r"\D", "", phone)
        send_message(
            f"Call {first_name} — tap to dial:\n+1{phone_digits}",
            chat_id=chat_id,
        )
        add_note_to_contact(contact_id, "Lead Alert: Ben tapped CALL.")
        _mark_lead_responded(contact_id)
        log_event(
            "lead_alert",
            "call",
            "success",
            contact_id=contact_id,
            file=__file__,
            function="_handle_callback",
        )
        return


def _parse_iso_timestamp(value: str | None) -> datetime | None:
    if not value:
        return None
    normalized = value.replace("Z", "+00:00") if value.endswith("Z") else value
    parsed = datetime.fromisoformat(normalized)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed


def _format_last_activity(last_activity: str | None) -> str:
    parsed = _parse_iso_timestamp(str(last_activity or ""))
    if not parsed:
        return "no activity"
    return parsed.date().isoformat()


def _run_brief_for_contact(client_id: str, contact_id: str) -> str:
    log_event(
        "cos_agent",
        "run_brief",
        "start",
        contact_id=contact_id,
        file=__file__,
        function="_run_brief_for_contact",
    )
    try:
        result = run_brief(client_id, contact_id)
        log_event(
            "cos_agent",
            "run_brief",
            "success",
            contact_id=contact_id,
            file=__file__,
            function="_run_brief_for_contact",
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
            file=__file__,
            function="_run_brief_for_contact",
        )
        return BRIEF_ERROR_MSG


def _duplicate_merge_note(name: str, total_records: int) -> str:
    return (
        f"\n\nFound {total_records} records for {name}. "
        "Showing the most recent. Theresa can merge them in FUB."
    )


def _send_contact_disambiguation_prompt(
    chat_id: str, name: str, candidates: list[dict]
) -> None:
    buttons = []
    for candidate in candidates:
        contact_id = str(candidate.get("id", ""))
        stage = str(candidate.get("stage") or "Unknown")
        activity = _format_last_activity(candidate.get("lastActivity"))
        label = f"{candidate.get('name', name)} · {activity} · {stage}"
        if len(label) > 64:
            label = label[:61] + "..."
        buttons.append(
            [{"text": label, "callback_data": f"brief_pick:{contact_id}"}]
        )

    prompt = f"Found {len(candidates)} records for {name}. Which one?"
    send_inline_message(
        prompt,
        {"inline_keyboard": buttons},
        chat_id=chat_id,
    )


def _handle_disambiguation_result(
    client_id: str,
    chat_id: str,
    query: str,
    result: SearchContactsDisambiguationResult,
) -> str | None:
    primary = result["primary"]
    duplicates_found = result["duplicates_found"]
    contact_id = str(primary.get("id", ""))
    name = _person_display_name(primary) or query

    if result["disambiguation_required"]:
        candidates = [_contact_summary(primary), *duplicates_found]
        _send_contact_disambiguation_prompt(chat_id, name, candidates)
        log_event(
            "bot",
            "name_lookup",
            "success",
            detail=f"{name} disambiguation prompt sent",
            file=__file__,
            function="_handle_disambiguation_result",
        )
        return None

    log_event(
        "bot",
        "name_lookup",
        "success",
        detail=f"{name} → {contact_id} (auto-disambiguated)",
        file=__file__,
        function="_handle_disambiguation_result",
    )
    log_event(
        "bot",
        "brief_requested",
        "start",
        contact_id=contact_id,
        file=__file__,
        function="_handle_disambiguation_result",
    )
    brief = _run_brief_for_contact(client_id, contact_id)
    if duplicates_found:
        total_records = 1 + len(duplicates_found)
        brief += _duplicate_merge_note(name, total_records)
    return brief


def _handle_message(client_id: str, text: str, chat_id: str) -> str | None:
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
            return _run_brief_for_contact(client_id, contact_id)
        except Exception as exc:
            log_event(
                "cos_agent",
                "run_brief",
                "failure",
                detail=str(exc),
                contact_id=contact_id,
                exc_info=exc,
                file=__file__,
                function="_handle_message",
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
        if isinstance(results, dict):
            return _handle_disambiguation_result(client_id, chat_id, query, results)
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
            return _run_brief_for_contact(client_id, contact_id)
        except Exception as exc:
            log_event(
                "cos_agent",
                "run_brief",
                "failure",
                detail=str(exc),
                contact_id=contact_id,
                exc_info=exc,
                file=__file__,
                function="_handle_message",
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

    offset = _drain_stale_updates()
    configured_chat_id = str(CHAT_ID)

    try:
        while True:
            updates = get_updates(offset=offset, timeout=POLL_TIMEOUT)
            for update in updates:
                update_id = update.get("update_id", 0)
                offset = update_id + 1

                message = extract_message(update)
                if message:
                    chat_id = message["chat_id"]
                    if chat_id == configured_chat_id:
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

                        reply = _handle_message(client_id, text, chat_id=chat_id)
                        if reply is not None:
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

                callback_query = update.get("callback_query")
                if callback_query:
                    callback_query_id = callback_query.get("id", "")
                    _answer_callback_query(callback_query_id)
                    callback_chat_id = str(
                        callback_query.get("message", {})
                        .get("chat", {})
                        .get("id", "")
                    )
                    if callback_chat_id == configured_chat_id:
                        _handle_callback(client_id, callback_query)
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
