"""CMA request handler -- impromptu Cloud CMA generation for Ben."""

from __future__ import annotations

import re
import secrets
import uuid
from datetime import datetime, timezone

from app.config import CMA_REDIRECT_BASE
from app.schemas import CmaJob, HandlerResult, RoutedIntent
from tools.cloudcma import request_quick_cma
from tools.cma_registry import mark_failed, upsert_job
from tools.draft_communication import chat_reply
from tools.fub import get_contact_by_id, search_contacts
from tools.logger import log_event
from tools.telegram import send_operator_alert

FALLBACK_MESSAGE = (
    "I could not start that CMA. Try again in a minute, or check the address."
)

OUT_OF_MLS_MESSAGE = (
    "I could not pull comps for that address. "
    "It may be outside Ben's MLS coverage area."
)

MISSING_ADDRESS_MESSAGE = (
    "I need a street address to generate a CMA. "
    "Try again with something like: Generate a CMA for 123 Main St, City, CA."
)

NO_CONTACT_ADDRESS_MESSAGE = (
    "That contact has no usable property address in FUB. "
    "Add an address on the contact, or send the street address directly."
)

NO_CONTACT_MESSAGE = (
    "No contact found for that name. Try a contact ID, or send the property address."
)

# Street address starts with a house number then whitespace (Phase 1 path).
_ADDRESS_PATTERN = re.compile(r"^\d+\s+\S+")


def _looks_like_address(entity: str) -> bool:
    return bool(_ADDRESS_PATTERN.match(entity.strip()))


def _format_address_from_contact(contact: dict) -> str | None:
    """Return a Cloud CMA-usable address from the FUB contact, or None."""
    addresses = contact.get("addresses") or []
    if not isinstance(addresses, list):
        return None
    for addr in addresses:
        if not isinstance(addr, dict):
            continue
        street = str(addr.get("street") or "").strip()
        if not street:
            continue
        city = str(addr.get("city") or "").strip()
        state = str(addr.get("state") or "").strip()
        code = str(addr.get("code") or "").strip()
        locality = ", ".join(p for p in (city, f"{state} {code}".strip()) if p)
        if locality:
            return f"{street}, {locality}"
        return street
    return None


def _resolve_contact(entity: str) -> tuple[dict | None, HandlerResult | None]:
    """Resolve entity to a FUB contact via search_contacts / get_contact_by_id.

    Returns (contact, None) on success, or (None, HandlerResult) when Ben
    needs a follow-up (not found, multi-match). Same lookup as brief_request.
    """
    if entity.isdigit():
        try:
            return get_contact_by_id(entity), None
        except Exception:
            return None, HandlerResult(
                success=False,
                telegram_output=NO_CONTACT_MESSAGE,
            )

    results = search_contacts(entity, limit=5)
    if isinstance(results, dict):
        primary = results.get("primary")
        duplicates = results.get("duplicates_found") or []
        if results.get("disambiguation_required") and primary:
            name = entity
            lines = [f"Found {1 + len(duplicates)} records for {name}. Which one?"]
            for candidate in [primary, *duplicates]:
                cid = str(candidate.get("id", ""))
                display = (
                    f"{candidate.get('firstName', '')} "
                    f"{candidate.get('lastName', '')}"
                ).strip() or str(candidate.get("name", name))
                lines.append(f"  CMA for {cid} -- {display}")
            return None, HandlerResult(success=True, telegram_output="\n".join(lines))
        if primary:
            return primary, None
        return None, HandlerResult(success=False, telegram_output=NO_CONTACT_MESSAGE)

    if not results:
        return None, HandlerResult(success=False, telegram_output=NO_CONTACT_MESSAGE)

    if len(results) > 1:
        lines = [f"Found {len(results)} matches. Which one?"]
        for person in results:
            name = f"{person.get('firstName', '')} {person.get('lastName', '')}".strip()
            cid = str(person.get("id", ""))
            lines.append(f"  CMA for {cid} -- {name}")
        return None, HandlerResult(success=True, telegram_output="\n".join(lines))

    return results[0], None


