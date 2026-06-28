"""Generative writing handler — Ben's voice on every request."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import requests
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env", override=True)

from tools.logger import log_event
from tools.voice import build_system_prompt

OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY", "")
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
SONNET_MODEL = "anthropic/claude-sonnet-4-6"


def draft_communication(
    request: str,
    comm_type: str = "email",
    contact_context: dict[str, Any] | None = None,
) -> str:
    """Draft any communication in Ben's voice.

    Args:
        request: Ben's natural language description of what to write
        comm_type: email, sms, or note
        contact_context: optional FUB contact fields
    """
    type_instruction = {
        "email": "Draft an email body. No subject line unless asked. No signature.",
        "sms": "Draft an SMS. Under 160 characters. Very casual. First name only.",
        "note": "Draft a short professional note suitable for a CRM contact record.",
    }.get(comm_type, "Draft an email body. No subject line. No signature.")

    system_prompt = build_system_prompt(contact_context=contact_context)
    user_prompt = f"{type_instruction}\n\nRequest: {request}"

    try:
        resp = requests.post(
            OPENROUTER_URL,
            headers={
                "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "model": SONNET_MODEL,
                "max_tokens": 400,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
            },
            timeout=20,
        )
        resp.raise_for_status()
        data = json.loads(resp.text.strip())
        draft = data["choices"][0]["message"]["content"].strip()
        log_event(
            "draft_communication", "draft", "success",
            detail=f"{comm_type} — {request[:60]}",
            file=__file__, function="draft_communication",
        )
        return draft
    except Exception as exc:
        log_event(
            "draft_communication", "draft", "failure",
            detail=str(exc), exc_info=exc,
            file=__file__, function="draft_communication",
        )
        return f"Draft failed: {exc}"
