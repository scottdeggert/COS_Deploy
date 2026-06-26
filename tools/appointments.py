"""FUB appointment fetching and upcoming appointment utilities."""

from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from typing import Any

import requests

from tools.logger import log_event

FUB_API_KEY = os.environ.get("FUB_API_KEY", "")
FUB_BASE = "https://api.followupboss.com/v1"

session = requests.Session()


def _fub_get(path: str, params: dict | None = None) -> dict:
    resp = session.get(
        f"{FUB_BASE}{path}",
        auth=(FUB_API_KEY, ""),
        params=params or {},
        timeout=15,
    )
    resp.raise_for_status()
    return resp.json()


def get_upcoming_appointments(
    hours_ahead: int = 24,
    limit: int = 50,
) -> list[dict[str, Any]]:
    """Return appointments starting within the next `hours_ahead` hours.

    Fetches up to `limit` appointments sorted by start descending,
    then filters in Python to the upcoming window. FUB date filter
    params do not work reliably — filtering is done client-side.
    """
    now = datetime.now(tz=timezone.utc)
    window_end = now + timedelta(hours=hours_ahead)

    try:
        data = _fub_get(
            "/appointments",
            params={"limit": limit, "sort": "start", "order": "desc"},
        )
    except Exception as exc:
        log_event(
            "fub",
            "get_appointments",
            "failure",
            detail=str(exc),
            exc_info=exc,
            file=__file__,
            function="get_upcoming_appointments",
        )
        return []

    appointments = data.get("appointments", [])
    upcoming = []

    for appt in appointments:
        start_str = appt.get("start")
        if not start_str:
            continue
        try:
            start = datetime.fromisoformat(start_str.replace("Z", "+00:00"))
        except ValueError:
            continue
        if now <= start <= window_end:
            upcoming.append(appt)

    log_event(
        "fub",
        "get_appointments",
        "success",
        detail=f"{len(upcoming)} upcoming in next {hours_ahead}h",
        file=__file__,
        function="get_upcoming_appointments",
    )
    return upcoming


def get_contact_id_from_appointment(appt: dict) -> str | None:
    """Extract a FUB personId from appointment invitees, excluding Ben's user entry."""
    for invitee in appt.get("invitees", []):
        if invitee.get("userId") is not None:
            continue  # Skip Ben's own entry
        person_id = invitee.get("personId")
        if person_id:
            return str(person_id)
    return None


def format_appointment_summary(appt: dict) -> str:
    """Return a one-line human-readable summary for digest use."""
    title = appt.get("title") or "Appointment"
    start_str = appt.get("start", "")
    location = appt.get("location") or ""
    try:
        start = datetime.fromisoformat(start_str.replace("Z", "+00:00"))
        # Convert UTC to Pacific
        pacific_offset = timedelta(hours=-7)  # PDT; adjust to -8 for PST
        local = start + pacific_offset
        time_str = local.strftime("%I:%M %p").lstrip("0")
    except ValueError:
        time_str = start_str
    summary = f"{time_str} — {title}"
    if location:
        summary += f" @ {location}"
    return summary
