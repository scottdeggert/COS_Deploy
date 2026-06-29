"""Generative writing handler — Ben's voice on every request."""

from __future__ import annotations

import json
from typing import Any

import requests

from app.config import OPENROUTER_API_KEY, OPENROUTER_URL, SONNET_MODEL
from tools.logger import log_event
from tools.voice import build_system_prompt


def _strip_em_dashes(text: str) -> str:
    """Remove em dashes and en dashes from generated text.
    
    Replaces em dash patterns with a comma or period depending on context.
    This is a hard rule: no em dashes in any agent output.
    """
    import re
    # Replace " — " and " -- " (spaced) with ", "
    text = re.sub(r"\s*[—–]\s*", ", ", text)
    # Clean up any double commas that result
    text = re.sub(r",\s*,", ",", text)
    return text


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
        draft = _strip_em_dashes(data["choices"][0]["message"]["content"].strip())
        log_event(
            "draft_communication", "draft", "success",
            detail=f"{comm_type}: {request[:60]}",
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


def chat_reply(instruction: str) -> str:
    """Generate a conversational reply to Ben using the agent soul context.

    Used for greeting, unknown, and other conversational intents.
    Does not use Ben's outbound voice context -- loads soul.md instead.

    Args:
        instruction: describes what kind of reply to generate
    """
    from pathlib import Path

    soul_path = Path("/root/COS_Deploy/clients/ben-olsen/soul.md")
    try:
        soul_context = soul_path.read_text(encoding="utf-8")
    except Exception:
        soul_context = (
            "You are a warm, direct operational assistant. "
            "Respond briefly and helpfully."
        )

    try:
        resp = requests.post(
            OPENROUTER_URL,
            headers={
                "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "model": SONNET_MODEL,
                "max_tokens": 100,
                "messages": [
                    {"role": "system", "content": soul_context},
                    {"role": "user", "content": instruction},
                ],
            },
            timeout=20,
        )
        resp.raise_for_status()
        data = json.loads(resp.text.strip())
        reply = _strip_em_dashes(data["choices"][0]["message"]["content"].strip())
        log_event(
            "chat_reply", "reply", "success",
            detail=instruction[:60],
            file=__file__, function="chat_reply",
        )
        return reply
    except Exception as exc:
        log_event(
            "chat_reply", "reply", "failure",
            detail=str(exc), exc_info=exc,
            file=__file__, function="chat_reply",
        )
        return "Something went wrong on my end. Try again."
