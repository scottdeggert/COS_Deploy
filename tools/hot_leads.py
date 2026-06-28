"""Fetch Hot 90 Days leads going cold, with action plan collision check."""

from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import requests
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env", override=True)

from tools.logger import log_event

FUB_API_KEY = os.environ.get("FUB_API_KEY", "")
FUB_BASE = "https://api.followupboss.com/v1"

session = requests.Session()


def _fub_get(path: str, params: dict | None = None) -> dict:
    resp = session.get(
        f"{FUB_BASE}{path}",
        auth=(FUB_API_KEY, ""),
        params=params or {},
        timeout=15,
    )
    resp.raise_for_status()
    return resp.json()


def get_active_action_plan_ids() -> set[str]:
    """Return set of personIds currently enrolled in an active action plan."""
    try:
        data = _fub_get("/actionPlansPeople", params={"limit": 200, "status": "active"})
        enrolled = set()
        for entry in data.get("actionPlansPeople", []):
            person_id = entry.get("personId")
            if person_id:
                enrolled.add(str(person_id))
        log_event(
            "fub",
            "get_action_plans",
            "success",
            detail=f"{len(enrolled)} contacts in active sequences",
            file=__file__,
            function="get_active_action_plan_ids",
        )
        return enrolled
    except Exception as exc:
        log_event(
            "fub",
            "get_action_plans",
            "failure",
            detail=str(exc),
            exc_info=exc,
            file=__file__,
            function="get_active_action_plan_ids",
        )
        return set()


def get_hot_leads_going_cold(days_silent: int = 14) -> list[dict[str, Any]]:
    """Return Hot 90 Days leads with no activity in `days_silent` days
    that are NOT currently in an active action plan sequence."""
    cutoff = datetime.now(tz=timezone.utc) - timedelta(days=days_silent)

    try:
        data = _fub_get(
            "/people",
            params={
                "limit": 100,
                "tags": "Hot 90 Days",
                "sort": "lastActivity",
                "order": "asc",
            },
        )
    except Exception as exc:
        log_event(
            "fub",
            "get_hot_leads",
            "failure",
            detail=str(exc),
            exc_info=exc,
            file=__file__,
            function="get_hot_leads_going_cold",
        )
        return []

    enrolled_ids = get_active_action_plan_ids()
    cold_leads = []

    for person in data.get("people", []):
        person_id = str(person.get("id", ""))
        if person_id in enrolled_ids:
            continue

        last_activity = person.get("lastActivity") or person.get("lastActionDate")
        if not last_activity:
            continue

        try:
            last_dt = datetime.fromisoformat(
                last_activity.replace("Z", "+00:00")
            )
        except ValueError:
            continue

        if last_dt < cutoff:
            days_ago = (datetime.now(tz=timezone.utc) - last_dt).days
            cold_leads.append({
                "id": person_id,
                "name": f"{person.get('firstName', '')} {person.get('lastName', '')}".strip(),
                "stage": person.get("stage") or "Unknown",
                "last_activity": last_dt.date().isoformat(),
                "days_silent": days_ago,
                "phone": _extract_phone(person),
            })

    log_event(
        "fub",
        "get_hot_leads",
        "success",
        detail=f"{len(cold_leads)} hot leads going cold",
        file=__file__,
        function="get_hot_leads_going_cold",
    )
    return cold_leads


def _extract_phone(person: dict) -> str:
    phones = person.get("phones") or []
    if isinstance(phones, list) and phones:
        first = phones[0]
        if isinstance(first, dict):
            return str(first.get("value", ""))
        return str(first)
    return ""
