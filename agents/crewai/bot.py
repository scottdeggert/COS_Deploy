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
from tools.appointments import (
    format_appointment_summary,
    get_contact_id_from_appointment,
    get_upcoming_appointments,
)
from tools.fub import (
    SearchContactsDisambiguationResult,
    _contact_summary,
    _person_display_name,
    get_contact_by_id,
    search_contacts,
)
from tools.draft_communication import draft_communication
from tools.fub_activity import get_contact_context
from tools.fub_write import add_note_to_contact, enroll_in_action_plan
from tools.health import run_health_check
from tools.hot_leads import get_hot_leads_going_cold
from tools.intent_router import ConversationBuffer, classify_intent
from tools.logger import log_event
from tools.scheduler import SimpleScheduler
from tools.telegram import (
    BOT_TOKEN,
    CHAT_ID,
    MONITOR_CHAT_ID,
    TELEGRAM_API,
    extract_message,
    get_updates,
    send_inline_message,
    send_long_message,
    send_message,
    send_monitor_copy,
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
STATUS_PATTERN = re.compile(r"^(?:/)?status(?:\s+(\d+))?$", re.IGNORECASE)
POLL_TIMEOUT = 30
BRIEF_ERROR_MSG = (
    "I ran into a problem pulling that brief. Check FUB directly: "
    "https://app.followupboss.com"
)
UNKNOWN_MSG = "I didn't catch that. Try asking me to draft an email, pull up a contact, or check your hot leads."
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
            send_long_message(result, chat_id=chat_id)
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


def _get_status_log(lines: int = 50) -> str:
    log_path = ROOT / "logs" / "cos_agent.log"
    if not log_path.exists():
        return "No log file found."
    try:
        with log_path.open(encoding="utf-8") as f:
            all_lines = f.readlines()
        tail = all_lines[-lines:]
        return "".join(tail)[:3800]  # Telegram message limit is 4096
    except Exception as exc:
        return f"Could not read log: {exc}"


def _handle_hot_leads_list(client_id: str, chat_id: str) -> str:
    cold = get_hot_leads_going_cold(days_silent=14)
    if not cold:
        return "No Hot 90 Days leads going cold right now. Pipeline looks healthy."

    lines = [f"Here are your {len(cold)} hot leads going cold:\n"]
    for lead in cold:
        lines.append(
            f"• {lead['name']} — {lead['stage']} — "
            f"last activity {lead['last_activity']} ({lead['days_silent']} days ago)"
        )

    lines.append(
        "\nWant me to draft outreach for one or all of these? "
        "Reply with a name or \"draft all\"."
    )
    return "\n".join(lines)


def _handle_generative_request(
    client_id: str, request: str, entity: str | None, comm_type: str, chat_id: str
) -> str:
    """Single handler for all generative writing requests.
    Ben's voice is always on. FUB context loaded when a contact name is provided."""
    contact_context = None

    if entity:
        try:
            results = search_contacts(entity, limit=3)
            if isinstance(results, dict):
                primary = results.get("primary")
                if primary:
                    contact_context = get_contact_context(str(primary.get("id", "")))
            elif results and len(results) == 1:
                contact_context = get_contact_context(str(results[0].get("id", "")))
            elif results and len(results) > 1:
                names = ", ".join(
                    f"{p.get('firstName', '')} {p.get('lastName', '')}".strip()
                    for p in results
                )
                send_message(
                    f"Found {len(results)} contacts matching {entity}: {names}. "
                    f"Drafting without contact context — use the full name to be specific.",
                    chat_id=chat_id,
                )
        except Exception as exc:
            log_event(
                "bot", "generative_lookup", "failure",
                detail=str(exc), exc_info=exc,
                file=__file__, function="_handle_generative_request",
            )

    return draft_communication(request, comm_type=comm_type, contact_context=contact_context)


def _handle_message(client_id: str, text: str, chat_id: str) -> str | None:
    # Always allow explicit operator commands through without classification
    if STATUS_PATTERN.match(text.strip()):
        lines = int(STATUS_PATTERN.match(text.strip()).group(1) or 50)
        return _get_status_log(lines)

    # Classify intent via Haiku with conversation context
    intent_result = classify_intent(text, _conversation_buffer)
    intent = intent_result.get("intent", "unknown")
    entity = intent_result.get("entity")

    if intent == "greeting":
        return GREETING_REPLY

    if intent == "identity_query":
        return IDENTITY_REPLY

    if intent == "help_request":
        return HELP_REPLY

    if intent == "brief_request":
        # entity is a name or numeric ID
        if entity and entity.isdigit():
            contact_id = entity
            log_event("bot", "brief_requested", "start",
                      contact_id=contact_id, file=__file__, function="_handle_message")
            return _run_brief_for_contact(client_id, contact_id)

        if entity:
            query = entity.strip()
            log_event("bot", "name_lookup", "start",
                      detail=query, file=__file__, function="_handle_message")
            results = search_contacts(query, limit=5)
            if isinstance(results, dict):
                return _handle_disambiguation_result(client_id, chat_id, query, results)
            if not results:
                return f"No contact found for '{query}'. Try a contact ID."
            if len(results) > 1:
                lines = [f"Found {len(results)} matches. Which one?"]
                for p in results:
                    name = f"{p.get('firstName', '')} {p.get('lastName', '')}".strip()
                    cid = str(p.get("id", ""))
                    lines.append(f"  brief {cid} — {name}")
                return "\n".join(lines)
            contact = results[0]
            contact_id = str(contact.get("id", ""))
            return _run_brief_for_contact(client_id, contact_id)

        return "Who would you like a brief on? Send me a name or contact ID."

    if intent in ("hot_leads", "hot_leads_list"):
        return _handle_hot_leads_list(client_id, chat_id)

    if intent in ("draft_outreach", "draft_communication", "generative"):
        comm_type = intent_result.get("type") or "email"
        return _handle_generative_request(
            client_id, text, entity, comm_type, chat_id
        )

    if intent == "status_check":
        return _get_status_log(50)

    # Fallback for unknown
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


_briefed_appointment_ids: set[int] = set()
_conversation_buffer = ConversationBuffer()


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
    send_operator_alert("CoS Agent is online — polling started.")
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

    def _job_morning_digest() -> None:
        """8:30am daily digest — greeting, today's appointments, hot leads check."""
        import random
        from datetime import timedelta

        now_pacific = datetime.now(tz=timezone.utc) + timedelta(hours=-7)
        day_name = now_pacific.strftime("%A")

        greetings = [
            f"Good morning, Ben.",
            f"Morning, Ben. Here's your day.",
            f"Buenos días, Ben.",
            f"Happy {day_name}, Ben.",
            f"Good morning, Ben. Another day in Lamorinda.",
        ]
        greeting = random.choice(greetings)

        lines = [greeting, ""]

        # Today's appointments
        appointments = get_upcoming_appointments(hours_ahead=18)
        if appointments:
            lines.append("Today's appointments:")
            for appt in appointments:
                summary = format_appointment_summary(appt)
                contact_id = get_contact_id_from_appointment(appt)
                if contact_id:
                    summary += f"\n  Send: brief {contact_id} for a full brief"
                lines.append(f"• {summary}")
        else:
            lines.append("No appointments in FUB today.")

        lines.append("")

        # Hot leads going cold
        try:
            cold = get_hot_leads_going_cold(days_silent=14)
            if cold:
                lines.append(
                    f"One thing worth knowing: you have {len(cold)} lead{'s' if len(cold) != 1 else ''} "
                    f"tagged Hot 90 Days with no activity in the last 14 days. "
                    f"They're warm and going cold. Reply \"hot leads\" to see the list."
                )
            else:
                lines.append("Your Hot 90 Days leads are all active. Nothing going cold.")
        except Exception as exc:
            log_event(
                "scheduler",
                "morning_digest_hot_leads",
                "failure",
                detail=str(exc),
                exc_info=exc,
                file=__file__,
                function="_job_morning_digest",
            )

        send_long_message("\n".join(lines), chat_id=configured_chat_id)

    def _job_pre_appointment_check() -> None:
        """Runs every 15 minutes. Fires a brief 2 hours before any appointment
        that has a linked contact and hasn't been briefed yet this session."""
        appointments = get_upcoming_appointments(hours_ahead=2)
        now = datetime.now(tz=timezone.utc)

        for appt in appointments:
            start_str = appt.get("start", "")
            try:
                start = datetime.fromisoformat(start_str.replace("Z", "+00:00"))
            except ValueError:
                continue

            minutes_until = (start - now).total_seconds() / 60
            if minutes_until > 120 or minutes_until < 90:
                continue  # Only fire in the 90-120 minute window

            appt_id = appt.get("id")
            if appt_id in _briefed_appointment_ids:
                continue
            _briefed_appointment_ids.add(appt_id)

            contact_id = get_contact_id_from_appointment(appt)
            if not contact_id:
                title = appt.get("title", "your next appointment")
                send_message(
                    f"Heads up — {title} starts in about 2 hours. "
                    f"No contact linked in FUB so I can't pull a brief automatically. "
                    f"Send me a name or ID if you want one.",
                    chat_id=configured_chat_id,
                )
                continue

            brief = _run_brief_for_contact(client_id, contact_id)
            title = appt.get("title", "upcoming appointment")
            send_long_message(
                f"2-hour brief for {title}:\n\n{brief}",
                chat_id=configured_chat_id,
            )

    scheduler = SimpleScheduler()
    scheduler.add_daily(hour=8, minute=30, job=_job_morning_digest, name="morning_digest")
    scheduler.add_interval(seconds=900, job=_job_pre_appointment_check, name="pre_appointment_check")
    scheduler.start()

    try:
        while True:
            updates = get_updates(offset=offset, timeout=POLL_TIMEOUT)
            for update in updates:
                update_id = update.get("update_id", 0)
                offset = update_id + 1

                message = extract_message(update)
                if message:
                    chat_id = message["chat_id"]
                    monitor_chat_id = str(MONITOR_CHAT_ID)
                    if chat_id == configured_chat_id or (
                        monitor_chat_id and chat_id == monitor_chat_id
                    ):
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

                        send_monitor_copy(f"[BEN → CoS] {text}")
                        _conversation_buffer.add("user", text)
                        reply = _handle_message(client_id, text, chat_id=chat_id)
                        if reply is not None:
                            send_long_message(reply, chat_id=chat_id)
                            _conversation_buffer.add("assistant", reply)
                            log_event(
                                "telegram",
                                "outbound",
                                "success",
                                detail=reply[:200],
                                contact_id="",
                                file=__file__,
                                function="run_bot",
                            )
                            send_monitor_copy(f"[BEN] {text}\n[CoS] {reply[:500]}")

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
        send_operator_alert("CoS Agent going offline.")
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
