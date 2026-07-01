"""Lead alert callback handler -- FUB webhook inline keyboard actions."""

from __future__ import annotations

import json
import re
from pathlib import Path

from app.config import CLIENT_ID, LOGS_DIR
from app.schemas import HandlerResult, InboundCallback
from tools.fub import get_contact_by_id
from tools.fub_write import add_note_to_contact, enroll_in_action_plan
from tools.logger import log_event
from tools.telegram import send_operator_alert

FALLBACK_MESSAGE = "Something went wrong processing that action. Check FUB directly."

LEAD_ALERT_STATE_PATH = LOGS_DIR / "lead_alert_state.json"


def _load_lead_alert_state() -> dict:
    if not LEAD_ALERT_STATE_PATH.exists():
        return {"drafts": {}, "contacts": {}, "responded": []}
    try:
        with LEAD_ALERT_STATE_PATH.open(encoding="utf-8") as handle:
            return json.load(handle)
    except (json.JSONDecodeError, OSError):
        return {"drafts": {}, "contacts": {}, "responded": []}


def _save_lead_alert_state(state: dict) -> None:
    LEAD_ALERT_STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    with LEAD_ALERT_STATE_PATH.open("w", encoding="utf-8") as handle:
        json.dump(state, handle)


def _get_lead_contact(contact_id: str) -> dict:
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


def handle_callback(callback: InboundCallback) -> HandlerResult:
    """Route inline keyboard actions for lead alert cards."""
    log_event(
        "lead_alert", "handle_callback", "start",
        detail=callback.data,
        file=__file__, function="handle_callback",
    )
    data = callback.data

    if not data or ":" not in data:
        return HandlerResult(
            success=False,
            telegram_output="",
            error_details="Invalid callback data format",
        )

    action, contact_id = data.split(":", 1)
    fub_writes = 0

    try:
        contact_info = _get_lead_contact(contact_id)
        first_name = contact_info.get("first_name", "")
        action_plan_id = contact_info.get("action_plan_id")

        if action == "approve":
            if action_plan_id:
                enroll_in_action_plan(contact_id, int(action_plan_id))
                fub_writes += 1
                add_note_to_contact(
                    contact_id,
                    "Lead Alert: Ben approved. Action plan enrolled by CoS agent.",
                )
                fub_writes += 1
                _mark_lead_responded(contact_id)
                log_event(
                    "lead_alert", "approve", "success",
                    contact_id=contact_id,
                    file=__file__, function="handle_callback",
                )
                return HandlerResult(
                    success=True,
                    telegram_output=f"Sequence started for {first_name}. FUB will send Day 1 email.",
                    fub_writes=fub_writes,
                )
            else:
                add_note_to_contact(
                    contact_id,
                    "Lead Alert: Ben approved but no action plan mapped for source.",
                )
                fub_writes += 1
                log_event(
                    "lead_alert", "approve", "success",
                    contact_id=contact_id,
                    file=__file__, function="handle_callback",
                )
                return HandlerResult(
                    success=True,
                    telegram_output="No sequence mapped for this lead source. Check FUB manually.",
                    fub_writes=fub_writes,
                )

        if action == "brief_pick":
            from handlers.brief import run_brief_for_contact
            brief_text = run_brief_for_contact(CLIENT_ID, contact_id)
            log_event(
                "bot", "brief_pick", "success",
                contact_id=contact_id,
                file=__file__, function="handle_callback",
            )
            return HandlerResult(success=True, telegram_output=brief_text)

        if action == "call":
            phone = contact_info.get("phone", "")
            phone_digits = re.sub(r"\D", "", phone)
            add_note_to_contact(contact_id, "Lead Alert: Ben tapped CALL.")
            fub_writes += 1
            _mark_lead_responded(contact_id)
            log_event(
                "lead_alert", "call", "success",
                contact_id=contact_id,
                file=__file__, function="handle_callback",
            )
            return HandlerResult(
                success=True,
                telegram_output=f"Call {first_name} -- tap to dial:\n+1{phone_digits}",
                fub_writes=fub_writes,
            )

        return HandlerResult(
            success=False,
            telegram_output="",
            error_details=f"Unknown callback action: {action}",
        )
    except Exception as exc:
        log_event(
            "lead_alert", "handle_callback", "failure",
            detail=str(exc), exc_info=exc,
            file=__file__, function="handle_callback",
        )
        send_operator_alert(f"Lead alert callback failed: {exc}")
        return HandlerResult(
            success=False,
            telegram_output=FALLBACK_MESSAGE,
            error_details=str(exc),
        )
