"""Generative writing handler -- draft_communication and draft_outreach."""

from __future__ import annotations

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

HELP_REPLY = (
    "Here's what I can do:\n"
    "* brief [name] or [ID] -- pull a contact brief\n"
    "* draft an email to [name] about [topic]\n"
    "* hot leads -- see your warm pipeline going cold\n"
    "* status -- check recent agent log"
)


def _load_soul_config() -> dict:
    soul_path = CLIENTS_DIR / CLIENT_ID / "soul.yaml"
    with soul_path.open(encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return data if isinstance(data, dict) else {}


def handle_greeting(intent: RoutedIntent) -> HandlerResult:
    """Handle greeting intents."""
    message = intent.original_message.raw_text
    reply = chat_reply(
        f"Ben just greeted you with: '{message}'. "
        "Respond warmly and briefly. Open the door for what he needs. "
        "1-2 sentences. Vary your phrasing naturally."
    )
    return HandlerResult(success=True, telegram_output=reply)


def handle_identity(intent: RoutedIntent) -> HandlerResult:
    """Handle identity_query intents."""
    soul = _load_soul_config()
    name = soul.get("name", "Chief of Staff")
    personality = str(soul.get("personality_summary", "")).strip()
    reply = f"I'm Ben's {name}. {personality}"
    return HandlerResult(success=True, telegram_output=reply)


def handle_help(intent: RoutedIntent) -> HandlerResult:
    """Handle help_request intents."""
    return HandlerResult(success=True, telegram_output=HELP_REPLY)


def handle_fallback(intent: RoutedIntent) -> HandlerResult:
    """Handle unknown or unclassified intents."""
    message = intent.original_message.raw_text
    reply = chat_reply(
        f"Ben sent this message and you could not classify it: "
        f"'{message}'. "
        "Do not announce that you did not understand. "
        "Ask a clarifying question or reflect back what you think he might mean. "
        "Stay warm and in the conversation. 1-2 sentences."
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
