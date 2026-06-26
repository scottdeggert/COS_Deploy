"""Haiku-powered intent classifier with conversation context."""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests

from pathlib import Path as _Path
from dotenv import load_dotenv as _load_dotenv

_load_dotenv(_Path(__file__).resolve().parent.parent / ".env", override=True)

from tools.logger import log_event

OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY", "")
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
HAIKU_MODEL = "anthropic/claude-haiku-4-5"

INTENTS = """
brief_request - user wants a contact brief by name or ID
hot_leads_list - user confirms they want the list of cooling hot leads
draft_outreach - user wants outreach drafted for one or all hot leads
status_check - user wants recent log output
greeting - hello, hi, checking in
identity_query - asking what the agent is or does
help_request - asking for commands or help
unknown - anything else
"""

SYSTEM_PROMPT = f"""You are an intent classifier for a real estate agent's AI Chief of Staff.
Classify the user's message into exactly one intent from this list:
{INTENTS}

Also extract any entity (contact name, contact ID, or "all") if present.

Respond ONLY with valid JSON in this exact format:
{{"intent": "intent_name", "entity": "extracted entity or null", "confidence": 0.0}}

No other text. No markdown. Just the JSON object."""


class ConversationBuffer:
    """Rolling window of recent exchanges, persisted to disk."""

    MAX_TURNS = 10
    PERSIST_PATH = Path("/root/COS_Deploy/logs/conversation_buffer.json")

    def __init__(self) -> None:
        self._turns: list[dict[str, str]] = []
        self._load()

    def _load(self) -> None:
        try:
            if self.PERSIST_PATH.exists():
                with self.PERSIST_PATH.open(encoding="utf-8") as f:
                    self._turns = json.load(f)
        except Exception:
            self._turns = []

    def _save(self) -> None:
        try:
            self.PERSIST_PATH.parent.mkdir(parents=True, exist_ok=True)
            with self.PERSIST_PATH.open("w", encoding="utf-8") as f:
                json.dump(self._turns[-self.MAX_TURNS:], f)
        except Exception:
            pass

    def add(self, role: str, content: str) -> None:
        self._turns.append({
            "role": role,
            "content": content,
            "ts": datetime.now(tz=timezone.utc).isoformat(),
        })
        if len(self._turns) > self.MAX_TURNS:
            self._turns = self._turns[-self.MAX_TURNS:]
        self._save()

    def recent(self, n: int = 3) -> list[dict[str, str]]:
        return self._turns[-n:]

    def last_agent_message(self) -> str | None:
        for turn in reversed(self._turns):
            if turn.get("role") == "assistant":
                return turn.get("content")
        return None


def classify_intent(message: str, buffer: ConversationBuffer) -> dict[str, Any]:
    """Send message + recent context to Haiku, return structured intent."""
    recent = buffer.recent(3)
    context_lines = []
    for turn in recent:
        role = "Ben" if turn["role"] == "user" else "Agent"
        context_lines.append(f"{role}: {turn['content'][:200]}")
    context = "\n".join(context_lines)

    user_prompt = f"Recent conversation:\n{context}\n\nNew message: {message}" if context else f"Message: {message}"

    try:
        resp = requests.post(
            OPENROUTER_URL,
            headers={
                "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "model": HAIKU_MODEL,
                "max_tokens": 100,
                "messages": [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt},
                ],
            },
            timeout=10,
        )
        resp.raise_for_status()
        data = json.loads(resp.text.strip())
        raw_content = data["choices"][0]["message"]["content"].strip()
        raw_content = raw_content.strip("` \n").removeprefix("json").strip()
        result = json.loads(raw_content)
        log_event(
            "intent_router",
            "classify",
            "success",
            detail=f"{message[:50]} → {result.get('intent')}",
            file=__file__,
            function="classify_intent",
        )
        return result
    except Exception as exc:
        log_event(
            "intent_router",
            "classify",
            "failure",
            detail=str(exc),
            exc_info=exc,
            file=__file__,
            function="classify_intent",
        )
        return {"intent": "unknown", "entity": None, "confidence": 0.0}
