"""Brief request handler -- contact lookup by name or ID."""

from __future__ import annotations

from app.config import CLIENT_ID
from app.schemas import HandlerResult, RoutedIntent
from tools.fub import (
    SearchContactsDisambiguationResult,
    _contact_summary,
    _person_display_name,
    get_contact_by_id,
    search_contacts,
)
from tools.health import run_health_check
from tools.logger import log_event
from tools.telegram import send_inline_message, send_operator_alert

FALLBACK_MESSAGE = (
    "I ran into a problem pulling that brief. Check FUB directly: "
    "https://app.followupboss.com"
)


def _run_brief_for_contact(client_id: str, contact_id: str) -> str:
    """Run the CrewAI brief generation for a contact."""
    log_event(
        "cos_agent", "run_brief", "start",
        contact_id=contact_id,
        file=__file__, function="_run_brief_for_contact",
    )
    try:
        from agents.crewai.crew import run_brief as _run_brief
        result = _run_brief(client_id, contact_id)
        log_event(
            "cos_agent", "run_brief", "success",
            contact_id=contact_id,
            file=__file__, function="_run_brief_for_contact",
        )
        run_health_check(
            "brief",
            {
                "status": "success",
                "agent": "brief_generator",
                "action": "generate_brief",
                "contact_id": contact_id,
            },
        )
        return result
    except Exception as exc:
        run_health_check(
            "brief",
            {
                "status": "failure",
                "agent": "brief_generator",
                "action": "generate_brief",
                "detail": str(exc),
                "contact_id": contact_id,
            },
        )
        log_event(
            "cos_agent", "run_brief", "failure",
            detail=str(exc), contact_id=contact_id, exc_info=exc,
            file=__file__, function="_run_brief_for_contact",
        )
        return FALLBACK_MESSAGE


def _format_last_activity(last_activity: str | None) -> str:
    from datetime import datetime, timezone
    if not last_activity:
        return "no activity"
    try:
        value = str(last_activity)
        normalized = value.replace("Z", "+00:00") if value.endswith("Z") else value
        parsed = datetime.fromisoformat(normalized)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.date().isoformat()
    except (ValueError, AttributeError):
        return "no activity"


def _duplicate_merge_note(name: str, total_records: int) -> str:
    return (
        f"\n\nFound {total_records} records for {name}. "
        "Showing the most recent. Theresa can merge them in FUB."
    )


def _send_contact_disambiguation_prompt(
    chat_id: str, name: str, candidates: list[dict]
) -> None:
    buttons = []
    for candidate in candidates:
        contact_id = str(candidate.get("id", ""))
        stage = str(candidate.get("stage") or "Unknown")
        activity = _format_last_activity(candidate.get("lastActivity"))
        label = f"{candidate.get('name', name)} -- {activity} -- {stage}"
        if len(label) > 64:
            label = label[:61] + "..."
        buttons.append(
            [{"text": label, "callback_data": f"brief_pick:{contact_id}"}]
        )

    prompt = f"Found {len(candidates)} records for {name}. Which one?"
    send_inline_message(
        prompt,
        {"inline_keyboard": buttons},
        chat_id=chat_id,
    )


def _handle_disambiguation_result(
    client_id: str,
    chat_id: str,
    query: str,
    result: SearchContactsDisambiguationResult,
) -> HandlerResult:
    primary = result["primary"]
    duplicates_found = result["duplicates_found"]
    contact_id = str(primary.get("id", ""))
    name = _person_display_name(primary) or query

    if result["disambiguation_required"]:
        candidates = [_contact_summary(primary), *duplicates_found]
        _send_contact_disambiguation_prompt(chat_id, name, candidates)
        log_event(
            "bot", "name_lookup", "success",
            detail=f"{name} disambiguation prompt sent",
            file=__file__, function="_handle_disambiguation_result",
        )
        return HandlerResult(
            success=True,
            telegram_output=f"Found {len(candidates)} records for {name}. Which one?",
            operator_note=f"Disambiguation prompt sent for {name}",
        )

    log_event(
        "bot", "name_lookup", "success",
        detail=f"{name} -> {contact_id} (auto-disambiguated)",
        file=__file__, function="_handle_disambiguation_result",
    )
    brief = _run_brief_for_contact(client_id, contact_id)
    if duplicates_found:
        total_records = 1 + len(duplicates_found)
        brief += _duplicate_merge_note(name, total_records)
    return HandlerResult(success=True, telegram_output=brief)


def handle(intent: RoutedIntent) -> HandlerResult:
    """Handle brief_request intents."""
    log_event(
        "brief", "handle", "start",
        detail=f"entity={intent.entity}",
        file=__file__, function="handle",
    )
    chat_id = intent.original_message.chat_id
    entity = intent.entity

    try:
        if entity and entity.isdigit():
            contact_id = entity
            log_event(
                "bot", "brief_requested", "start",
                contact_id=contact_id,
                file=__file__, function="handle",
            )
            brief_text = _run_brief_for_contact(CLIENT_ID, contact_id)
            return HandlerResult(success=True, telegram_output=brief_text)

        if entity:
            query = entity.strip()
            log_event(
                "bot", "name_lookup", "start",
                detail=query,
                file=__file__, function="handle",
            )
            results = search_contacts(query, limit=5)
            if isinstance(results, dict):
                return _handle_disambiguation_result(
                    CLIENT_ID, chat_id, query, results
                )
            if not results:
                return HandlerResult(
                    success=True,
                    telegram_output=f"No contact found for '{query}'. Try a contact ID.",
                )
            if len(results) > 1:
                lines = [f"Found {len(results)} matches. Which one?"]
                for p in results:
                    name = f"{p.get('firstName', '')} {p.get('lastName', '')}".strip()
                    cid = str(p.get("id", ""))
                    lines.append(f"  brief {cid} -- {name}")
                return HandlerResult(success=True, telegram_output="\n".join(lines))
            contact = results[0]
            contact_id = str(contact.get("id", ""))
            brief_text = _run_brief_for_contact(CLIENT_ID, contact_id)
            return HandlerResult(success=True, telegram_output=brief_text)

        return HandlerResult(
            success=True,
            telegram_output="Who would you like a brief on? Send me a name or contact ID.",
        )
    except Exception as exc:
        log_event(
            "brief", "handle", "failure",
            detail=str(exc), exc_info=exc,
            file=__file__, function="handle",
        )
        send_operator_alert(f"Brief handler failed: {exc}")
        return HandlerResult(
            success=False,
            telegram_output=FALLBACK_MESSAGE,
            error_details=str(exc),
        )
