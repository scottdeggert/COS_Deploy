"""Morning digest formatting from logs/activity_feed.json."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

from app.config import LOGS_DIR
from tools.fub import ASSIGNED_TO_NAME, get_contact_by_id
from tools.logger import log_event

ACTIVITY_FEED_PATH = LOGS_DIR / "activity_feed.json"
DIGEST_ACTIVITY_WINDOW_HOURS = 24
DIGEST_ACTIVITY_MAX_PEOPLE = 10


def _parse_iso_timestamp(value: str) -> datetime:
    normalized = value.replace("Z", "+00:00") if value.endswith("Z") else value
    parsed = datetime.fromisoformat(normalized)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed


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


def _contact_display_name(contact: dict) -> str:
    return f"{contact.get('firstName', '')} {contact.get('lastName', '')}".strip()


def format_morning_digest_recent_activity() -> list[str]:
    """Build Recent Activity lines for the morning digest."""
    log_event(
        "activity_feed",
        "morning_digest_recent_activity",
        "start",
        file=__file__,
        function="format_morning_digest_recent_activity",
    )

    cutoff = datetime.now(timezone.utc) - timedelta(hours=DIGEST_ACTIVITY_WINDOW_HOURS)
    recent_by_person: dict[str, dict] = {}

    for entry in _load_activity_feed():
        person_id = str(entry.get("person_id") or "").strip()
        if not person_id or person_id == "0":
            continue

        timestamp_raw = entry.get("timestamp")
        if not timestamp_raw:
            continue
        try:
            timestamp = _parse_iso_timestamp(str(timestamp_raw))
        except (ValueError, TypeError):
            continue
        if timestamp < cutoff:
            continue

        if entry.get("actor_type") != "inbound":
            continue

        existing = recent_by_person.get(person_id)
        if existing is None or timestamp > _parse_iso_timestamp(str(existing["timestamp"])):
            recent_by_person[person_id] = entry

    sorted_entries = sorted(
        recent_by_person.values(),
        key=lambda item: _parse_iso_timestamp(str(item["timestamp"])),
        reverse=True,
    )

    contact_cache: dict[str, dict] = {}
    qualified: list[tuple[str, str]] = []

    for entry in sorted_entries:
        person_id = str(entry["person_id"])
        if person_id not in contact_cache:
            try:
                contact_cache[person_id] = get_contact_by_id(person_id)
            except Exception as exc:
                log_event(
                    "activity_feed",
                    "morning_digest_recent_activity",
                    "failure",
                    detail=str(exc),
                    contact_id=person_id,
                    exc_info=exc,
                    file=__file__,
                    function="format_morning_digest_recent_activity",
                )
                continue

        contact = contact_cache[person_id]
        if _assigned_to_name(contact) != ASSIGNED_TO_NAME:
            continue

        detail = str(entry.get("detail") or "").strip()
        if not detail:
            continue

        qualified.append((_contact_display_name(contact) or f"Contact {person_id}", detail))

    header = f"Recent activity (last {DIGEST_ACTIVITY_WINDOW_HOURS}h):"
    lines = [header]

    if not qualified:
        lines.append(
            f"No new activity in the last {DIGEST_ACTIVITY_WINDOW_HOURS} hours."
        )
        log_event(
            "activity_feed",
            "morning_digest_recent_activity",
            "success",
            file=__file__,
            function="format_morning_digest_recent_activity",
        )
        return lines

    shown = qualified[:DIGEST_ACTIVITY_MAX_PEOPLE]
    overflow = len(qualified) - len(shown)

    for name, detail in shown:
        lines.append(f"* {name} - {detail}")
    if overflow > 0:
        lines.append(f"+{overflow} more")

    log_event(
        "activity_feed",
        "morning_digest_recent_activity",
        "success",
        file=__file__,
        function="format_morning_digest_recent_activity",
    )
    return lines
