"""
Follow Up Boss API client.

Framework-agnostic integration — no CrewAI or other agent framework imports.
Can be used directly or wrapped by any orchestration layer.
"""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from typing import Any, TypedDict

import requests
from requests.exceptions import HTTPError, RequestException

from tools.logger import log_event

BASE_URL = "https://api.followupboss.com/v1"
ASSIGNED_TO_NAME = "Ben Olsen"
DEFAULT_TIMEOUT = 10
DISAMBIGUATION_ACTIVITY_DAYS = 90
ACTIVE_ACTION_PLAN_STATUSES = frozenset({"running", "active"})

session = requests.Session()


class SearchContactsDisambiguationResult(TypedDict):
    primary: dict
    duplicates_found: list[dict]
    disambiguation_required: bool

_original_request = session.request


def _request_with_timeout(method: str, url: str, **kwargs: Any) -> requests.Response:
    kwargs.setdefault("timeout", DEFAULT_TIMEOUT)
    return _original_request(method, url, **kwargs)


session.request = _request_with_timeout  # type: ignore[method-assign]


def _ensure_api_key() -> None:
    api_key = os.environ.get("FUB_API_KEY", "")
    if not api_key:
        raise ValueError("FUB_API_KEY environment variable is required")
    session.auth = (api_key, "")


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


def _require_ben_olsen(person: dict) -> None:
    if _assigned_to_name(person) != ASSIGNED_TO_NAME:
        raise PermissionError("Contact not assigned to Ben Olsen")


def _log_http_error(method: str, endpoint: str, response: requests.Response) -> None:
    print(
        f"FUB API error: {method} {endpoint} — HTTP {response.status_code}: {response.text}",
        file=sys.stderr,
    )


def _raise_http_error(method: str, endpoint: str, response: requests.Response) -> None:
    _log_http_error(method, endpoint, response)
    raise HTTPError(
        f"{method} {endpoint} failed with HTTP {response.status_code}",
        response=response,
    )


def _get_json(method: str, endpoint: str, **kwargs: Any) -> dict:
    _ensure_api_key()
    url = f"{BASE_URL}{endpoint}"
    try:
        response = session.request(method, url, **kwargs)
    except RequestException as exc:
        print(f"FUB API error: {method} {endpoint} — {exc}", file=sys.stderr)
        raise

    if not response.ok:
        _raise_http_error(method, endpoint, response)

    try:
        return response.json()
    except json.JSONDecodeError as exc:
        print(
            f"FUB API error: {method} {endpoint} — invalid JSON response: {exc}",
            file=sys.stderr,
        )
        raise ValueError(f"Invalid JSON from FUB API: {endpoint}") from exc


def _extract_list(payload: dict, key: str) -> list[dict]:
    items = payload.get(key, [])
    if not isinstance(items, list):
        raise ValueError(f"Expected list at '{key}' in FUB API response")
    return items


def get_contact_by_id(contact_id: str) -> dict:
    """Fetch a contact by FUB person ID."""
    log_event(
        "fub",
        "get_contact",
        "start",
        contact_id=contact_id,
        file=__file__,
        function="get_contact_by_id",
    )
    endpoint = f"/people/{contact_id}"
    try:
        _ensure_api_key()
        url = f"{BASE_URL}{endpoint}"
        try:
            response = session.get(url)
        except RequestException as exc:
            print(f"FUB API error: GET {endpoint} — {exc}", file=sys.stderr)
            raise

        if response.status_code != 200:
            _log_http_error("GET", endpoint, response)
            raise ValueError(
                f"Failed to fetch contact {contact_id}: HTTP {response.status_code}"
            )

        try:
            result = response.json()
        except json.JSONDecodeError as exc:
            print(
                f"FUB API error: GET {endpoint} — invalid JSON response: {exc}",
                file=sys.stderr,
            )
            raise ValueError(f"Invalid JSON from FUB API: {endpoint}") from exc

        log_event(
            "fub",
            "get_contact",
            "success",
            contact_id=contact_id,
            file=__file__,
            function="get_contact_by_id",
        )
        return result
    except Exception as e:
        log_event(
            "fub",
            "get_contact",
            "failure",
            detail=str(e),
            contact_id=contact_id,
            exc_info=e,
        )
        raise


