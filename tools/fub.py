"""
Follow Up Boss API client.

Framework-agnostic integration — no CrewAI or other agent framework imports.
Can be used directly or wrapped by any orchestration layer.
"""

from __future__ import annotations

import json
import os
import sys
from typing import Any

import requests
from requests.exceptions import HTTPError, RequestException

from tools.logger import log_event

BASE_URL = "https://api.followupboss.com/v1"
ASSIGNED_TO_NAME = "Ben Olsen"
DEFAULT_TIMEOUT = 10

session = requests.Session()

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


def search_contacts(query: str, limit: int = 25) -> list[dict]:
    """Search contacts assigned in FUB, filtered to Ben Olsen."""
    endpoint = "/people"
    params = {"q": query, "limit": limit, "assigned": "true"}
    payload = _get_json("GET", endpoint, params=params)
    people = _extract_list(payload, "people")
    return [person for person in people if _assigned_to_name(person) == ASSIGNED_TO_NAME]


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
