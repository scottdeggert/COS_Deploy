"""Minimal analytics capture seam. Temporary until a full PostHog tool exists."""

from __future__ import annotations

from typing import Any

import requests

from app.config import POSTHOG_API_KEY, POSTHOG_HOST, POSTHOG_PROJECT_ID
from tools.logger import log_event


def capture(event: str, properties: dict[str, Any] | None = None) -> None:
    """Fire a PostHog capture event when configured; otherwise no-op.

    Swallows all exceptions. Never raises.
    """
    if not POSTHOG_API_KEY or not POSTHOG_HOST or not POSTHOG_PROJECT_ID:
        return

    props = dict(properties or {})
    if "distinct_id" not in props:
        props["distinct_id"] = "cos_agent"

    url = f"{POSTHOG_HOST.rstrip('/')}/capture/"
    payload = {
        "api_key": POSTHOG_API_KEY,
        "project_id": POSTHOG_PROJECT_ID,
        "event": event,
        "properties": props,
    }
    try:
        requests.post(url, json=payload, timeout=5)
    except Exception as exc:
        log_event(
            "analytics",
            "capture",
            "failure",
            detail=f"event={event}",
            exc_info=exc,
            file=__file__,
            function="capture",
        )
