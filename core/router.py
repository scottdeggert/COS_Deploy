"""Haiku-powered intent classifier.

Receives an InboundMessage, sends it to Haiku with recent conversation
context, and returns a RoutedIntent that the transport layer passes
to the appropriate handler.

Known Haiku quirks (do not remove these workarounds):
- Haiku wraps JSON in markdown fences despite prompt instructions.
  Strip with: raw.strip('` \\n').removeprefix('json').strip()
- OpenRouter responses have leading whitespace before JSON.
  Always use json.loads(resp.text.strip()) not resp.json().
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests

from app.config import OPENROUTER_API_KEY, OPENROUTER_URL, HAIKU_MODEL, LOGS_DIR
from app.schemas import InboundMessage, RoutedIntent
from tools.logger import log_event

_INTENTS = """
brief_request - user wants a contact brief, profile, or lookup by name or ID; includes "look up", "find", "what's X's address"
hot_leads - user asks about cooling hot leads in general
hot_leads_list - user wants to see the cooling hot leads list; says "hot leads", "show me the list", or "yes" after being prompted
draft_outreach - user wants outreach drafted for one or all cold hot leads; entity is the contact name or "all"
draft_communication - user wants to draft an email, text, or note to someone; entity is the full contact name if provided; type is email/sms/note
status_check - user wants recent log output
greeting - hello, hi, checking in
identity_query - asking what the agent is or does
help_request - asking for commands or help
unknown - anything else
"""

_SYSTEM_PROMPT = f"""You are an intent classifier for a real estate agent's AI Chief of Staff.
Classify the user's message into exactly one intent from this list:
{_INTENTS}

Extract any entity (contact name, contact ID, or "all") if present.
For draft_communication: extract the full contact name as entity and the type (email/sms/note, default email).
For brief_request: treat "look up", "find", "what's X's address", and similar lookup phrases as brief_request.
For draft_outreach: extract the contact name as entity, or "all" if the user says "all", "everyone", "draft all".

Respond ONLY with valid JSON in this exact format:
{{"intent": "intent_name", "entity": "extracted entity or null", "type": "email or sms or note or null", "confidence": 0.0}}

No other text. No markdown. Just the JSON object."""


class ConversationBuffer:
    """Rolling window of recent exchanges, persisted to disk.

    Survives agent restarts so Ben can resume threads.
    """

    MAX_TURNS: int = 10
    PERSIST_PATH: Path = LOGS_DIR / "conversation_buffer.json"

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


def classify_intent(message: InboundMessage, buffer: ConversationBuffer) -> RoutedIntent:
    """Classify inbound message intent via Haiku.

    Returns a RoutedIntent. Never raises -- falls back to intent_type='unknown'
    on any failure.
    """
    recent = buffer.recent(3)
    context_lines = []
    for turn in recent:
        role = "Ben" if turn["role"] == "user" else "Agent"
        context_lines.append(f"{role}: {turn['content'][:200]}")
    context = "\n".join(context_lines)

    user_prompt = (
        f"Recent conversation:\n{context}\n\nNew message: {message.raw_text}"
        if context
        else f"Message: {message.raw_text}"
    )

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
                    {"role": "system", "content": _SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt},
                ],
            },
            timeout=10,
        )
        resp.raise_for_status()
        data = json.loads(resp.text.strip())
        raw_content = data["choices"][0]["message"]["content"].strip()
        raw_content = raw_content.strip("` \n").removeprefix("json").strip()
        parsed = json.loads(raw_content)

        intent_type = parsed.get("intent", "unknown")
        log_event(
            "router", "classify", "success",
            detail=f"{message.raw_text[:50]} -> {intent_type}",
            file=__file__, function="classify_intent",
        )
        return RoutedIntent(
            original_message=message,
            intent_type=intent_type,
            entity=parsed.get("entity"),
            comm_type=parsed.get("type"),
            confidence=float(parsed.get("confidence", 0.0)),
        )
    except Exception as exc:
        log_event(
            "router", "classify", "failure",
            detail=str(exc), exc_info=exc,
            file=__file__, function="classify_intent",
        )
        return RoutedIntent(
            original_message=message,
            intent_type="unknown",
            entity=None,
            comm_type=None,
            confidence=0.0,
        )
