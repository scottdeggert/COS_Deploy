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

from typing import Any

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from app.config import FUB_API_KEY, FUB_BASE_URL
from tools.logger import log_event

_SESSION: requests.Session | None = None


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


def fub_get(path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
    """GET from the FUB API. Returns parsed JSON dict.

    Raises requests.HTTPError on non-2xx after retries exhausted.
    """
    session = _get_session()
    url = f"{FUB_BASE_URL}{path}"
    resp = session.get(url, params=params or {}, timeout=15)

    if not resp.ok:
        log_event(
            "fub_client", "get", "failure",
            detail=f"HTTP {resp.status_code} -- {path}",
            file=__file__, function="fub_get",
        )
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
        log_event(
            "fub_client", "post", "failure",
            detail=f"HTTP {resp.status_code} -- {path}",
            file=__file__, function="fub_post",
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
        log_event(
            "fub_client", "put", "failure",
            detail=f"HTTP {resp.status_code} -- {path}",
            file=__file__, function="fub_put",
        )
        resp.raise_for_status()

    return resp.json()
