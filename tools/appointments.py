"""FUB appointment fetching and upcoming appointment utilities."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from services.fub_client import fub_get as _fub_get
from tools.fub import get_contact_by_id
from tools.logger import log_event

_APPOINTMENTS_PAGE_SIZE = 100


def _fetch_all_appointments(page_size: int = _APPOINTMENTS_PAGE_SIZE) -> list[dict[str, Any]]:
    """Fetch all appointments from FUB, paginating until the account is complete."""
    appointments: list[dict[str, Any]] = []
    offset = 0
    while True:
        data = _fub_get(
            "/appointments",
            params={"limit": page_size, "offset": offset},
        )
        batch = data.get("appointments", [])
        appointments.extend(batch)
        total = data.get("_metadata", {}).get("total", len(appointments))
        offset += page_size
        if offset >= total or not batch:
            break
    return appointments


def _appointment_created_at(appt: dict[str, Any]) -> datetime | None:
    created_str = appt.get("created")
    if not created_str:
        return None
    try:
        return datetime.fromisoformat(created_str.replace("Z", "+00:00"))
    except ValueError:
        return None


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


def get_recently_booked_appointments(
    hours_back: int = 24,
    limit: int = _APPOINTMENTS_PAGE_SIZE,
) -> list[dict[str, Any]]:
    """Return appointments created within the last `hours_back` hours.

    FUB sort/order and date filter params do not work reliably. All pages are
    fetched, sorted client-side by `created` descending, then filtered in Python.
    """
    now = datetime.now(tz=timezone.utc)
    window_start = now - timedelta(hours=hours_back)

    try:
        appointments = _fetch_all_appointments(page_size=limit)
    except Exception as exc:
        log_event(
            "fub",
            "get_recently_booked_appointments",
            "failure",
            detail=str(exc),
            exc_info=exc,
            file=__file__,
            function="get_recently_booked_appointments",
        )
        return []

    appointments.sort(
        key=lambda appt: _appointment_created_at(appt) or datetime.min.replace(tzinfo=timezone.utc),
        reverse=True,
    )

    recent: list[dict[str, Any]] = []

    for appt in appointments:
        created = _appointment_created_at(appt)
        if created is None:
            continue
        if window_start <= created <= now:
            recent.append(appt)

    log_event(
        "fub",
        "get_recently_booked_appointments",
        "success",
        detail=f"{len(recent)} created in last {hours_back}h",
        file=__file__,
        function="get_recently_booked_appointments",
    )
    return recent


def get_contact_id_from_appointment(appt: dict) -> str | None:
    """Extract a FUB personId from appointment invitees, excluding Ben's user entry."""
    for invitee in appt.get("invitees", []):
        if invitee.get("userId") is not None:
            continue  # Skip Ben's own entry
        person_id = invitee.get("personId")
        if person_id:
            return str(person_id)
    return None


def _invitee_contact_name(appt: dict) -> str | None:
    """Resolve contact display name from the non-user invitee entry."""
    for invitee in appt.get("invitees", []):
        if invitee.get("userId") is not None:
            continue

        name = str(invitee.get("name") or "").strip()
        if not name:
            first = invitee.get("firstName") or ""
            last = invitee.get("lastName") or ""
            name = f"{first} {last}".strip()
        if name:
            return name

        person_id = invitee.get("personId")
        if not person_id:
            continue

        try:
            person = get_contact_by_id(str(person_id))
            return (
                f"{person.get('firstName', '')} {person.get('lastName', '')}".strip()
                or None
            )
        except Exception:
            return None
    return None


def _format_booking_start(start_str: str) -> str:
    """Return a Pacific-time date/time phrase for a booking line."""
    try:
        start = datetime.fromisoformat(start_str.replace("Z", "+00:00"))
        pacific_offset = timedelta(hours=-7)
        local = start + pacific_offset
        now_pacific = datetime.now(tz=timezone.utc) + pacific_offset
        time_str = local.strftime("%I:%M %p").lstrip("0")
        if local.date() == now_pacific.date():
            return f"today at {time_str}"
        return f"{local.strftime('%A, %B')} {local.day} at {time_str}"
    except ValueError:
        return start_str


def format_new_booking_line(appt: dict) -> str | None:
    """Return one digest line for a newly booked appointment, or None if unresolved."""
    name = _invitee_contact_name(appt)
    start_str = appt.get("start", "")
    if not name or not start_str:
        return None
    when = _format_booking_start(start_str)
    return f"{name} booked a meeting for {when}."


def format_morning_digest_new_bookings() -> list[str]:
    """Build new booking lines for the morning digest. Empty when none."""
    bookings = get_recently_booked_appointments()
    lines: list[str] = []
    for appt in sorted(bookings, key=lambda item: item.get("start", "")):
        line = format_new_booking_line(appt)
        if line:
            lines.append(line)
    return lines


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
