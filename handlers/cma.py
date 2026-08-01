"""CMA request handler -- impromptu Cloud CMA generation for Ben."""

from __future__ import annotations

import secrets
import uuid
from datetime import datetime, timezone

from app.config import CMA_REDIRECT_BASE
from app.schemas import CmaJob, HandlerResult, RoutedIntent
from tools.cloudcma import request_quick_cma
from tools.cma_registry import mark_failed, upsert_job
from tools.draft_communication import chat_reply
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


def handle(intent: RoutedIntent) -> HandlerResult:
    """Handle cma_request: mint job, call Cloud CMA, acknowledge Ben."""
    address = (intent.entity or "").strip()
    log_event(
        "cma",
        "handle",
        "start",
        detail=f"address_len={len(address)}",
        file=__file__,
        function="handle",
    )

    if not address:
        return HandlerResult(success=False, telegram_output=MISSING_ADDRESS_MESSAGE)

    job_id = str(uuid.uuid4())
    token = secrets.token_urlsafe(16)
    now = datetime.now(timezone.utc).isoformat()
    job = CmaJob(
        job_id=job_id,
        reply_chat_id=intent.original_message.chat_id,
        contact_id=None,
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
            file=__file__,
            function="handle",
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
            file=__file__,
            function="handle",
        )
        return HandlerResult(
            success=False,
            telegram_output=FALLBACK_MESSAGE,
            error_details=result.detail,
        )

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
        file=__file__,
        function="handle",
    )
    return HandlerResult(success=True, telegram_output=reply)