def get_recent_activity(contact_id: str, limit: int = 10) -> list[dict]:
    """Fetch recent timeline events for a contact, most recent first."""
    log_event(
        "fub",
        "get_recent_activity",
        "start",
        contact_id=contact_id,
        file=__file__,
        function="get_recent_activity",
    )
    try:
        contact = get_contact_by_id(contact_id)
        _require_ben_olsen(contact)

        endpoint = "/events"
        params = {
            "personId": contact_id,
            "limit": limit,
            "sort": "created",
            "direction": "desc",
        }
        payload = _get_json("GET", endpoint, params=params)
        result = _extract_list(payload, "events")
        log_event(
            "fub",
            "get_recent_activity",
            "success",
            contact_id=contact_id,
            file=__file__,
            function="get_recent_activity",
        )
        return result
    except Exception as e:
        log_event(
            "fub",
            "get_recent_activity",
            "failure",
            detail=str(e),
            contact_id=contact_id,
            exc_info=e,
        )
        raise


def _normalize_person_name(first: str | None, last: str | None) -> str:
    return " ".join(f"{first or ''} {last or ''}".split()).casefold()


def _parse_iso_timestamp(value: str | None) -> datetime | None:
    if not value:
        return None
    normalized = value.replace("Z", "+00:00") if value.endswith("Z") else value
    parsed = datetime.fromisoformat(normalized)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed


def _person_display_name(person: dict) -> str:
    return f"{person.get('firstName', '')} {person.get('lastName', '')}".strip()


def _contact_summary(person: dict) -> dict:
    return {
        "id": str(person.get("id", "")),
        "name": _person_display_name(person),
        "lastActivity": person.get("lastActivity"),
        "stage": str(person.get("stage") or ""),
    }


def _has_valid_email(person: dict) -> bool:
    emails = person.get("emails") or []
    if not isinstance(emails, list):
        return False
    for entry in emails:
        if not isinstance(entry, dict):
            continue
        status = str(entry.get("status") or "").casefold()
        value = str(entry.get("value") or entry.get("email") or "").strip()
        if status == "valid" and value:
            return True
    return False


def _list_action_plan_enrollments(contact_id: str) -> list[dict]:
    endpoint = "/actionPlansPeople"
    params = {"personId": contact_id, "limit": 100}
    payload = _get_json("GET", endpoint, params=params)
    return _extract_list(payload, "actionPlansPeople")


def _has_active_action_plan(contact_id: str) -> bool:
    try:
        enrollments = _list_action_plan_enrollments(contact_id)
    except Exception:
        return False
    for enrollment in enrollments:
        status = str(enrollment.get("status") or "").casefold()
        if status in ACTIVE_ACTION_PLAN_STATUSES:
            return True
    return False


def _list_appointments_for_contact(contact_id: str) -> list[dict]:
    endpoint = "/appointments"
    params = {"personId": contact_id, "limit": 100}
    payload = _get_json("GET", endpoint, params=params)
    return _extract_list(payload, "appointments")


def _has_upcoming_appointment(contact_id: str) -> bool:
    try:
        appointments = _list_appointments_for_contact(contact_id)
    except Exception:
        return False
    now = datetime.now(timezone.utc)
    for appointment in appointments:
        start = _parse_iso_timestamp(str(appointment.get("start") or ""))
        if start and start >= now:
            return True
    return False


def _contact_disambiguation_score(person: dict) -> tuple[float, int, int, int]:
    """Higher tuple values indicate a stronger match."""
    last_activity = _parse_iso_timestamp(str(person.get("lastActivity") or ""))
    activity_ts = last_activity.timestamp() if last_activity else 0.0
    contact_id = str(person.get("id", ""))
    return (
        activity_ts,
        int(_has_upcoming_appointment(contact_id)),
        int(_has_active_action_plan(contact_id)),
        int(_has_valid_email(person)),
    )


def _last_activity_within_days(person: dict, days: int) -> bool:
    last_activity = _parse_iso_timestamp(str(person.get("lastActivity") or ""))
    if not last_activity:
        return False
    elapsed = datetime.now(timezone.utc) - last_activity
    return elapsed.days <= days


