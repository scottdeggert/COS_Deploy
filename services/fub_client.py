"""Centralized FUB API client with retry and rate-limit handling.

All tools that make FUB API calls must import from this module.
Do not use requests.Session directly in tools/.

FUB rate limits: sliding 10-second window, ~180-200 global requests,
20 for events, 10 for notes. The retry adapter handles 429s automatically.

Usage:
    from services.fub_client import fub_get, fub_post, fub_put

    data = fub_get("/people/31735")
    result = fub_post("/notes", json={"body": "...", "personId": 31735})
"""

from __future__ import annotations

import inspect
import threading
import time
from collections import deque
from typing import Any

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from app.config import FUB_API_KEY, FUB_BASE_URL
from tools.logger import log_event

_SESSION: requests.Session | None = None
_EVENTS_RATE_LIMIT_PER_10S = 18
_EVENTS_WINDOW_SECONDS = 10.0
_EVENTS_TIMESTAMPS: deque[float] = deque()
_EVENTS_LOCK = threading.Lock()


def configure_events_rate_limit(max_per_10s: int) -> None:
    """Set the sliding-window cap for GET /events calls."""
    global _EVENTS_RATE_LIMIT_PER_10S
    if max_per_10s > 0:
        _EVENTS_RATE_LIMIT_PER_10S = max_per_10s


def _is_events_path(path: str) -> bool:
    normalized = path.split("?", 1)[0]
    return normalized == "/events" or normalized.startswith("/events/")


def _acquire_events_slot() -> None:
    """Block until a GET /events slot is available in the sliding window."""
    while True:
        with _EVENTS_LOCK:
            now = time.monotonic()
            while _EVENTS_TIMESTAMPS and now - _EVENTS_TIMESTAMPS[0] > _EVENTS_WINDOW_SECONDS:
                _EVENTS_TIMESTAMPS.popleft()
            if len(_EVENTS_TIMESTAMPS) < _EVENTS_RATE_LIMIT_PER_10S:
                _EVENTS_TIMESTAMPS.append(now)
                return
            wait_seconds = _EVENTS_WINDOW_SECONDS - (now - _EVENTS_TIMESTAMPS[0]) + 0.05
        time.sleep(max(wait_seconds, 0.05))


def _retry_after_seconds(response: requests.Response) -> float | None:
    retry_after = response.headers.get("Retry-After")
    if not retry_after:
        return None
    try:
        return max(float(retry_after), 0.0)
    except ValueError:
        return None


def _get_session() -> requests.Session:
    """Return the singleton FUB session, creating it if needed."""
    global _SESSION
    if _SESSION is not None:
        return _SESSION

    session = requests.Session()
    session.auth = (FUB_API_KEY, "")

    retry_strategy = Retry(
        total=3,
        backoff_factor=2,           # waits: 2s, 4s, 8s
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["GET", "POST", "PUT", "PATCH"],
        raise_on_status=False,      # we handle status ourselves
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


def fub_get(path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
    """GET from the FUB API. Returns parsed JSON dict.

    Raises requests.HTTPError on non-2xx after retries exhausted.
    """
    session = _get_session()
    url = f"{FUB_BASE_URL}{path}"
    max_attempts = 4 if _is_events_path(path) else 1

    for attempt in range(max_attempts):
        if _is_events_path(path):
            _acquire_events_slot()
        resp = session.get(url, params=params or {}, timeout=15)

        if resp.status_code == 429 and _is_events_path(path) and attempt < max_attempts - 1:
            wait_seconds = _retry_after_seconds(resp) or min(2 ** attempt, 8)
            time.sleep(wait_seconds)
            continue

        if not resp.ok:
            caller_file, caller_function = _caller_context()
            log_event(
                "fub_client", "get", "failure",
                detail=_failure_detail("GET", path, resp.status_code, params=params),
                file=caller_file, function=caller_function,
            )
            resp.raise_for_status()

        return resp.json()

    resp.raise_for_status()
    return resp.json()


def fub_post(path: str, json: dict[str, Any] | None = None) -> dict[str, Any]:
    """POST to the FUB API. Returns parsed JSON dict.

    Raises requests.HTTPError on non-2xx after retries exhausted.
    """
    session = _get_session()
    url = f"{FUB_BASE_URL}{path}"
    resp = session.post(url, json=json or {}, timeout=15)

    if not resp.ok:
        caller_file, caller_function = _caller_context()
        log_event(
            "fub_client", "post", "failure",
            detail=_failure_detail("POST", path, resp.status_code, json=json),
            file=caller_file, function=caller_function,
        )
        resp.raise_for_status()

    return resp.json()


def fub_put(path: str, json: dict[str, Any] | None = None) -> dict[str, Any]:
    """PUT to the FUB API. Returns parsed JSON dict.

    Raises requests.HTTPError on non-2xx after retries exhausted.
    """
    session = _get_session()
    url = f"{FUB_BASE_URL}{path}"
    resp = session.put(url, json=json or {}, timeout=15)

    if not resp.ok:
        caller_file, caller_function = _caller_context()
        log_event(
            "fub_client", "put", "failure",
            detail=_failure_detail("PUT", path, resp.status_code, json=json),
            file=caller_file, function=caller_function,
        )
        resp.raise_for_status()

    return resp.json()
