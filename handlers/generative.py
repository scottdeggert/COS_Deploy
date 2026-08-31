"""Generative writing handler -- draft_communication and draft_outreach."""

from __future__ import annotations

import re

import yaml

from app.config import CLIENTS_DIR, CLIENT_ID
from app.schemas import HandlerResult, RoutedIntent
from tools.draft_communication import chat_reply, draft_communication
from tools.fub import search_contacts
from tools.fub_activity import get_contact_context
from tools.logger import log_event
from tools.telegram import send_operator_alert

FALLBACK_MESSAGE = (
    "I ran into a problem drafting that. Try again or check FUB directly: "
    "https://app.followupboss.com"
)

_CAPABILITIES_MISSING_REPLY = (
    "I don't have that information yet, it's worth asking Scott about. "
    "Do you want me to flag it for him?"
)


def _capabilities_path():
    return CLIENTS_DIR / CLIENT_ID / "knowledge" / "capabilities.md"


def _load_capabilities() -> str | None:
    """Read capabilities.md at request time. Returns None if missing or empty."""
    path = _capabilities_path()
    try:
        text = path.read_text(encoding="utf-8").strip()
    except OSError as exc:
        log_event(
            "generative", "load_capabilities", "failure",
            detail=str(exc),
            file=__file__, function="_load_capabilities",
        )
        return None
    if not text:
        log_event(
            "generative", "load_capabilities", "failure",
            detail="capabilities.md is empty",
            file=__file__, function="_load_capabilities",
        )
        return None
    return text


def _load_soul_config() -> dict:
    soul_path = CLIENTS_DIR / CLIENT_ID / "soul.yaml"
    with soul_path.open(encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return data if isinstance(data, dict) else {}


def _recent_history(current_message: str, n: int = 5) -> list[dict]:
    """Live conversation turns from the process buffer.

    Imported at call time so this module can load without importing
    core.main (core.main already imports this handler).

    The current user turn is already in the buffer by the time a
    handler runs, so fetch one extra turn and drop it when it matches.
    """
    from core.main import _buffer
    turns = _buffer.recent(n + 1)
    if turns and turns[-1].get("content") == current_message:
        turns = turns[:-1]
    return turns


def handle_greeting(intent: RoutedIntent) -> HandlerResult:
    """Handle greeting intents."""
    message = intent.original_message.raw_text
    reply = chat_reply(
        f"Ben just greeted you with: '{message}'. "
        "Respond warmly and briefly. Open the door for what he needs. "
        "1-2 sentences. Vary your phrasing naturally.",
        history=_recent_history(intent.original_message.raw_text),
    )
    return HandlerResult(success=True, telegram_output=reply)


def handle_identity(intent: RoutedIntent) -> HandlerResult:
    """Handle identity_query intents."""
    soul = _load_soul_config()
    name = soul.get("name", "Trevor")
    personality = str(soul.get("personality_summary", "")).strip()
    reply = f"I'm {name}. {personality}"
    return HandlerResult(success=True, telegram_output=reply)


def handle_help(intent: RoutedIntent) -> HandlerResult:
    """Handle help_request intents."""
    message = intent.original_message.raw_text
    capabilities = _load_capabilities()
    if capabilities is None:
        send_operator_alert(
            "help_request handler: capabilities.md missing, empty, or unreadable"
        )
        reply = chat_reply(
            f"Ben asked what you can do or how to use you: '{message}'. "
            f"You do not have your capabilities reference loaded. "
            f"Respond with this meaning in your own words, warmly and briefly: "
            f"'{_CAPABILITIES_MISSING_REPLY}'",
            history=_recent_history(intent.original_message.raw_text),
        )
        return HandlerResult(success=True, telegram_output=reply)

    reply = chat_reply(
        f"Ben asked what you can do or how to use you: '{message}'. "
        "Answer using ONLY the capabilities reference below. "
        "Do not invent features not listed there. "
        "Plain language, Ben's point of view, concise.\n\n"
        f"Capabilities reference:\n{capabilities}",
        history=_recent_history(intent.original_message.raw_text),
    )
    return HandlerResult(success=True, telegram_output=reply)


def handle_fallback(intent: RoutedIntent) -> HandlerResult:
    """Handle unknown or unclassified intents."""
    message = intent.original_message.raw_text
    if re.search(r"https?://", message):
        return HandlerResult(
            success=True,
            telegram_output=(
                "I can't pull content from a link yet, that's coming. "
                "For now paste the text in and I'll work with it."
            ),
        )
    reply = chat_reply(
        f"Ben sent this message and you could not classify it: "
        f"'{message}'. "
        "Check the conversation history above first. "
        "If it clearly refers to something just discussed "
        "(a link, a name, a request), respond to that directly "
        "instead of asking what he means. "
        "Only ask a clarifying question if nothing in the recent "
        "history explains it. "
        "Do not announce that you did not understand. "
        "Stay warm and in the conversation. 1-2 sentences.",
        history=_recent_history(intent.original_message.raw_text),
    )
    return HandlerResult(success=True, telegram_output=reply)


def handle(intent: RoutedIntent) -> HandlerResult:
    """Handle draft_communication and draft_outreach intents."""
    log_event(
        "generative", "handle", "start",
        detail=f"entity={intent.entity}, type={intent.comm_type}",
        file=__file__, function="handle",
    )
    entity = intent.entity
    comm_type = intent.comm_type or "email"
    request_text = intent.original_message.raw_text
    contact_context = None

    try:
        if entity:
            try:
                results = search_contacts(entity, limit=3)
                if isinstance(results, dict):
                    primary = results.get("primary")
                    if primary:
                        contact_context = get_contact_context(
                            str(primary.get("id", ""))
                        )
                elif results and len(results) == 1:
                    contact_context = get_contact_context(
                        str(results[0].get("id", ""))
                    )
            except Exception as exc:
                log_event(
                    "generative", "contact_lookup", "failure",
                    detail=str(exc), exc_info=exc,
                    file=__file__, function="handle",
                )

        draft = draft_communication(
            request_text, comm_type=comm_type, contact_context=contact_context
        )
        log_event(
            "generative", "handle", "success",
            detail=f"{comm_type} draft complete",
            file=__file__, function="handle",
        )
        return HandlerResult(success=True, telegram_output=draft)
    except Exception as exc:
        log_event(
            "generative", "handle", "failure",
            detail=str(exc), exc_info=exc,
            file=__file__, function="handle",
        )
        send_operator_alert(f"Generative handler failed: {exc}")
        return HandlerResult(
            success=False,
            telegram_output=FALLBACK_MESSAGE,
            error_details=str(exc),
        )