def _duplicate_name_group(people: list[dict], query: str) -> list[dict] | None:
    query_norm = " ".join(query.split()).casefold()
    by_name: dict[str, list[dict]] = {}
    for person in people:
        key = _normalize_person_name(
            person.get("firstName"), person.get("lastName")
        )
        by_name.setdefault(key, []).append(person)

    if query_norm in by_name and len(by_name[query_norm]) >= 2:
        return by_name[query_norm]

    duplicate_groups = [group for group in by_name.values() if len(group) >= 2]
    if len(duplicate_groups) == 1 and len(duplicate_groups[0]) == len(people):
        return duplicate_groups[0]
    return None


def _disambiguate_duplicate_contacts(
    people: list[dict],
) -> SearchContactsDisambiguationResult:
    full_records: list[dict] = []
    for person in people:
        contact_id = str(person.get("id", ""))
        full_records.append(get_contact_by_id(contact_id))

    ranked = sorted(full_records, key=_contact_disambiguation_score, reverse=True)
    primary = ranked[0]
    duplicates_found = [_contact_summary(person) for person in ranked[1:]]
    disambiguation_required = any(
        _last_activity_within_days(person, DISAMBIGUATION_ACTIVITY_DAYS)
        for person in ranked
    )
    return {
        "primary": primary,
        "duplicates_found": duplicates_found,
        "disambiguation_required": disambiguation_required,
    }


def search_contacts(
    query: str, limit: int = 25
) -> list[dict] | SearchContactsDisambiguationResult:
    """Search contacts assigned in FUB, filtered to Ben Olsen.

    Returns a list for zero/one results and for multi-match cases without
    same-name duplicates. When two or more results share a normalized name,
    returns a disambiguation payload with primary, duplicates_found, and
    disambiguation_required.
    """
    endpoint = "/people"
    params = {"q": query, "limit": limit, "assigned": "true"}
    payload = _get_json("GET", endpoint, params=params)
    people = _extract_list(payload, "people")
    filtered = [
        person for person in people if _assigned_to_name(person) == ASSIGNED_TO_NAME
    ]

    duplicate_group = _duplicate_name_group(filtered, query)
    if duplicate_group and len(duplicate_group) >= 2:
        return _disambiguate_duplicate_contacts(duplicate_group)
    return filtered


def get_contact_by_email(email: str) -> dict | None:
    """Return the first matching person by email, or None if not found or not Ben's."""
    endpoint = "/people"
    params = {"email": email}
    payload = _get_json("GET", endpoint, params=params)
    people = _extract_list(payload, "people")
    if not people:
        return None

    person = people[0]
    if _assigned_to_name(person) != ASSIGNED_TO_NAME:
        return None
    return person


def get_appointments(contact_id: str) -> list[dict]:
    """Fetch appointments for a contact."""
    log_event(
        "fub",
        "get_appointments",
        "start",
        contact_id=contact_id,
        file=__file__,
        function="get_appointments",
    )
    try:
        contact = get_contact_by_id(contact_id)
        _require_ben_olsen(contact)

        endpoint = "/appointments"
        params = {"personId": contact_id}
        payload = _get_json("GET", endpoint, params=params)
        result = _extract_list(payload, "appointments")
        log_event(
            "fub",
            "get_appointments",
            "success",
            contact_id=contact_id,
            file=__file__,
            function="get_appointments",
        )
        return result
    except Exception as e:
        log_event(
            "fub",
            "get_appointments",
            "failure",
            detail=str(e),
            contact_id=contact_id,
            exc_info=e,
        )
        raise


if __name__ == "__main__":
    TEST_CONTACT_ID = os.environ.get("TEST_FUB_CONTACT_ID", "")
    if TEST_CONTACT_ID:
        contact = get_contact_by_id(TEST_CONTACT_ID)
        print(json.dumps(contact, indent=2))
        activity = get_recent_activity(TEST_CONTACT_ID)
        print(f"\nRecent activity ({len(activity)} events):")
        for event in activity:
            print(f"  {event.get('created', '')} — {event.get('type', '')}")
    else:
        print("Set TEST_FUB_CONTACT_ID env var to run smoke test")
