"""Internal data contracts between layers.

These models are the only way the transport, router, and handler
layers communicate. Do not pass raw strings or dicts between layers.

Adding a new intent type: add it to the Literal in RoutedIntent.intent_type.
Adding a new callback action: add it to InboundCallback.data format docs.
"""

from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel


class InboundMessage(BaseModel):
    """Raw inbound Telegram message, normalized from the polling loop."""
    chat_id: str
    raw_text: str
    timestamp: int
    client_id: str  # tenant identifier, e.g. "ben-olsen"


class InboundCallback(BaseModel):
    """Inline keyboard button press from a Telegram message."""
    chat_id: str
    callback_query_id: str
    data: str           # format: "action:id", e.g. "approve:31735" or "send_cma:{job_id}"
    message_id: int     # ID of the original message with the keyboard
    client_id: str


class RoutedIntent(BaseModel):
    """Result of Haiku intent classification. Passed to handlers."""
    original_message: InboundMessage
    intent_type: Literal[
        "brief_request",
        "draft_communication",
        "draft_outreach",
        "hot_leads",
        "hot_leads_list",
        "status_check",
        "digest_test",
        "greeting",
        "identity_query",
        "help_request",
        "cma_request",
        "unknown",
    ]
    entity: Optional[str] = None        # contact name/ID, or address (cma_request: either)
    entity_address: Optional[str] = None  # cma_request pattern 3: property address when entity is a contact
    send_intent: Optional[bool] = None  # cma_request: delivery phrasing detected (send/email/get this to)
    comm_type: Optional[str] = None     # email | sms | note (generative intents)
    confidence: float = 0.0


class CmaJob(BaseModel):
    """Tracked Cloud CMA generation job. Persisted in logs/cma_registry.json."""
    job_id: str
    reply_chat_id: str
    contact_id: Optional[str] = None  # filing contact for custom field write
    send_target_contact_id: Optional[str] = None  # delivery recipient; None = no send button
    address: str
    title: Optional[str] = None
    token: str
    status: Literal["pending", "ready", "failed"]
    source_pdf_url: Optional[str] = None
    archived_pdf_path: Optional[str] = None
    tracking_url: Optional[str] = None
    open_count: int = 0
    created_at: str
    ready_at: Optional[str] = None
    last_opened_at: Optional[str] = None


class HandlerResult(BaseModel):
    """Standard return from every handler. Transport layer reads this."""
    success: bool
    telegram_output: str            # what Ben receives -- always set
    operator_note: Optional[str] = None   # sent to monitor if set
    fub_writes: int = 0             # count of FUB mutations performed
    error_details: Optional[str] = None   # logged, never shown to Ben
