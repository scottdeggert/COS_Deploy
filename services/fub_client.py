"""Centralized FUB API client with retry and rate-limit handling.

All tools that make FUB API calls must import from this module.
Do not use requests.Session directly in tools/.

FUB rate limits: sliding 10-second window, ~180-200 global requests,
20 for events, 10 for notes. Cross-process token bucket serializes
all outbound calls via services/rate_limiter.py.

Usage:
    from services.fub_client import fub_get, fub_post, fub_put

    data = fub_get("/people/31735")
    result = fub_post("/notes", json={"body": "...", "personId": 31735})
"""

from __future__ import annotations

import inspect
import random
import re
import time
from typing import Any

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from app.config import (
    FUB_429_BACKOFF_BASE_SECONDS,
    FUB_429_BACKOFF_MAX_SECONDS,
    FUB_429_MAX_ATTEMPTS,
    FUB_API_KEY,
    FUB_BASE_URL,
    FUB_X_SYSTEM,
    FUB_X_SYSTEM_KEY,
)
from services.rate_limiter import acquire_fub_token, update_from_response
from tools.logger import log_event

_SESSION: requests.Session | None = None
_PEOPLE_ID_PATTERN = re.compile(r"/people/(\d+)")


def configure_events_rate_limit(max_per_10s: int) -> None:
    """Backward-compatible no-op. Global token bucket replaces events-only cap."""
    _ = max_per_10s


def _retry_after_seconds(response: requests.Response) -> float | None:
    retry_after = response.headers.get("Retry-After")
    if not retry_after:
        return None
    try:
        return max(float(retry_after), 0.0)
    except ValueError:
        return None


def _contact_id_from_context(
    path: str,
    params: dict[str, Any] | None = None,
    json: dict[str, Any] | None = None,
) -> str:
    match = _PEOPLE_ID_PATTERN.search(path)
    if match:
        return match.group(1)
    if params:
        person_id = params.get("personId")
        if person_id is not None:
            return str(person_id)
    if json:
        person_id = json.get("personId")
        if person_id is not None:
            return str(person_id)
    return ""


def _get_session() -> requests.Session:
    """Return the singleton FUB session, creating it if needed."""
    global _SESSION
    if _SESSION is not None:
        return _SESSION

    session = requests.Session()
    session.auth = (FUB_API_KEY, "")
    session.headers.update(
        {
            "X-System": FUB_X_SYSTEM,
            "X-System-Key": FUB_X_SYSTEM_KEY,
        }
    )

    retry_strategy = Retry(
        total=0,
        raise_on_status=False,
    )
    adapter = HTTPAdapter(max_retries=retry_strategy)
    session.mount("https://", adapter)
    session.mount("http://", adapter)

    _SESSION = session
    return _SESSION


def _caller_context() -> tuple[str, str]:
    """Return the first stack frame outside this module."""
    for frame in inspect.stack()[2:]:
        if "fub_client.py" not in frame.filename:
            return frame.filename, frame.function
    return __file__, "unknown"


def _failure_detail(
    method: str,
    path: str,
    status_code: int,
    params: dict[str, Any] | None = None,
    json: dict[str, Any] | None = None,
) -> str:
    """Build a failure detail string with endpoint context for tracing."""
    detail = f"HTTP {status_code} -- {method} {path}"
    if params:
        detail += f" params={params}"
    if json:
        detail += f" json_keys={sorted(json.keys())}"
    return detail


def _429_backoff_seconds(attempt: int, response: requests.Response | None) -> float:
    if response is not None:
        retry_after = _retry_after_seconds(response)
        if retry_after is not None:
            return retry_after
    base = min(
        FUB_429_BACKOFF_BASE_SECONDS * (2 ** attempt),
        FUB_429_BACKOFF_MAX_SECONDS,
    )
    jitter = random.uniform(0.0, base * 0.25)
    return base + jitter


def _request_with_rate_limit(
    method: str,
    path: str,
    *,
    params: dict[str, Any] | None = None,
    json: dict[str, Any] | None = None,
) -> dict[str, Any]:
    session = _get_session()
    url = f"{FUB_BASE_URL}{path}"
    contact_id = _contact_id_from_context(path, params=params, json=json)
    caller_file, caller_function = _caller_context()
    last_response: requests.Response | None = None

    for attempt in range(FUB_429_MAX_ATTEMPTS):
        acquire_fub_token()
        if method == "GET":
            last_response = session.get(url, params=params or {}, timeout=15)
        elif method == "POST":
            last_response = session.post(url, json=json or {}, timeout=15)
        else:
            last_response = session.put(url, json=json or {}, timeout=15)

        update_from_response(last_response)

        if last_response.status_code == 429 and attempt < FUB_429_MAX_ATTEMPTS - 1:
            wait_seconds = _429_backoff_seconds(attempt, last_response)
            time.sleep(wait_seconds)
            continue

        if not last_response.ok:
            log_event(
                "fub_client",
                method.lower(),
                "failure",
                detail=_failure_detail(
                    method,
                    path,
                    last_response.status_code,
                    params=params,
                    json=json,
                ),
                contact_id=contact_id,
                file=caller_file,
                function=caller_function,
            )
            last_response.raise_for_status()

        return last_response.json()

    if last_response is not None and not last_response.ok:
        log_event(
            "fub_client",
            method.lower(),
            "failure",
            detail=_failure_detail(
                method,
                path,
                last_response.status_code,
                params=params,
                json=json,
            ),
            contact_id=contact_id,
            file=caller_file,
            function=caller_function,
        )
        last_response.raise_for_status()

    raise requests.HTTPError(f"FUB {method} failed after retries: {path}")


def fub_get(path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
    """GET from the FUB API. Returns parsed JSON dict."""
    return _request_with_rate_limit("GET", path, params=params)


def fub_post(path: str, json: dict[str, Any] | None = None) -> dict[str, Any]:
    """POST to the FUB API. Returns parsed JSON dict."""
    return _request_with_rate_limit("POST", path, json=json)


def fub_put(path: str, json: dict[str, Any] | None = None) -> dict[str, Any]:
    """PUT to the FUB API. Returns parsed JSON dict."""
    return _request_with_rate_limit("PUT", path, json=json)
