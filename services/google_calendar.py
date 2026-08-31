"""Google Calendar API client for read-only schedule data.

Loads OAuth credentials from GOOGLE_CALENDAR_CREDENTIALS_PATH, refreshes
access tokens, and returns normalized events for a Pacific calendar day.
"""

from __future__ import annotations

import json
import os
import tempfile
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

from app.config import CLIENTS_DIR, GOOGLE_CALENDAR_CREDENTIALS_PATH
from tools.logger import log_event

_PACIFIC = ZoneInfo("America/Los_Angeles")
_CALENDAR_READONLY_SCOPE = "https://www.googleapis.com/auth/calendar.readonly"
_DEFAULT_SCOPES = [_CALENDAR_READONLY_SCOPE]
_DEFAULT_TOKEN_URI = "https://oauth2.googleapis.com/token"


@dataclass(frozen=True)
class CalendarEvent:
    """Normalized calendar event for digest rendering."""

    title: str
    start: datetime
    end: datetime
    all_day: bool
    calendar_source: str
    calendar_id: str


def _credentials_path() -> Path:
    if GOOGLE_CALENDAR_CREDENTIALS_PATH is None:
        raise EnvironmentError(
            "GOOGLE_CALENDAR_CREDENTIALS_PATH is not set. "
            "Add it to .env before using Google Calendar."
        )
    return GOOGLE_CALENDAR_CREDENTIALS_PATH


def _load_credentials_file() -> dict[str, Any]:
    path = _credentials_path()
    if not path.is_file():
        raise FileNotFoundError(f"Google Calendar credentials file not found: {path}")
    with path.open(encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict):
        raise ValueError(f"Google Calendar credentials file must be a JSON object: {path}")
    return payload


def _save_credentials_file(payload: dict[str, Any]) -> None:
    path = _credentials_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(
        dir=str(path.parent),
        prefix=f"{path.name}.",
        suffix=".tmp",
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_name, path)
    except Exception:
        try:
            os.unlink(temp_name)
        except OSError:
            pass
        raise


def load_calendar_exclusion_config(client_id: str) -> list[str]:
    """Return calendar IDs to exclude for a tenant (default: include all)."""
    config_path = CLIENTS_DIR / client_id / "google_calendar_config.json"
    if not config_path.is_file():
        return []
    try:
        with config_path.open(encoding="utf-8") as handle:
            payload = json.load(handle)
    except (OSError, json.JSONDecodeError):
        return []
    excluded = payload.get("exclude_calendar_ids", [])
    if not isinstance(excluded, list):
        return []
    return [str(item) for item in excluded if str(item).strip()]


def _build_credentials(payload: dict[str, Any]) -> Credentials:
    client_id = str(payload.get("client_id") or "").strip()
    client_secret = str(payload.get("client_secret") or "").strip()
    if not client_id or not client_secret:
        raise ValueError(
            "Google Calendar credentials file must include client_id and client_secret."
        )

    scopes = payload.get("scopes") or _DEFAULT_SCOPES
    if isinstance(scopes, str):
        scopes = [scopes]

    expiry = None
    expiry_raw = payload.get("expiry")
    if expiry_raw:
        try:
            expiry = datetime.fromisoformat(str(expiry_raw))
        except ValueError:
            expiry = None

    return Credentials(
        token=payload.get("token"),
        refresh_token=payload.get("refresh_token"),
        token_uri=str(payload.get("token_uri") or _DEFAULT_TOKEN_URI),
        client_id=client_id,
        client_secret=client_secret,
        scopes=list(scopes),
        expiry=expiry,
    )


def get_credentials() -> Credentials:
    """Load credentials from disk, refreshing the access token when needed."""
    payload = _load_credentials_file()
    creds = _build_credentials(payload)
    if creds.valid:
        return creds

    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
        payload["token"] = creds.token
        if creds.expiry is not None:
            payload["expiry"] = creds.expiry.isoformat()
        _save_credentials_file(payload)
        return creds

    if not creds.refresh_token:
        raise ValueError(
            "Google Calendar refresh token missing. Run OAuth authorization first."
        )

    raise ValueError("Google Calendar credentials are invalid and could not be refreshed.")


def list_calendars() -> list[dict[str, str]]:
    """Return Ben's calendars from calendarList.list."""
    creds = get_credentials()
    service = build("calendar", "v3", credentials=creds, cache_discovery=False)
    calendars: list[dict[str, str]] = []
    page_token: str | None = None

    while True:
        response = (
            service.calendarList()
            .list(pageToken=page_token, minAccessRole="reader")
            .execute()
        )
        for item in response.get("items", []):
            calendars.append(
                {
                    "id": str(item.get("id") or ""),
                    "summary": str(item.get("summary") or item.get("id") or ""),
                }
            )
        page_token = response.get("nextPageToken")
        if not page_token:
            break

    log_event(
        "google_calendar",
        "list_calendars",
        "success",
        detail=f"{len(calendars)} calendars",
        file=__file__,
        function="list_calendars",
    )
    return calendars


def _pacific_day_bounds(target_date: date) -> tuple[datetime, datetime]:
    day_start = datetime.combine(target_date, time.min, tzinfo=_PACIFIC)
    day_end = day_start + timedelta(days=1)
    return day_start, day_end


