"""FastAPI webhook gateway for FUB lead alerts."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import re
import sys
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urljoin

import requests
import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, RedirectResponse

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

load_dotenv(ROOT / ".env")

from app.config import (
    CLIENT_ID,
    CLIENTS_DIR,
    CMA_PDF_ARCHIVE_DIR,
    CMA_REDIRECT_BASE,
    FUB_X_SYSTEM_KEY,
    GOOGLE_CALENDAR_CREDENTIALS_PATH,
    LEAD_ALERT_PROCESSING_STALE_SECONDS,
    TELEGRAM_CHAT_ID,
)
from services.fub_client import fub_get
from services.google_calendar import build_authorization_url, exchange_authorization_code
from services.webhook_db import enqueue_event
from tools.analytics import capture
from tools.cma_registry import get_job, get_job_by_token, mark_failed, mark_ready, record_open
from tools.fub import get_contact_by_id, get_recent_activity
from tools.fub_write import (
    add_note_to_contact,
    add_tags_to_contact,
    update_custom_field,
)
from tools.logger import log_event
from tools.telegram import (
    BOT_TOKEN,
    CHAT_ID,
    TELEGRAM_API,
    send_inline_message,
    send_operator_alert,
)

ASSIGNED_TO_NAME = "Ben Olsen"
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
DRAFT_MODEL = "anthropic/claude-sonnet-4-6"
FALLBACK_SECONDS = 30 * 60
NOTIFY_DEDUP_SECONDS = 300
LEAD_ALERT_STATE_PATH = ROOT / "logs" / "lead_alert_state.json"
ACTIVITY_FEED_PATH = ROOT / "logs" / "activity_feed.json"
ACTIVITY_FEED_RETENTION_DAYS = 7
_LEAD_ALERT_CONFIG_PATH = CLIENTS_DIR / CLIENT_ID / "scheduler_config.json"

_DEFAULT_LEAD_ALERT_CONFIG = {
    "creation_date_threshold_days": 30,
    "last_activity_window_seconds": 120,
    "events_rate_limit_per_10s": 18,
}


def _load_lead_alert_config() -> dict[str, int]:
    if not _LEAD_ALERT_CONFIG_PATH.exists():
        return dict(_DEFAULT_LEAD_ALERT_CONFIG)
    try:
        with _LEAD_ALERT_CONFIG_PATH.open(encoding="utf-8") as handle:
            payload = json.load(handle)
        lead_alert = payload.get("lead_alert") or {}
        return {
            "creation_date_threshold_days": int(
                lead_alert.get(
                    "creation_date_threshold_days",
                    _DEFAULT_LEAD_ALERT_CONFIG["creation_date_threshold_days"],
                )
            ),
            "last_activity_window_seconds": int(
                lead_alert.get(
                    "last_activity_window_seconds",
                    _DEFAULT_LEAD_ALERT_CONFIG["last_activity_window_seconds"],
                )
            ),
            "events_rate_limit_per_10s": int(
                lead_alert.get(
                    "events_rate_limit_per_10s",
                    _DEFAULT_LEAD_ALERT_CONFIG["events_rate_limit_per_10s"],
                )
            ),
        }
    except (json.JSONDecodeError, OSError, TypeError, ValueError):
        return dict(_DEFAULT_LEAD_ALERT_CONFIG)


_LEAD_ALERT_CONFIG = _load_lead_alert_config()

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


def _lead_alert_draft_exists(contact_id: str) -> bool:
    with _state_lock:
        state = _load_state()
        return contact_id in state.get("drafts", {})


def _begin_lead_alert_processing(contact_id: str) -> bool:
    """Claim in-flight processing slot. False if another worker is active."""
    now = datetime.now(timezone.utc)
    with _state_lock:
        state = _load_state()
        processing = state.setdefault("processing", {})
        existing = processing.get(contact_id)
        if existing:
            try:
                started = _parse_iso_timestamp(str(existing))
                elapsed = (now - started).total_seconds()
            except (ValueError, TypeError):
                elapsed = LEAD_ALERT_PROCESSING_STALE_SECONDS
            if elapsed < LEAD_ALERT_PROCESSING_STALE_SECONDS:
                return False
        processing[contact_id] = now.isoformat()
        _save_state(state)
    return True


def _clear_lead_alert_processing(contact_id: str) -> None:
    with _state_lock:
        state = _load_state()
        processing = state.setdefault("processing", {})
        if contact_id in processing:
            processing.pop(contact_id, None)
            _save_state(state)


def _try_resend_stored_lead_alert(contact_id: str) -> bool:
    """Resend Telegram from stored draft after a crash between store and send."""
    with _state_lock:
        state = _load_state()
        draft = state.get("drafts", {}).get(contact_id)
        contact = state.get("contacts", {}).get(contact_id)
    if not draft or not contact:
        return False
    if _is_recently_notified(contact_id):
        return False

    card_contact = {
        "id": contact_id,
        "firstName": contact.get("first_name", ""),
        "lastName": contact.get("last_name", ""),
        "phone": contact.get("phone", ""),
        "source": contact.get("source", ""),
    }
    draft_email = str(draft.get("draft_email") or "")
    source = str(contact.get("source") or "Unknown")
    if not draft_email:
        return False

    if not send_lead_alert_card(card_contact, draft_email, form_notes="", source=source):
        return False

    _mark_notified(contact_id)
    _schedule_fallback(contact_id)
    log_event(
        "lead_alert",
        "handle_new_lead",
        "success",
        detail="resent alert from stored draft after reclaim",
        contact_id=contact_id,
        file=__file__,
        function="_try_resend_stored_lead_alert",
    )
    return True


def _last_activity_is_fresh(contact: dict) -> bool:
    last_activity = contact.get("lastActivity")
    if not last_activity:
        return False
    elapsed = datetime.now(timezone.utc) - _parse_iso_timestamp(str(last_activity))
    window_seconds = _LEAD_ALERT_CONFIG["last_activity_window_seconds"]
    return elapsed.total_seconds() <= window_seconds


def _contact_created_within_threshold(contact: dict) -> bool:
    created = contact.get("created")
    if not created:
        return False
    created_at = _parse_iso_timestamp(str(created))
    threshold_days = _LEAD_ALERT_CONFIG["creation_date_threshold_days"]
    age = datetime.now(timezone.utc) - created_at
    return age.days <= threshold_days


def _resource_type_from_event(event: str | None) -> str:
    if not event:
        return "unknown"
    if event.startswith("people"):
        return "people"
    if event.startswith("events"):
        return "events"
    if event.startswith("calls"):
        return "calls"
    if event.startswith("textMessages"):
        return "textMessages"
    return "unknown"


def _format_resource_ids(resource_ids: list[Any]) -> str:
    normalized = [str(raw_id) for raw_id in resource_ids]
    if len(normalized) <= 20:
        return ",".join(normalized)
    shown = ",".join(normalized[:20])
    return f"{shown},...+{len(normalized) - 20} more"


def _log_inbound_webhook(payload: dict[str, Any]) -> None:
    event = str(payload.get("event") or "unknown")
    resource_ids = payload.get("resourceIds") or []
    if not isinstance(resource_ids, list):
        resource_ids = []
    log_event(
        "webhook",
        "inbound",
        "start",
        detail=(
            f"event={event} resource_type={_resource_type_from_event(event)} "
            f"resource_count={len(resource_ids)} resource_ids={_format_resource_ids(resource_ids)}"
        ),
        file=__file__,
        function="_log_inbound_webhook",
    )


# FUB_X_SYSTEM_KEY (app/config.py) serves two roles: outbound X-System-Key
# header on all FUB API calls (via services/fub_client.py) and inbound
# webhook signature verification here. The signature algorithm is
# HMAC-SHA256(base64_encode(raw_body), x_system_key).
def _verify_signature(raw_body: bytes, signature: str | None) -> bool:
    secret = FUB_X_SYSTEM_KEY
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


def _fub_single_record(payload: dict, key: str) -> dict:
    nested = payload.get(key)
    if isinstance(nested, dict):
        return nested
    return payload


def _load_activity_feed() -> list[dict]:
    if not ACTIVITY_FEED_PATH.exists():
        return []
    try:
        with ACTIVITY_FEED_PATH.open(encoding="utf-8") as handle:
            data = json.load(handle)
        if isinstance(data, list):
            return data
        return []
    except (json.JSONDecodeError, OSError):
        return []


def _trim_activity_feed(entries: list[dict]) -> list[dict]:
    cutoff = datetime.now(timezone.utc) - timedelta(days=ACTIVITY_FEED_RETENTION_DAYS)
    trimmed: list[dict] = []
    for entry in entries:
        timestamp = entry.get("timestamp")
        if not timestamp:
            continue
        try:
            parsed = _parse_iso_timestamp(str(timestamp))
        except (ValueError, TypeError):
            continue
        if parsed >= cutoff:
            trimmed.append(entry)
    return trimmed


def _append_activity_feed(entry: dict) -> None:
    with _state_lock:
        try:
            entries = _load_activity_feed()
            entries.append(entry)
            entries = _trim_activity_feed(entries)
            ACTIVITY_FEED_PATH.parent.mkdir(parents=True, exist_ok=True)
            with ACTIVITY_FEED_PATH.open("w", encoding="utf-8") as handle:
                json.dump(entries, handle)
            log_event(
                "webhook",
                "activity_feed",
                "success",
                contact_id=entry.get("person_id"),
                file=__file__,
                function="_append_activity_feed",
            )
        except Exception as exc:
            log_event(
                "webhook",
                "activity_feed",
                "failure",
                detail=str(exc),
                contact_id=entry.get("person_id"),
                exc_info=exc,
                file=__file__,
                function="_append_activity_feed",
            )


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


def handle_new_lead(contact_id: str, event_type: str = "peopleCreated") -> None:
    """Fetch contact, draft email, send Telegram card, schedule fallback."""
    with _in_flight_lock:
        if contact_id in _in_flight:
            log_event(
                "lead_alert",
                "handle_new_lead",
                "success",
                detail="suppressed duplicate in-flight",
                contact_id=contact_id,
                file=__file__,
                function="handle_new_lead",
            )
            return
        _in_flight.add(contact_id)
    try:
        log_event(
            "lead_alert",
            "handle_new_lead",
            "start",
            detail=f"source_event={event_type}",
            contact_id=contact_id,
            file=__file__,
            function="handle_new_lead",
        )
        if _is_recently_notified(contact_id):
            log_event(
                "lead_alert",
                "handle_new_lead",
                "success",
                detail="suppressed duplicate",
                contact_id=contact_id,
                file=__file__,
                function="handle_new_lead",
            )
            return

        if _try_resend_stored_lead_alert(contact_id):
            return

        if _lead_alert_draft_exists(contact_id):
            log_event(
                "lead_alert",
                "handle_new_lead",
                "success",
                detail="suppressed duplicate draft already stored",
                contact_id=contact_id,
                file=__file__,
                function="handle_new_lead",
            )
            return

        if not _begin_lead_alert_processing(contact_id):
            log_event(
                "lead_alert",
                "handle_new_lead",
                "success",
                detail="suppressed duplicate processing fingerprint",
                contact_id=contact_id,
                file=__file__,
                function="handle_new_lead",
            )
            return

        try:
            contact = get_contact_by_id(contact_id)
            if _assigned_to_name(contact) != ASSIGNED_TO_NAME:
                log_event(
                    "lead_alert",
                    "handle_new_lead",
                    "success",
                    detail="suppressed not assigned to Ben Olsen",
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

            _mark_notified(contact_id)
            _schedule_fallback(contact_id)
            log_event(
                "lead_alert",
                "handle_new_lead",
                "success",
                detail=f"alert sent via {event_type}",
                contact_id=contact_id,
                file=__file__,
                function="handle_new_lead",
            )
        finally:
            _clear_lead_alert_processing(contact_id)
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


def _process_people_updated(contact_id: str) -> None:
    try:
        contact = get_contact_by_id(contact_id)
    except Exception as exc:
        log_event(
            "lead_alert",
            "peopleUpdated",
            "failure",
            detail=str(exc),
            contact_id=contact_id,
            exc_info=exc,
            file=__file__,
            function="_process_people_updated",
        )
        return

    if not _contact_created_within_threshold(contact):
        log_event(
            "lead_alert",
            "peopleUpdated",
            "success",
            detail="suppressed stale contact: created before threshold",
            contact_id=contact_id,
            file=__file__,
            function="_process_people_updated",
        )
        return

    if not _last_activity_is_fresh(contact):
        log_event(
            "lead_alert",
            "peopleUpdated",
            "success",
            detail="suppressed not fresh: lastActivity outside window",
            contact_id=contact_id,
            file=__file__,
            function="_process_people_updated",
        )
        return

    handle_new_lead(contact_id, event_type="peopleUpdated")


def _process_fub_event(payload: dict) -> None:
    event = payload.get("event")
    resource_ids = payload.get("resourceIds") or []

    if event == "peopleCreated":
        for raw_id in resource_ids:
            handle_new_lead(str(raw_id), event_type="peopleCreated")
        return

    if event == "peopleUpdated":
        for raw_id in resource_ids:
            _process_people_updated(str(raw_id))
        return

    if event == "eventsCreated":
        for raw_id in resource_ids:
            try:
                payload_data = fub_get(f"/events/{raw_id}")
                event_record = _fub_single_record(payload_data, "events")
                person_id = event_record.get("personId")
                if person_id is None:
                    continue
                event_type = str(event_record.get("type") or "").strip()
                page_title = str(event_record.get("pageTitle") or "").strip()
                detail = event_type
                if page_title:
                    detail = f"{event_type} {page_title}".strip()
                _append_activity_feed({
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "event_type": "eventsCreated",
                    "actor_type": "inbound",
                    "person_id": str(person_id),
                    "person_name": "",
                    "detail": detail,
                })
            except Exception as exc:
                log_event(
                    "webhook",
                    "eventsCreated",
                    "failure",
                    detail=str(exc),
                    file=__file__,
                    function="_process_fub_event",
                )
        return

    if event == "callsCreated":
        for raw_id in resource_ids:
            try:
                payload_data = fub_get(f"/calls/{raw_id}")
                call_record = _fub_single_record(payload_data, "calls")
                person_id = call_record.get("personId")
                if person_id is None:
                    continue
                user_id = call_record.get("userId")
                is_incoming = call_record.get("isIncoming")
                if user_id == 1:
                    actor_type = "ben"
                elif is_incoming is True:
                    actor_type = "inbound"
                else:
                    continue
                outcome = str(call_record.get("outcome") or "").strip()
                note = str(call_record.get("note") or "")[:100]
                detail = f"{outcome} {note}".strip()
                _append_activity_feed({
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "event_type": "callsCreated",
                    "actor_type": actor_type,
                    "person_id": str(person_id),
                    "person_name": "",
                    "detail": detail,
                })
            except Exception as exc:
                log_event(
                    "webhook",
                    "callsCreated",
                    "failure",
                    detail=str(exc),
                    file=__file__,
                    function="_process_fub_event",
                )
        return

    if event == "textMessagesCreated":
        for raw_id in resource_ids:
            try:
                payload_data = fub_get(f"/textMessages/{raw_id}")
                text_record = _fub_single_record(payload_data, "textMessages")
                person_id = text_record.get("personId")
                if person_id is None:
                    continue
                user_id = text_record.get("userId")
                is_incoming = text_record.get("isIncoming")
                if user_id == 1 and is_incoming is False:
                    actor_type = "ben"
                    detail = "outbound text"
                elif is_incoming is True:
                    actor_type = "inbound"
                    detail = "inbound text"
                else:
                    continue
                _append_activity_feed({
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "event_type": "textMessagesCreated",
                    "actor_type": actor_type,
                    "person_id": str(person_id),
                    "person_name": "",
                    "detail": detail,
                })
            except Exception as exc:
                log_event(
                    "webhook",
                    "textMessagesCreated",
                    "failure",
                    detail=str(exc),
                    file=__file__,
                    function="_process_fub_event",
                )
        return

    log_event(
        "webhook",
        "dispatch",
        "success",
        detail=f"no matching route: {event or 'unknown'}",
        file=__file__,
        function="_process_fub_event",
    )


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "webhook"}


def _google_oauth_redirect_uri() -> str:
    base = (CMA_REDIRECT_BASE or "").rstrip("/")
    if not base:
        raise HTTPException(
            status_code=503,
            detail="CMA_REDIRECT_BASE is not configured for Google OAuth callback",
        )
    return f"{base}/oauth/google/callback"


@app.get("/oauth/google/authorize")
def google_oauth_authorize() -> RedirectResponse:
    """Start Google Calendar OAuth consent (one-time or re-auth)."""
    if GOOGLE_CALENDAR_CREDENTIALS_PATH is None:
        raise HTTPException(
            status_code=503,
            detail="GOOGLE_CALENDAR_CREDENTIALS_PATH is not configured",
        )
    try:
        auth_url = build_authorization_url(_google_oauth_redirect_uri())
    except Exception as exc:
        log_event(
            "google_calendar",
            "oauth_authorize",
            "failure",
            detail=str(exc),
            exc_info=exc,
            file=__file__,
            function="google_oauth_authorize",
        )
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    log_event(
        "google_calendar",
        "oauth_authorize",
        "start",
        detail=f"redirecting to Google consent, callback={_google_oauth_redirect_uri()}",
        file=__file__,
        function="google_oauth_authorize",
    )
    return RedirectResponse(url=auth_url, status_code=302)


@app.get("/oauth/google/callback")
def google_oauth_callback(
    code: str | None = None,
    error: str | None = None,
) -> HTMLResponse:
    """Exchange OAuth authorization code and persist refresh token."""
    if error:
        log_event(
            "google_calendar",
            "oauth_callback",
            "failure",
            detail=f"Google OAuth error: {error}",
            file=__file__,
            function="google_oauth_callback",
        )
        raise HTTPException(status_code=400, detail=f"Google OAuth error: {error}")

    if not code:
        raise HTTPException(status_code=400, detail="Missing authorization code")

    if GOOGLE_CALENDAR_CREDENTIALS_PATH is None:
        raise HTTPException(
            status_code=503,
            detail="GOOGLE_CALENDAR_CREDENTIALS_PATH is not configured",
        )

    redirect_uri = _google_oauth_redirect_uri()
    try:
        exchange_authorization_code(code, redirect_uri)
    except Exception as exc:
        log_event(
            "google_calendar",
            "oauth_callback",
            "failure",
            detail=str(exc),
            exc_info=exc,
            file=__file__,
            function="google_oauth_callback",
        )
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    log_event(
        "google_calendar",
        "oauth_callback",
        "success",
        detail=f"tokens saved to {GOOGLE_CALENDAR_CREDENTIALS_PATH}",
        file=__file__,
        function="google_oauth_callback",
    )
    return HTMLResponse(
        "<html><body><p>Google Calendar authorization complete. "
        "You can close this window.</p></body></html>"
    )


_RELAUNCH_BATCHES_ROOT = ROOT / "relaunch" / "batches"
_BATCH_ID_PATTERN = re.compile(r"^\d{4}-\d{2}$")
_OPAQUE_TOKEN_PATTERN = re.compile(r"^[A-Za-z0-9_-]{8,128}$")


def _safe_batch_dir(batch_id: str) -> Path:
    if not _BATCH_ID_PATTERN.match(batch_id or ""):
        raise HTTPException(status_code=400, detail="Invalid batch id")
    batch_dir = (_RELAUNCH_BATCHES_ROOT / batch_id).resolve()
    batches_root = _RELAUNCH_BATCHES_ROOT.resolve()
    if not str(batch_dir).startswith(str(batches_root) + os.sep):
        raise HTTPException(status_code=400, detail="Invalid batch path")
    if not batch_dir.is_dir():
        raise HTTPException(status_code=404, detail="Batch not found")
    return batch_dir


def _safe_batch_output_dir(batch_id: str) -> Path:
    output_dir = (_safe_batch_dir(batch_id) / "output").resolve()
    if not output_dir.is_dir():
        raise HTTPException(status_code=404, detail="Batch output not found")
    return output_dir


def _load_review_map(batch_id: str) -> dict[str, str]:
    path = _safe_batch_dir(batch_id) / "review_map.json"
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Review map not found")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise HTTPException(status_code=500, detail=f"Review map unreadable: {exc}")
    if not isinstance(payload, dict):
        raise HTTPException(status_code=500, detail="Review map invalid")
    return {str(k): str(v) for k, v in payload.items()}


def _require_relaunch_review_auth(authorization: str | None) -> None:
    """Basic auth for the directory-index view only."""
    user = os.environ.get("RELAUNCH_REVIEW_BASIC_USER", "").strip()
    password = os.environ.get("RELAUNCH_REVIEW_BASIC_PASSWORD", "").strip()
    if not user or not password:
        raise HTTPException(
            status_code=503,
            detail="Review auth not configured",
        )
    if not authorization or not authorization.lower().startswith("basic "):
        raise HTTPException(
            status_code=401,
            detail="Authentication required",
            headers={"WWW-Authenticate": 'Basic realm="relaunch-review"'},
        )
    try:
        decoded = base64.b64decode(authorization.split(" ", 1)[1].strip()).decode(
            "utf-8"
        )
        provided_user, provided_password = decoded.split(":", 1)
    except Exception:
        raise HTTPException(
            status_code=401,
            detail="Invalid authorization header",
            headers={"WWW-Authenticate": 'Basic realm="relaunch-review"'},
        )
    if not (
        hmac.compare_digest(provided_user, user)
        and hmac.compare_digest(provided_password, password)
    ):
        raise HTTPException(
            status_code=401,
            detail="Invalid credentials",
            headers={"WWW-Authenticate": 'Basic realm="relaunch-review"'},
        )


@app.get("/relaunch/batches/{batch_id}/")
def relaunch_batch_index(
    batch_id: str,
    authorization: str | None = Header(default=None),
) -> HTMLResponse:
    """Auth-gated HTML index of opaque PDF links for operator review."""
    _require_relaunch_review_auth(authorization)
    output_dir = _safe_batch_output_dir(batch_id)
    review_map = _load_review_map(batch_id)
    # Only list tokens whose files still exist.
    items_parts: list[str] = []
    for token, filename in sorted(review_map.items(), key=lambda kv: kv[1]):
        path = output_dir / filename
        if not path.is_file():
            continue
        items_parts.append(
            f'<li><a href="/relaunch/batches/{batch_id}/f/{token}.pdf">'
            f"{filename}</a></li>"
        )
    html = (
        "<!DOCTYPE html><html><head><meta charset='utf-8'>"
        f"<title>Relaunch batch {batch_id}</title></head><body>"
        f"<h1>Relaunch batch {batch_id}</h1>"
        f"<p>{len(items_parts)} PDF packet(s)</p>"
        f"<ul>{''.join(items_parts)}</ul>"
        "</body></html>"
    )
    return HTMLResponse(content=html)


@app.get("/relaunch/batches/{batch_id}/f/{token}.pdf")
def relaunch_batch_opaque_file(batch_id: str, token: str) -> FileResponse:
    """
    Serve one PDF by opaque token. Unauthenticated so Lob can fetch.
    Tokens are unguessable; predictable {city}_{street}.pdf paths are gone.
    """
    if not _OPAQUE_TOKEN_PATTERN.match(token or ""):
        raise HTTPException(status_code=400, detail="Invalid token")
    review_map = _load_review_map(batch_id)
    filename = review_map.get(token)
    if not filename:
        raise HTTPException(status_code=404, detail="File not found")
    if "/" in filename or "\\" in filename or filename.startswith("."):
        raise HTTPException(status_code=400, detail="Invalid mapped filename")
    if not filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are served")
    output_dir = _safe_batch_output_dir(batch_id)
    path = (output_dir / filename).resolve()
    if not str(path).startswith(str(output_dir) + os.sep):
        raise HTTPException(status_code=400, detail="Invalid file path")
    if not path.is_file():
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(
        path,
        media_type="application/pdf",
        filename=filename,
        headers={"Cache-Control": "private, no-store"},
    )


_CMA_GATEWAY_TIMEOUT_SECONDS = 30
_CMA_PDF_FETCH_TIMEOUT_SECONDS = 60
_PDF_MAGIC = b"%PDF-"


def _content_type_base(response: requests.Response) -> str:
    raw = str(response.headers.get("Content-Type") or "")
    return raw.split(";", 1)[0].strip().lower()


def _parse_meta_refresh_url(html: str) -> str | None:
    """Extract redirect target from a Cloud CMA HTML gateway meta-refresh page."""
    for match in re.finditer(
        r"<meta\b[^>]*(?:http-equiv\s*=\s*['\"]?refresh['\"]?[^>]*|"
        r"content\s*=\s*['\"][^'\"]*['\"][^>]*http-equiv\s*=\s*['\"]?refresh['\"]?)[^>]*>",
        html,
        re.IGNORECASE,
    ):
        tag = match.group(0)
        content_match = re.search(
            r"\bcontent\s*=\s*['\"]([^'\"]+)['\"]",
            tag,
            re.IGNORECASE,
        )
        if not content_match:
            continue
        url_match = re.search(
            r"url\s*=\s*(.+)",
            content_match.group(1),
            re.IGNORECASE,
        )
        if url_match:
            return url_match.group(1).strip().strip("'\"")
    return None


def _fetch_cma_pdf_bytes(pdf_url: str) -> tuple[bytes, str, str]:
    """Resolve and download CMA PDF bytes from Cloud CMA pdf_url.

    Returns (pdf_bytes, effective_source_url, content_type).
    """
    gateway_resp = requests.get(pdf_url, timeout=_CMA_GATEWAY_TIMEOUT_SECONDS)
    gateway_resp.raise_for_status()
    gateway_ct = _content_type_base(gateway_resp)

    if gateway_ct == "application/pdf":
        return gateway_resp.content, pdf_url, gateway_ct

    if gateway_ct == "text/html":
        redirect_url = _parse_meta_refresh_url(gateway_resp.text)
        if not redirect_url:
            raise ValueError(
                f"html response missing meta refresh redirect byte_len={len(gateway_resp.content)}"
            )
        resolved_url = urljoin(pdf_url, redirect_url)
        pdf_resp = requests.get(resolved_url, timeout=_CMA_PDF_FETCH_TIMEOUT_SECONDS)
        pdf_resp.raise_for_status()
        return pdf_resp.content, resolved_url, _content_type_base(pdf_resp)

    raise ValueError(
        f"unexpected content-type: {gateway_ct or 'missing'} "
        f"byte_len={len(gateway_resp.content)}"
    )


def _fail_cma_pdf_archive(
    job_id: str,
    detail: str,
    *,
    exc: Exception | None = None,
) -> JSONResponse:
    log_event(
        "cma",
        "callback",
        "failure",
        detail=f"job_id={job_id} {detail}",
        exc_info=exc,
        file=__file__,
        function="cma_callback",
    )
    send_operator_alert(f"CMA callback PDF archive failed job_id={job_id} {detail}")
    mark_failed(job_id)
    return JSONResponse(status_code=500, content={"status": "error"})


def _extract_cma_callback_fields(payload: dict[str, Any]) -> tuple[str, str, str | None]:
    """Pull job_id, pdf_url, and optional edit_url from a Cloud CMA callback body."""
    job_id = str(payload.get("job_id") or "").strip()
    pdf_url = str(payload.get("pdf_url") or "").strip()
    edit_raw = payload.get("edit_url")
    edit_url = str(edit_raw).strip() if edit_raw else None
    if edit_url == "":
        edit_url = None
    return job_id, pdf_url, edit_url


def _format_cma_callback_payload_for_log(payload: dict[str, Any]) -> str:
    """Serialize callback payload for logging. Strips api_key if present."""
    safe = {
        key: value
        for key, value in payload.items()
        if key.lower() not in {"api_key", "apikey"}
    }
    return json.dumps(safe, default=str)


def _recipient_first_name(contact_id: str) -> str:
    """Resolve first name for the ready-card send button label."""
    try:
        contact = get_contact_by_id(contact_id)
        first = str(contact.get("firstName") or "").strip()
        if first:
            return first
    except Exception:
        pass
    return "contact"


def _send_cma_ready_card(
    address: str,
    tracking_url: str,
    edit_url: str | None,
    chat_id: str,
    job_id: str,
    send_target_contact_id: str | None = None,
) -> bool:
    """Send a CMA ready card with View (and optional Edit) URL buttons.

    Jobs with a send target also get a Send to {{first_name}} callback button
    on its own row. Telegram allows mixing url and callback_data buttons; the
    send action is isolated on a second row for clarity.
    """
    url_row = [{"text": "View", "url": tracking_url}]
    if edit_url:
        url_row.append({"text": "Edit", "url": edit_url})
    keyboard = [url_row]
    if send_target_contact_id:
        first_name = _recipient_first_name(send_target_contact_id)
        keyboard.append(
            [{
                "text": f"Send to {first_name}",
                "callback_data": f"send_cma:{job_id}",
            }]
        )
    reply_markup = {"inline_keyboard": keyboard}
    text = f"CMA ready for {address}\n\n{tracking_url}"
    sent = send_inline_message(text, reply_markup=reply_markup, chat_id=chat_id)
    if sent:
        log_event(
            "cma",
            "ready_card",
            "success",
            detail=f"job_id={job_id}",
            contact_id=send_target_contact_id or "",
            file=__file__,
            function="_send_cma_ready_card",
        )
    else:
        err = sent.error or "unknown telegram error"
        log_event(
            "cma",
            "ready_card",
            "failure",
            detail=f"job_id={job_id} telegram={err}",
            contact_id=send_target_contact_id or "",
            file=__file__,
            function="_send_cma_ready_card",
        )
    return bool(sent)


def _resolve_cma_reply_chat_id(job, job_id: str) -> str:
    """Return the job reply target, falling back for pre-fix legacy jobs."""
    reply_chat_id = str(job.reply_chat_id or "").strip()
    if reply_chat_id:
        return reply_chat_id
    log_event(
        "cma",
        "ready_card",
        "fallback",
        detail=f"missing reply_chat_id on legacy job job_id={job_id}",
        file=__file__,
        function="_resolve_cma_reply_chat_id",
    )
    return str(TELEGRAM_CHAT_ID)


@app.post("/cma/callback")
async def cma_callback(request: Request) -> JSONResponse:
    """Receive Cloud CMA completion callback. Never 500 on unknown job_id.

    Phase 2 TODO: FUB custom field writeback for tracking URL (Theresa).
    Phase 2 TODO: CMA Delivery action plan enrollment (Theresa).
    Phase 2 TODO: Auto-trigger on inbound seller leads with address.
    Phase 2 TODO: cma.brightworkrealty.com subdomain (Scott / Cloudflare).
    """
    from urllib.parse import parse_qs

    job_id = ""
    pdf_url = ""
    edit_url: str | None = None
    try:
        raw_body = await request.body()
        payload: dict[str, Any] = {}
        try:
            parsed = json.loads(raw_body)
            if isinstance(parsed, dict):
                payload = parsed
        except (json.JSONDecodeError, UnicodeDecodeError, TypeError, ValueError):
            payload = {}
        if not payload.get("job_id"):
            try:
                form_map = parse_qs(raw_body.decode("utf-8", errors="replace"), keep_blank_values=True)
                payload = {k: (v[0] if v else "") for k, v in form_map.items()}
            except Exception:
                payload = {}
        job_id, pdf_url, edit_url = _extract_cma_callback_fields(payload)
    except Exception as exc:
        log_event(
            "cma",
            "callback",
            "failure",
            detail=f"parse error: {exc}",
            exc_info=exc,
            file=__file__,
            function="cma_callback",
        )
        return JSONResponse(status_code=400, content={"status": "bad_request"})

    if not job_id:
        return JSONResponse(status_code=404, content={"status": "not_found"})

    job = get_job(job_id)
    if job is None:
        log_event(
            "cma",
            "callback",
            "fallback",
            detail=(
                f"unknown job_id={job_id} "
                f"payload={_format_cma_callback_payload_for_log(payload)}"
            ),
            file=__file__,
            function="cma_callback",
        )
        return JSONResponse(status_code=404, content={"status": "not_found"})

    if not pdf_url:
        log_event(
            "cma",
            "callback",
            "failure",
            detail=f"missing pdf_url job_id={job_id}",
            file=__file__,
            function="cma_callback",
        )
        return JSONResponse(status_code=400, content={"status": "missing_pdf_url"})

    try:
        try:
            pdf_bytes, effective_pdf_url, received_content_type = _fetch_cma_pdf_bytes(
                pdf_url
            )
        except requests.RequestException as exc:
            return _fail_cma_pdf_archive(
                job_id,
                f"pdf fetch error: {exc}",
                exc=exc,
            )
        except ValueError as exc:
            return _fail_cma_pdf_archive(job_id, str(exc), exc=exc)

        if not pdf_bytes.startswith(_PDF_MAGIC):
            return _fail_cma_pdf_archive(
                job_id,
                (
                    f"invalid pdf bytes content_type={received_content_type or 'missing'} "
                    f"byte_len={len(pdf_bytes)}"
                ),
            )

        CMA_PDF_ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
        archive_path = CMA_PDF_ARCHIVE_DIR / f"{job.token}.pdf"
        archive_path.write_bytes(pdf_bytes)

        tracking_url = f"{CMA_REDIRECT_BASE.rstrip('/')}/r/{job.token}"
        updated = mark_ready(
            job_id,
            source_pdf_url=effective_pdf_url,
            archived_pdf_path=str(archive_path),
            tracking_url=tracking_url,
        )
        if updated is None:
            return JSONResponse(status_code=404, content={"status": "not_found"})

        if updated.contact_id:
            try:
                log_event(
                    "cma",
                    "custom_field_write",
                    "start",
                    detail=f"job_id={job_id} field=customCMAReportLink",
                    contact_id=updated.contact_id,
                    file=__file__,
                    function="cma_callback",
                )
                update_custom_field(
                    updated.contact_id,
                    "customCMAReportLink",
                    tracking_url,
                )
                log_event(
                    "cma",
                    "custom_field_write",
                    "success",
                    detail=f"job_id={job_id} field=customCMAReportLink",
                    contact_id=updated.contact_id,
                    file=__file__,
                    function="cma_callback",
                )
            except Exception as field_exc:
                log_event(
                    "cma",
                    "custom_field_write",
                    "failure",
                    detail=f"job_id={job_id} {field_exc}",
                    contact_id=updated.contact_id,
                    exc_info=field_exc,
                    file=__file__,
                    function="cma_callback",
                )
                send_operator_alert(
                    f"CMA custom field write failed job_id={job_id} "
                    f"contact_id={updated.contact_id}: {field_exc}"
                )

        _append_activity_feed({
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "event_type": "cma_ready",
            "actor_type": "system",
            "person_id": updated.contact_id or "",
            "person_name": "",
            "detail": f"job_id={job_id} address_len={len(updated.address)}",
        })
        log_event(
            "cma",
            "callback",
            "success",
            detail=f"job_id={job_id}",
            contact_id=updated.contact_id or "",
            file=__file__,
            function="cma_callback",
        )
        reply_chat_id = _resolve_cma_reply_chat_id(updated, job_id)
        _send_cma_ready_card(
            updated.address,
            tracking_url,
            edit_url,
            reply_chat_id,
            job_id,
            send_target_contact_id=updated.send_target_contact_id,
        )
        return JSONResponse(status_code=200, content={"status": "ok"})
    except Exception as exc:
        log_event(
            "cma",
            "callback",
            "failure",
            detail=f"job_id={job_id}",
            exc_info=exc,
            file=__file__,
            function="cma_callback",
        )
        return JSONResponse(status_code=500, content={"status": "error"})


@app.get("/r/{token}", response_model=None)
def cma_tracked_open(token: str):
    """Serve archived CMA PDF and record the open. Never 500 on unknown token."""
    job = get_job_by_token(token)
    if job is None:
        return JSONResponse(status_code=404, content={"status": "not_found"})

    try:
        capture(
            "cma_opened",
            {
                "token": token,
                "address": job.address,
                "contact_id": job.contact_id,
                "open_count": int(job.open_count or 0) + 1,
            },
        )
    except Exception:
        pass

    updated = record_open(token)
    if updated is None:
        return JSONResponse(status_code=404, content={"status": "not_found"})

    archive = updated.archived_pdf_path
    if not archive:
        return JSONResponse(status_code=404, content={"status": "not_found"})
    path = Path(archive)
    if not path.is_file():
        log_event(
            "cma",
            "tracked_open",
            "failure",
            detail=f"missing archive token={token}",
            file=__file__,
            function="cma_tracked_open",
        )
        return JSONResponse(status_code=404, content={"status": "not_found"})

    log_event(
        "cma",
        "tracked_open",
        "success",
        detail=f"token={token} open_count={updated.open_count}",
        contact_id=updated.contact_id or "",
        file=__file__,
        function="cma_tracked_open",
    )
    return FileResponse(
        path=path,
        media_type="application/pdf",
        filename=f"cma-{token}.pdf",
        content_disposition_type="inline",
    )


@app.post("/fub/webhook")
async def fub_webhook(
    request: Request,
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

    _log_inbound_webhook(payload)
    try:
        event_id = enqueue_event(payload)
        log_event(
            "webhook",
            "enqueue",
            "success",
            detail=f"event_id={event_id} event={payload.get('event', 'unknown')}",
            file=__file__,
            function="fub_webhook",
        )
    except Exception as exc:
        log_event(
            "webhook",
            "enqueue",
            "failure",
            detail=str(exc),
            exc_info=exc,
            file=__file__,
            function="fub_webhook",
        )
        raise HTTPException(status_code=500, detail="Queue write failed") from exc

    return JSONResponse(status_code=200, content={"status": "accepted"})


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8766)
