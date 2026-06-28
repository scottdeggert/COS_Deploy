"""Fetch enriched contact context from FUB for generative requests."""

from __future__ import annotations

import os
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


def get_contact_context(person_id: str, notes_limit: int = 5) -> dict[str, Any]:
    """Return structured contact context for use in generative prompts."""
    context: dict[str, Any] = {}

    try:
        person = _fub_get(f"/people/{person_id}")
        phones = person.get("phones") or []
        phone = ""
        if isinstance(phones, list) and phones:
            first = phones[0]
            phone = str(first.get("value", "") if isinstance(first, dict) else first)

        tags = ", ".join(
            t.get("name", "") if isinstance(t, dict) else str(t)
            for t in (person.get("tags") or [])
        )

        context = {
            "name": f"{person.get('firstName', '')} {person.get('lastName', '')}".strip(),
            "stage": person.get("stage") or "",
            "last_activity": (person.get("lastActivity") or "")[:10],
            "tags": tags,
            "source": person.get("source") or "",
            "phone": phone,
        }
    except Exception as exc:
        log_event(
            "fub_activity", "get_person", "failure",
            detail=str(exc), exc_info=exc,
            file=__file__, function="get_contact_context",
        )
        return context

    try:
        notes_data = _fub_get("/notes", params={"personId": person_id, "limit": notes_limit})
        notes = notes_data.get("notes", [])
        if notes:
            note_lines = []
            for note in notes:
                body = note.get("body", "").strip()
                created = (note.get("created") or "")[:10]
                if body and "[CONTENT HIDDEN]" not in body:
                    note_lines.append(f"  [{created}] {body}")
            if note_lines:
                context["notes"] = "\n".join(note_lines)
    except Exception as exc:
        log_event(
            "fub_activity", "get_notes", "failure",
            detail=str(exc), exc_info=exc,
            file=__file__, function="get_contact_context",
        )

    return context
