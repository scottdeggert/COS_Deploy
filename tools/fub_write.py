"""Follow Up Boss write operations — kept separate from read-only tools/fub.py."""

from __future__ import annotations

import json
import os
import sys
from typing import Any

import requests
from requests.exceptions import HTTPError, RequestException

from tools.logger import log_event

BASE_URL = "https://api.followupboss.com/v1"
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


def add_note_to_contact(contact_id: str, note_text: str) -> dict:
    """POST a note to a FUB contact."""
    log_event(
        "fub",
        "add_note",
        "start",
        contact_id=contact_id,
        file=__file__,
        function="add_note_to_contact",
    )
    endpoint = "/notes"
    payload = {"personId": int(contact_id), "body": note_text}
    try:
        _ensure_api_key()
        url = f"{BASE_URL}{endpoint}"
        try:
            response = session.post(url, json=payload)
        except RequestException as exc:
            print(f"FUB API error: POST {endpoint} — {exc}", file=sys.stderr)
            raise

        if not response.ok:
            _raise_http_error("POST", endpoint, response)

        try:
            result = response.json()
        except json.JSONDecodeError as exc:
            print(
                f"FUB API error: POST {endpoint} — invalid JSON response: {exc}",
                file=sys.stderr,
            )
            raise ValueError(f"Invalid JSON from FUB API: {endpoint}") from exc

        log_event(
            "fub",
            "add_note",
            "success",
            contact_id=contact_id,
            file=__file__,
            function="add_note_to_contact",
        )
        return result
    except Exception as exc:
        log_event(
            "fub",
            "add_note",
            "failure",
            detail=str(exc),
            contact_id=contact_id,
            exc_info=exc,
            file=__file__,
            function="add_note_to_contact",
        )
        raise


def enroll_in_action_plan(contact_id: str, plan_id: int) -> dict:
    """Enroll a FUB contact in an action plan."""
    log_event(
        "fub",
        "enroll_action_plan",
        "start",
        contact_id=contact_id,
        file=__file__,
        function="enroll_in_action_plan",
    )
    endpoint = "/actionPlansPeople"
    payload = {"personId": int(contact_id), "actionPlanId": int(plan_id)}
    try:
        _ensure_api_key()
        url = f"{BASE_URL}{endpoint}"
        try:
            response = session.post(url, json=payload)
        except RequestException as exc:
            print(f"FUB API error: POST {endpoint} — {exc}", file=sys.stderr)
            raise

        if not response.ok:
            _raise_http_error("POST", endpoint, response)

        try:
            result = response.json()
        except json.JSONDecodeError as exc:
            print(
                f"FUB API error: POST {endpoint} — invalid JSON response: {exc}",
                file=sys.stderr,
            )
            raise ValueError(f"Invalid JSON from FUB API: {endpoint}") from exc

        log_event(
            "fub",
            "enroll_action_plan",
            "success",
            contact_id=contact_id,
            file=__file__,
            function="enroll_in_action_plan",
        )
        return result
    except Exception as exc:
        log_event(
            "fub",
            "enroll_action_plan",
            "failure",
            detail=str(exc),
            contact_id=contact_id,
            exc_info=exc,
            file=__file__,
            function="enroll_in_action_plan",
        )
        raise


def add_tags_to_contact(contact_id: str, tags: list[str]) -> dict:
    """Add tags to a FUB contact without replacing existing tags."""
    if not tags:
        return {}

    log_event(
        "fub",
        "add_tags",
        "start",
        contact_id=contact_id,
        file=__file__,
        function="add_tags_to_contact",
    )
    endpoint = f"/people/{contact_id}"
    params = {"mergeTags": "true"}
    payload = {"tags": tags}
    try:
        _ensure_api_key()
        url = f"{BASE_URL}{endpoint}"
        try:
            response = session.put(url, params=params, json=payload)
        except RequestException as exc:
            print(f"FUB API error: PUT {endpoint} — {exc}", file=sys.stderr)
            raise

        if not response.ok:
            _raise_http_error("PUT", endpoint, response)

        try:
            result = response.json()
        except json.JSONDecodeError as exc:
            print(
                f"FUB API error: PUT {endpoint} — invalid JSON response: {exc}",
                file=sys.stderr,
            )
            raise ValueError(f"Invalid JSON from FUB API: {endpoint}") from exc

        log_event(
            "fub",
            "add_tags",
            "success",
            contact_id=contact_id,
            file=__file__,
            function="add_tags_to_contact",
        )
        return result
    except Exception as exc:
        log_event(
            "fub",
            "add_tags",
            "failure",
            detail=str(exc),
            contact_id=contact_id,
            exc_info=exc,
            file=__file__,
            function="add_tags_to_contact",
        )
        raise


def send_fub_email(contact_id: str, subject: str, body: str) -> dict:
    """POST an email to a FUB contact."""
    log_event(
        "fub",
        "send_email",
        "start",
        contact_id=contact_id,
        file=__file__,
        function="send_fub_email",
    )
    endpoint = "/emails"
    payload = {
        "personId": int(contact_id),
        "subject": subject,
        "message": body,
        "isHtml": False,
    }
    try:
        _ensure_api_key()
        url = f"{BASE_URL}{endpoint}"
        try:
            response = session.post(url, json=payload)
        except RequestException as exc:
            print(f"FUB API error: POST {endpoint} — {exc}", file=sys.stderr)
            raise

        if not response.ok:
            _raise_http_error("POST", endpoint, response)

        try:
            result = response.json()
        except json.JSONDecodeError as exc:
            print(
                f"FUB API error: POST {endpoint} — invalid JSON response: {exc}",
                file=sys.stderr,
            )
            raise ValueError(f"Invalid JSON from FUB API: {endpoint}") from exc

        log_event(
            "fub",
            "send_email",
            "success",
            contact_id=contact_id,
            file=__file__,
            function="send_fub_email",
        )
        return result
    except Exception as exc:
        log_event(
            "fub",
            "send_email",
            "failure",
            detail=str(exc),
            contact_id=contact_id,
            exc_info=exc,
            file=__file__,
            function="send_fub_email",
        )
        raise
