"""Google Calendar helpers for the morning digest schedule section."""

from __future__ import annotations

from datetime import date, datetime
from zoneinfo import ZoneInfo

from app.config import GOOGLE_CALENDAR_CREDENTIALS_PATH
from services.google_calendar import CalendarEvent, get_events_for_client_date
from tools.logger import log_event

_PACIFIC = ZoneInfo("America/Los_Angeles")


def _pacific_today() -> date:
    return datetime.now(tz=_PACIFIC).date()


def fetch_today_calendar_events(client_id: str) -> list[CalendarEvent]:
    """Fetch today's Google Calendar events for digest rendering."""
    if GOOGLE_CALENDAR_CREDENTIALS_PATH is None:
        log_event(
            "google_calendar",
            "fetch_today_events",
            "fallback",
            detail="GOOGLE_CALENDAR_CREDENTIALS_PATH not configured",
            file=__file__,
            function="fetch_today_calendar_events",
        )
        return []

    target_date = _pacific_today()
    try:
        events = get_events_for_client_date(client_id, target_date)
    except Exception as exc:
        log_event(
            "google_calendar",
            "fetch_today_events",
            "failure",
            detail=str(exc),
            exc_info=exc,
            file=__file__,
            function="fetch_today_calendar_events",
        )
        return []

    log_event(
        "google_calendar",
        "fetch_today_events",
        "success",
        detail=(
            f"{len(events)} events for {target_date.isoformat()} "
            f"from {GOOGLE_CALENDAR_CREDENTIALS_PATH}"
        ),
        file=__file__,
        function="fetch_today_calendar_events",
    )
    return events


def format_calendar_event_line(event: CalendarEvent) -> str:
    """Return one digest line for a Google Calendar event."""
    if event.all_day:
        time_part = "All day"
    else:
        time_part = event.start.strftime("%I:%M %p").lstrip("0")
    summary = f"{time_part} - {event.title}"
    if event.calendar_source and event.calendar_source != event.calendar_id:
        summary += f" ({event.calendar_source})"
    return summary


def format_morning_digest_schedule_lines(events: list[CalendarEvent]) -> list[str]:
    """Build schedule section lines for the morning digest."""
    if not events:
        return ["No events on your calendar today."]
    return [f"* {format_calendar_event_line(event)}" for event in events]
