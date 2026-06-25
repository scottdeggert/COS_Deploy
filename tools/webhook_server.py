"""FastAPI webhook gateway for FUB lead alerts."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import sys
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests
import uvicorn
from dotenv import load_dotenv
from fastapi import BackgroundTasks, FastAPI, Header, HTTPException, Request
from fastapi.responses import JSONResponse

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

load_dotenv(ROOT / ".env")

from tools.fub import get_contact_by_id, get_recent_activity
from tools.fub_write import add_note_to_contact, add_tags_to_contact
from tools.logger import log_event
from tools.telegram import BOT_TOKEN, CHAT_ID, TELEGRAM_API

ASSIGNED_TO_NAME = "Ben Olsen"
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
DRAFT_MODEL = "anthropic/claude-sonnet-4-6"
FALLBACK_SECONDS = 30 * 60
LAST_ACTIVITY_WINDOW_SECONDS = 120
NOTIFY_DEDUP_SECONDS = 300
LEAD_ALERT_STATE_PATH = ROOT / "logs" / "lead_alert_state.json"

app = FastAPI()
_fallback_timers: dict[str, threading.Timer] = {}
_state_lock = threading.Lock()
_in_flight: set[str] = set()
_in_flight_lock = threading.Lock()


def _load_state() -> dict[str, Any]:
    if not LEAD_ALERT_STATE_PATH.exists():
        return {"drafts": {}, "contacts": {}, "responded": [], "notified": {}}
    try:
        with LEAD_ALERT_STATE_PATH.open(encoding="utf-8") as handle:
            return json.load(handle)
    except (json.JSONDecodeError, OSError):
        return {"drafts": {}, "contacts": {}, "responded": [], "notified": {}}


def _save_state(state: dict[str, Any]) -> None:
    LEAD_ALERT_STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    with LEAD_ALERT_STATE_PATH.open("w", encoding="utf-8") as handle:
        json.dump(state, handle)


def _mark_responded(contact_id: str) -> None:
    with _state_lock:
        state = _load_state()
        responded = state.setdefault("responded", [])
        if contact_id not in responded:
            responded.append(contact_id)
        _save_state(state)


def _get_action_plan_id(source: str) -> int | None:
    """Map lead source string to FUB action plan ID."""
    source_lower = source.lower()
    if any(k in source_lower for k in ("finaloffer", "final-offer", "final_offer")):
        return 53
    if any(k in source_lower for k in ("offmarket", "off-market", "off_market")):
        return 55
    if "quiet" in source_lower:
        return 51
    if any(k in source_lower for k in ("seniors", "senior")):
        return 57
    if "relaunch" in source_lower:
        return 54
    if any(k in source_lower for k in ("mcc", "moraga")):
        return 50
    if "homelight" in source_lower:
        return 49
    if "brightflip" in source_lower:
        return 52
    if any(k in source_lower for k in ("buybefore", "buy-before")):
        return 56
    if "expired" in source_lower:
        return 58
    return None


def _store_lead_alert(
    contact_id: str,
    draft_email: str,
    draft_subject: str,
    contact: dict,
    action_plan_id: int | None = None,
) -> None:
    with _state_lock:
        state = _load_state()
        state.setdefault("drafts", {})[contact_id] = {
            "draft_email": draft_email,
            "draft_subject": draft_subject,
        }
        state.setdefault("contacts", {})[contact_id] = {
            "first_name": contact.get("firstName", ""),
            "last_name": contact.get("lastName", ""),
            "phone": _extract_phone(contact),
            "source": contact.get("source", ""),
            "action_plan_id": action_plan_id,
        }
        _save_state(state)


def _parse_iso_timestamp(value: str) -> datetime:
    normalized = value.replace("Z", "+00:00") if value.endswith("Z") else value
    parsed = datetime.fromisoformat(normalized)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed


def _is_recently_notified(contact_id: str) -> bool:
    with _state_lock:
        state = _load_state()
        notified_at = state.get("notified", {}).get(contact_id)
    if not notified_at:
        return False
    elapsed = datetime.now(timezone.utc) - _parse_iso_timestamp(notified_at)
    return elapsed.total_seconds() < NOTIFY_DEDUP_SECONDS


def _mark_notified(contact_id: str) -> None:
    with _state_lock:
        state = _load_state()
        state.setdefault("notified", {})[contact_id] = datetime.now(timezone.utc).isoformat()
        _save_state(state)


def _last_activity_is_fresh(contact: dict) -> bool:
    last_activity = contact.get("lastActivity")
    if not last_activity:
        return False
    elapsed = datetime.now(timezone.utc) - _parse_iso_timestamp(str(last_activity))
    return elapsed.total_seconds() <= LAST_ACTIVITY_WINDOW_SECONDS


# FUB_WEBHOOK_SECRET must be set to the X-System-Key value used when
# registering the FUB webhook, not a separate secret. The signature
# algorithm is HMAC-SHA256(base64_encode(raw_body), x_system_key).
def _verify_signature(raw_body: bytes, signature: str | None) -> bool:
    secret = os.environ.get("FUB_WEBHOOK_SECRET", "")
    if not secret or not signature:
        return False
    expected = hmac.new(
        secret.encode(),
        base64.b64encode(raw_body),
        hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(expected, signature)


def _assigned_to_name(person: dict) -> str | None:
    assigned = person.get("assignedTo")
    if assigned is None:
        return None
    if isinstance(assigned, dict):
        name = assigned.get("name")
        return str(name) if name is not None else None
    if isinstance(assigned, str):
        return assigned
    return None


def _extract_phone(contact: dict) -> str:
    phones = contact.get("phones") or []
    if isinstance(phones, list) and phones:
        value = phones[0].get("value") if isinstance(phones[0], dict) else phones[0]
        return str(value or "")
    return str(contact.get("phone", "") or "")


_SKIP_FORM_LABELS = frozenset({
    "FIRST NAME",
    "LAST NAME",
    "PHONE NUMBER",
    "EMAIL ADDRESS",
})


def _parse_form_notes(raw: str) -> str:
    pairs: list[str] = []
    for part in raw.split(" | "):
        part = part.strip()
        if not part or "unknown field" in part.lower():
            continue
        if ": " not in part:
            continue
        label, value = part.split(": ", 1)
        label = label.strip()
        value = value.strip()
        if label.upper() in _SKIP_FORM_LABELS:
            continue
        label = label.replace("(OPTIONAL)", "").strip()
        if value:
            pairs.append(f"{label}: {value}")
    return "\n".join(pairs)


MCC_ESTIMATE_MARKER = "ESTIMATE REQUEST - MCC Home Estimator"
EMAIL_SIGNOFF = "Ben Olsen\nBrightWork Realty Advocates"


def _is_mcc_submission_message(message: str) -> bool:
    stripped = message.strip()
    if MCC_ESTIMATE_MARKER in stripped:
        return True
    return stripped.lower().startswith("via: mcc")


def _extract_mcc_form_notes(events: list[dict]) -> str:
    """Return the verbatim MCC estimator submission block from the event timeline."""
    sorted_events = sorted(
        events,
        key=lambda event: event.get("created", ""),
        reverse=True,
    )
    for event in sorted_events:
        message = str(event.get("message", "")).strip()
        if _is_mcc_submission_message(message):
            return message
    return ""


def _extract_form_notes(events: list[dict]) -> str:
    type_substrings = ("inquiry", "registration", "note", "form", "submission", "comment")
    notes: list[str] = []
    for event in events:
        event_type = str(event.get("type", "")).lower()
        if not any(sub in event_type for sub in type_substrings):
            continue
        for key in ("message", "description", "body", "note"):
            value = event.get(key)
            if value and str(value).strip():
                parsed = _parse_form_notes(str(value).strip())
                if parsed:
                    notes.append(parsed)
        data = event.get("data") or {}
        if isinstance(data, dict):
            for key in ("message", "body"):
                value = data.get(key)
                if value and str(value).strip():
                    parsed = _parse_form_notes(str(value).strip())
                    if parsed:
                        notes.append(parsed)
    return "\n".join(notes)


def _resolve_source(contact: dict, events: list[dict]) -> str:
    """Resolve lead source from contact field or event timeline."""
    contact_source = str(contact.get("source") or "").strip()
    if contact_source and contact_source.lower() != "<unspecified>":
        return contact_source
    return _get_source_from_events(events, fallback="Unknown")


def _tags_from_mcc_event_note(event_note: str, source: str) -> list[str]:
    """Map MCC estimator flags and timeline to FUB tags."""
    tags: list[str] = []
    if event_note:
        upper = event_note.upper()
        if "BUY BEFORE SELL CANDIDATE" in upper:
            tags.append("Buy Before Sell")
        if "PRE-SALE RENO INTEREST" in upper:
            tags.append("Pre-Sale Reno")
        if "OFF-MARKET CANDIDATE" in upper:
            tags.append("off-market-lead")
        if "6-12MO" in upper:
            tags.append("Warm 6-12 Months")
    if source.strip().lower() == "mcc home estimator":
        tags.append("MCC Estimator")
    return tags


def _apply_mcc_tags(contact_id: str, event_note: str, source: str) -> None:
    tags = _tags_from_mcc_event_note(event_note, source)
    if not tags:
        return
    try:
        add_tags_to_contact(contact_id, tags)
        log_event(
            "lead_alert",
            "apply_mcc_tags",
            "success",
            contact_id=contact_id,
            file=__file__,
            function="_apply_mcc_tags",
        )
    except Exception as exc:
        log_event(
            "lead_alert",
            "apply_mcc_tags",
            "failure",
            detail=str(exc),
            contact_id=contact_id,
            exc_info=exc,
            file=__file__,
            function="_apply_mcc_tags",
        )


def _normalize_email_signoff(draft_email: str) -> str:
    """Ensure the draft ends with the fixed Ben sign-off, no closing phrase."""
    text = draft_email.strip()
    body = text
    for marker in ("Ben Olsen", "BrightWork Realty Advocates", "BrightWork"):
        idx = body.rfind(marker)
        if idx != -1:
            body = body[:idx].strip()
            break

    closing_prefixes = (
        "talk soon",
        "best regards",
        "warm regards",
        "kind regards",
        "thanks",
        "thank you",
        "sincerely",
        "cheers",
        "best",
        "regards",
    )
    lines = body.splitlines()
    while lines:
        candidate = lines[-1].strip().lower().rstrip(",")
        if any(candidate == prefix or candidate.startswith(f"{prefix},") for prefix in closing_prefixes):
            lines.pop()
            continue
        break

    body = "\n".join(lines).strip()
    if body:
        return f"{body}\n\n{EMAIL_SIGNOFF}"
    return EMAIL_SIGNOFF


def _openrouter_completion(
    api_key: str,
    system_prompt: str,
    user_prompt: str,
    max_tokens: int,
) -> str:
    response = requests.post(
        OPENROUTER_URL,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        json={
            "model": DRAFT_MODEL,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "max_tokens": max_tokens,
        },
        timeout=30,
    )
    response.raise_for_status()
    payload = response.json()
    content = payload["choices"][0]["message"]["content"]
    return content.strip().strip('"').strip("'")


def _draft_first_touch_email(
    first_name: str,
    source: str,
    form_notes: str,
    source_context: str,
) -> tuple[str, str]:
    api_key = os.environ.get("OPENROUTER_API_KEY", "")
    if not api_key:
        raise ValueError("OPENROUTER_API_KEY environment variable is required")

    body_system_prompt = (
        "You are drafting a first-touch email for Ben Olsen, a real estate agent "
        "in the Lamorinda area of the East Bay. Ben's voice is warm, direct, and personal. "
        "Write 3-4 sentences. No scheduling links. No em dashes. "
        "No filler phrases like 'I hope this finds you well.' "
        "End with exactly these two lines and nothing after them:\n"
        "Ben Olsen\n"
        "BrightWork Realty Advocates\n"
        "Do not include any closing phrase before the name "
        "(no 'Talk soon,' 'Best,' 'Thanks,' or similar). "
        "Return only the email body, no subject line, no preamble. "
        f"Context about this lead: {source_context}"
    )
    user_parts = [f"Contact name: {first_name}", f"Lead source: {source}"]
    if form_notes:
        user_parts.append(f"Form notes: {form_notes}")
    user_prompt = "\n".join(user_parts)

    draft_email = _normalize_email_signoff(
        _openrouter_completion(
            api_key,
            body_system_prompt,
            user_prompt,
            max_tokens=300,
        )
    )

    subject_system_prompt = (
        "Write a short email subject line, 6 words or fewer, "
        "no punctuation, for a real estate agent following up on a lead. "
        "Return only the subject line itself. No explanation, no formatting, "
        "no bold text, no preamble."
    )
    draft_subject = _openrouter_completion(
        api_key,
        subject_system_prompt,
        user_prompt,
        max_tokens=30,
    )

    return draft_email, draft_subject


def send_lead_alert_card(
    contact: dict,
    draft_email: str,
    form_notes: str = "",
    source: str = "",
) -> bool:
    """Send Telegram lead alert card with inline keyboard."""
    contact_id = str(contact.get("id", ""))
    first_name = contact.get("firstName", "")
    last_name = contact.get("lastName", "")
    phone = _extract_phone(contact)
    resolved_source = source or contact.get("source") or "Unknown"
    notes_display = form_notes.strip() if form_notes.strip() else "None"

    text = (
        f"🔔 New lead — {resolved_source}\n"
        f"{first_name} {last_name}\n"
        f"📞 {phone}\n"
        f"🌐 via {resolved_source}\n"
        f"\n"
        f"Form notes: {notes_display}\n\n"
        f"Draft email below ↓"
    )
    reply_markup = {
        "inline_keyboard": [
            [
                {"text": "START SEQUENCE", "callback_data": f"approve:{contact_id}"},
                {"text": f"CALL {first_name}", "callback_data": f"call:{contact_id}"},
            ]
        ]
    }

    url = f"{TELEGRAM_API}/bot{BOT_TOKEN}/sendMessage"
    card_payload = {
        "chat_id": CHAT_ID,
        "text": text,
        "reply_markup": reply_markup,
    }
    draft_payload = {
        "chat_id": CHAT_ID,
        "text": draft_email,
    }
    try:
        resp = requests.post(url, json=card_payload, timeout=10)
        if not resp.ok:
            print(f"sendMessage failed: {resp.status_code}", file=sys.stderr)
            return False
        draft_resp = requests.post(url, json=draft_payload, timeout=10)
        if not draft_resp.ok:
            print(f"sendMessage (draft) failed: {draft_resp.status_code}", file=sys.stderr)
            return False
        return True
    except requests.RequestException as exc:
        print(f"sendMessage error: {exc}", file=sys.stderr)
        return False


def log_fallback_note(contact_id: str) -> None:
    """Write fallback note if Ben has not responded to the lead alert."""
    with _state_lock:
        state = _load_state()
        if contact_id in state.get("responded", []):
            return

    log_event(
        "lead_alert",
        "fallback",
        "start",
        contact_id=contact_id,
        file=__file__,
        function="log_fallback_note",
    )
    try:
        add_note_to_contact(
            contact_id,
            "Lead Alert draft unanswered — fallback sequence eligible.",
        )
        log_event(
            "lead_alert",
            "fallback",
            "success",
            contact_id=contact_id,
            file=__file__,
            function="log_fallback_note",
        )
    except Exception as exc:
        log_event(
            "lead_alert",
            "fallback",
            "failure",
            detail=str(exc),
            contact_id=contact_id,
            exc_info=exc,
            file=__file__,
            function="log_fallback_note",
        )


def _schedule_fallback(contact_id: str) -> None:
    existing = _fallback_timers.pop(contact_id, None)
    if existing is not None:
        existing.cancel()

    timer = threading.Timer(FALLBACK_SECONDS, log_fallback_note, args=(contact_id,))
    timer.daemon = True
    _fallback_timers[contact_id] = timer
    timer.start()


def _get_source_from_events(events: list[dict], fallback: str) -> str:
    """Return source from the most recent event with a meaningful source value."""
    sorted_events = sorted(
        events,
        key=lambda e: e.get("created", ""),
        reverse=True,
    )
    for event in sorted_events:
        source = str(event.get("source", "")).strip()
        if source and source.lower() not in ("<unspecified>", "unknown", ""):
            return source
        message = str(event.get("message", "")).strip()
        for line in message.splitlines():
            if line.lower().startswith("via:"):
                url = line.split(":", 1)[1].strip()
                if url:
                    return url
    return fallback


def handle_new_lead(contact_id: str) -> None:
    """Fetch contact, draft email, send Telegram card, schedule fallback."""
    with _in_flight_lock:
        if contact_id in _in_flight:
            return
        _in_flight.add(contact_id)
    try:
        log_event(
            "lead_alert",
            "handle_new_lead",
            "start",
            contact_id=contact_id,
            file=__file__,
            function="handle_new_lead",
        )
        if _is_recently_notified(contact_id):
            log_event(
                "lead_alert",
                "handle_new_lead",
                "fallback",
                detail="duplicate notification suppressed",
                contact_id=contact_id,
                file=__file__,
                function="handle_new_lead",
            )
            return

        contact = get_contact_by_id(contact_id)
        if _assigned_to_name(contact) != ASSIGNED_TO_NAME:
            log_event(
                "lead_alert",
                "handle_new_lead",
                "fallback",
                detail="not assigned to Ben Olsen",
                contact_id=contact_id,
                file=__file__,
                function="handle_new_lead",
            )
            return

        first_name = contact.get("firstName", "")
        events = get_recent_activity(contact_id, limit=25)
        source = _resolve_source(contact, events)
        source_key = source.lower()
        if "finaloffer" in source_key:
            source_context = (
                "This lead is interested in selling their home via the Final Offer program. "
                "They provided their property address."
            )
        elif "offmarket" in source_key:
            source_context = (
                "This lead is interested in off-market property listings as a buyer."
            )
        elif "quiet" in source_key:
            source_context = (
                "This lead wants to sell their home quietly without a public listing."
            )
        elif "seniors" in source_key:
            source_context = "This lead is exploring senior real estate planning."
        elif "relaunch" in source_key:
            source_context = (
                "This lead has an expired listing and wants to relaunch their home sale."
            )
        elif "mcc" in source_key:
            source_context = (
                "This lead is interested in Moraga Country Club area properties."
            )
        else:
            source_context = "This lead submitted an inquiry form."
        mcc_event_note = _extract_mcc_form_notes(events)
        form_notes = mcc_event_note or _extract_form_notes(events)
        _apply_mcc_tags(contact_id, mcc_event_note, source)
        draft_email, draft_subject = _draft_first_touch_email(
            first_name, source, form_notes, source_context
        )
        action_plan_id = _get_action_plan_id(source)
        contact_for_state = {**contact, "source": source}
        _store_lead_alert(
            contact_id, draft_email, draft_subject, contact_for_state, action_plan_id
        )
        _mark_notified(contact_id)

        if not send_lead_alert_card(contact, draft_email, form_notes, source=source):
            log_event(
                "lead_alert",
                "handle_new_lead",
                "failure",
                detail="telegram send failed",
                contact_id=contact_id,
                file=__file__,
                function="handle_new_lead",
            )
            return

        _schedule_fallback(contact_id)
        log_event(
            "lead_alert",
            "handle_new_lead",
            "success",
            contact_id=contact_id,
            file=__file__,
            function="handle_new_lead",
        )
    except Exception as exc:
        log_event(
            "lead_alert",
            "handle_new_lead",
            "failure",
            detail=str(exc),
            contact_id=contact_id,
            exc_info=exc,
            file=__file__,
            function="handle_new_lead",
        )
    finally:
        with _in_flight_lock:
            _in_flight.discard(contact_id)


def _process_fub_event(payload: dict) -> None:
    event = payload.get("event")
    resource_ids = payload.get("resourceIds") or []

    if event == "peopleCreated":
        for raw_id in resource_ids:
            handle_new_lead(str(raw_id))
        return

    if event == "peopleUpdated":
        for raw_id in resource_ids:
            contact_id = str(raw_id)
            try:
                contact = get_contact_by_id(contact_id)
            except Exception:
                continue
            if not _last_activity_is_fresh(contact):
                continue
            handle_new_lead(contact_id)
        return


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "webhook"}


@app.post("/fub/webhook")
async def fub_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    x_fub_signature: str | None = Header(default=None, alias="X-FUB-Signature"),
    fub_signature: str | None = Header(default=None, alias="FUB-Signature"),
) -> JSONResponse:
    raw_body = await request.body()
    signature = x_fub_signature or fub_signature
    if not _verify_signature(raw_body, signature):
        raise HTTPException(status_code=401, detail="Invalid signature")

    try:
        payload = json.loads(raw_body)
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=400, detail="Invalid JSON") from exc

    background_tasks.add_task(_process_fub_event, payload)
    return JSONResponse(status_code=200, content={"status": "accepted"})


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8766)