def _start_cma_job(
    *,
    address: str,
    reply_chat_id: str,
    contact_id: str | None,
    send_target_contact_id: str | None,
) -> HandlerResult:
    """Mint job, call Cloud CMA, acknowledge Ben. Shared by all paths."""
    job_id = str(uuid.uuid4())
    token = secrets.token_urlsafe(16)
    now = datetime.now(timezone.utc).isoformat()
    job = CmaJob(
        job_id=job_id,
        reply_chat_id=reply_chat_id,
        contact_id=contact_id,
        send_target_contact_id=send_target_contact_id,
        address=address,
        title=None,
        token=token,
        status="pending",
        source_pdf_url=None,
        archived_pdf_path=None,
        tracking_url=None,
        open_count=0,
        created_at=now,
        ready_at=None,
        last_opened_at=None,
    )
    upsert_job(job)

    callback_url = f"{CMA_REDIRECT_BASE.rstrip('/')}/cma/callback"
    result = request_quick_cma(
        address=address,
        job_id=job_id,
        callback_url=callback_url,
    )

    if result.failure_kind == "out_of_mls":
        mark_failed(job_id)
        log_event(
            "cma",
            "handle",
            "fallback",
            detail=f"out_of_mls job_id={job_id}",
            contact_id=contact_id or "",
            file=__file__,
            function="_start_cma_job",
        )
        return HandlerResult(success=False, telegram_output=OUT_OF_MLS_MESSAGE)

    if not result.ok:
        mark_failed(job_id)
        send_operator_alert(f"CMA request failed job_id={job_id} kind={result.failure_kind}")
        log_event(
            "cma",
            "handle",
            "failure",
            detail=f"job_id={job_id} kind={result.failure_kind}",
            contact_id=contact_id or "",
            file=__file__,
            function="_start_cma_job",
        )
        return HandlerResult(
            success=False,
            telegram_output=FALLBACK_MESSAGE,
            error_details=result.detail,
        )

    if contact_id:
        reply = chat_reply(
            f"Ben asked you to generate a CMA for contact {contact_id} "
            f"at this address: {address}. "
            "Acknowledge briefly that you are on it and will send the link when "
            "the report is ready. 1-2 sentences. Do not invent a link."
        )
    else:
        reply = chat_reply(
            f"Ben asked you to generate a CMA for this address: {address}. "
            "Acknowledge briefly that you are on it and will send the link when "
            "the report is ready. 1-2 sentences. Do not invent a link."
        )
    log_event(
        "cma",
        "handle",
        "success",
        detail=f"job_id={job_id}",
        contact_id=contact_id or "",
        file=__file__,
        function="_start_cma_job",
    )
    return HandlerResult(success=True, telegram_output=reply)


def _resolve_contact_for_cma(entity: str) -> tuple[str | None, HandlerResult | None]:
    """Resolve entity to contact_id, or return an early HandlerResult."""
    contact, early = _resolve_contact(entity)
    if early is not None:
        return None, early
    assert contact is not None
    contact_id = str(contact.get("id", ""))
    if not contact_id:
        return None, HandlerResult(success=False, telegram_output=NO_CONTACT_MESSAGE)
    return contact_id, None


def handle(intent: RoutedIntent) -> HandlerResult:
    """Handle cma_request: address-only, contact-based, or contact + address."""
    entity = (intent.entity or "").strip()
    entity_address = (intent.entity_address or "").strip()
    log_event(
        "cma",
        "handle",
        "start",
        detail=f"entity_len={len(entity)} entity_address_len={len(entity_address)}",
        file=__file__,
        function="handle",
    )

    if not entity:
        return HandlerResult(success=False, telegram_output=MISSING_ADDRESS_MESSAGE)

    # Pattern 3: named contact + separate property address from the utterance.
    if entity_address:
        contact_id, early = _resolve_contact_for_cma(entity)
        if early is not None:
            return early
        assert contact_id is not None
        # Delivery language -> send target is the named contact; look-only leaves it unset.
        send_target = contact_id if intent.send_intent is True else None
        return _start_cma_job(
            address=entity_address,
            reply_chat_id=intent.original_message.chat_id,
            contact_id=contact_id,
            send_target_contact_id=send_target,
        )

    # Contact path: numeric ID, or a name that does not look like a street address.
    # No entity_address: preserve shipped behavior (delivery-eligible send button).
    if entity.isdigit() or not _looks_like_address(entity):
        contact, early = _resolve_contact(entity)
        if early is not None:
            return early
        assert contact is not None
        contact_id = str(contact.get("id", ""))
        if not contact_id:
            return HandlerResult(success=False, telegram_output=NO_CONTACT_MESSAGE)
        # Prefer a fresh full record so addresses are present.
        if not contact.get("addresses"):
            try:
                contact = get_contact_by_id(contact_id)
            except Exception as exc:
                log_event(
                    "cma",
                    "handle",
                    "failure",
                    detail=str(exc),
                    contact_id=contact_id,
                    exc_info=exc,
                    file=__file__,
                    function="handle",
                )
                send_operator_alert(f"CMA contact lookup failed: {exc}")
                return HandlerResult(
                    success=False,
                    telegram_output=FALLBACK_MESSAGE,
                    error_details=str(exc),
                )
        address = _format_address_from_contact(contact)
        if not address:
            log_event(
                "cma",
                "handle",
                "fallback",
                detail="no usable address on contact",
                contact_id=contact_id,
                file=__file__,
                function="handle",
            )
            return HandlerResult(
                success=False,
                telegram_output=NO_CONTACT_ADDRESS_MESSAGE,
            )
        return _start_cma_job(
            address=address,
            reply_chat_id=intent.original_message.chat_id,
            contact_id=contact_id,
            send_target_contact_id=contact_id,
        )

    # Phase 1 address-only path (unchanged behavior).
    return _start_cma_job(
        address=entity,
        reply_chat_id=intent.original_message.chat_id,
        contact_id=None,
        send_target_contact_id=None,
    )