def _parse_event_datetime(value: str, all_day: bool) -> datetime:
    if all_day:
        parsed_date = date.fromisoformat(value)
        return datetime.combine(parsed_date, time.min, tzinfo=_PACIFIC)
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=_PACIFIC)
    return parsed.astimezone(_PACIFIC)


def _normalize_event(
    raw: dict[str, Any],
    calendar_id: str,
    calendar_source: str,
) -> CalendarEvent | None:
    start_payload = raw.get("start") or {}
    end_payload = raw.get("end") or {}
    start_value = start_payload.get("dateTime") or start_payload.get("date")
    if not start_value:
        return None

    all_day = "date" in start_payload and "dateTime" not in start_payload
    end_value = end_payload.get("dateTime") or end_payload.get("date") or start_value

    try:
        start = _parse_event_datetime(str(start_value), all_day)
        end = _parse_event_datetime(str(end_value), all_day)
    except ValueError:
        return None

    title = str(raw.get("summary") or "Untitled event").strip() or "Untitled event"
    return CalendarEvent(
        title=title,
        start=start,
        end=end,
        all_day=all_day,
        calendar_source=calendar_source,
        calendar_id=calendar_id,
    )


def get_events_for_date(
    target_date: date,
    calendar_ids: list[str],
    calendar_labels: dict[str, str] | None = None,
) -> list[CalendarEvent]:
    """Return normalized events for one Pacific calendar day across calendar IDs."""
    if not calendar_ids:
        return []

    creds = get_credentials()
    service = build("calendar", "v3", credentials=creds, cache_discovery=False)
    day_start, day_end = _pacific_day_bounds(target_date)
    events: list[CalendarEvent] = []
    labels = calendar_labels or {}

    for calendar_id in calendar_ids:
        calendar_source = labels.get(calendar_id, calendar_id)
        page_token: str | None = None
        while True:
            response = (
                service.events()
                .list(
                    calendarId=calendar_id,
                    timeMin=day_start.isoformat(),
                    timeMax=day_end.isoformat(),
                    singleEvents=True,
                    orderBy="startTime",
                    pageToken=page_token,
                )
                .execute()
            )
            for raw in response.get("items", []):
                normalized = _normalize_event(raw, calendar_id, calendar_source)
                if normalized is not None:
                    events.append(normalized)
            page_token = response.get("nextPageToken")
            if not page_token:
                break

    events.sort(key=lambda event: (event.all_day, event.start, event.title))
    return events


def get_events_for_client_date(client_id: str, target_date: date) -> list[CalendarEvent]:
    """List calendars, apply tenant exclusions, and fetch events for one day."""
    excluded = set(load_calendar_exclusion_config(client_id))
    calendars = list_calendars()
    included = [item for item in calendars if item["id"] and item["id"] not in excluded]
    calendar_ids = [item["id"] for item in included]
    labels = {item["id"]: item["summary"] for item in included}
    return get_events_for_date(target_date, calendar_ids, labels)


def exchange_authorization_code(code: str, redirect_uri: str) -> dict[str, Any]:
    """Exchange an OAuth authorization code and persist tokens to disk."""
    from google_auth_oauthlib.flow import Flow

    payload = _load_credentials_file()
    client_id = str(payload.get("client_id") or "").strip()
    client_secret = str(payload.get("client_secret") or "").strip()
    if not client_id or not client_secret:
        raise ValueError(
            "Google Calendar credentials file must include client_id and client_secret "
            "before running OAuth."
        )

    scopes = list(payload.get("scopes") or _DEFAULT_SCOPES)
    flow = Flow.from_client_config(
        {
            "web": {
                "client_id": client_id,
                "client_secret": client_secret,
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": str(payload.get("token_uri") or _DEFAULT_TOKEN_URI),
            }
        },
        scopes=scopes,
        redirect_uri=redirect_uri,
        autogenerate_code_verifier=False,
    )
    flow.fetch_token(code=code)
    creds = flow.credentials

    payload["token"] = creds.token
    payload["refresh_token"] = creds.refresh_token
    if creds.expiry is not None:
        payload["expiry"] = creds.expiry.isoformat()
    payload["scopes"] = list(creds.scopes or scopes)
    _save_credentials_file(payload)
    return payload


def build_authorization_url(redirect_uri: str, state: str = "") -> str:
    """Build the Google OAuth consent URL for initial authorization."""
    from google_auth_oauthlib.flow import Flow

    payload = _load_credentials_file()
    client_id = str(payload.get("client_id") or "").strip()
    client_secret = str(payload.get("client_secret") or "").strip()
    if not client_id or not client_secret:
        raise ValueError(
            "Google Calendar credentials file must include client_id and client_secret."
        )

    scopes = list(payload.get("scopes") or _DEFAULT_SCOPES)
    flow = Flow.from_client_config(
        {
            "web": {
                "client_id": client_id,
                "client_secret": client_secret,
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": str(payload.get("token_uri") or _DEFAULT_TOKEN_URI),
            }
        },
        scopes=scopes,
        redirect_uri=redirect_uri,
        autogenerate_code_verifier=False,
    )
    auth_url, _ = flow.authorization_url(
        access_type="offline",
        include_granted_scopes="true",
        prompt="consent",
        state=state or None,
    )
    return auth_url
