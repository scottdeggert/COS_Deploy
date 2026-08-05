"""Follow Up Boss write operations -- kept separate from read-only tools/fub.py."""

from __future__ import annotations

import json

from tools.logger import log_event
from services.fub_client import fub_post, fub_put


def add_note_to_contact(contact_id: str, note_text: str) -> dict:
    """POST a note to a FUB contact."""
    log_event(
        "fub",
        "add_note",
        "start",
        contact_id=contact_id,
        file=__file__,
        function="add_note_to_contact",
    )
    payload = {"personId": int(contact_id), "body": note_text}
    try:
        result = fub_post("/notes", json=payload)
        log_event(
            "fub",
            "add_note",
            "success",
            contact_id=contact_id,
            file=__file__,
            function="add_note_to_contact",
        )
        return result
    except Exception as exc:
        log_event(
            "fub",
            "add_note",
            "failure",
            detail=str(exc),
            contact_id=contact_id,
            exc_info=exc,
            file=__file__,
            function="add_note_to_contact",
        )
        raise


def update_custom_field(contact_id: str, field_name: str, value: str) -> dict:
    """PUT a single custom field value onto a FUB contact."""
    log_event(
        "fub",
        "update_custom_field",
        "start",
        contact_id=contact_id,
        detail=field_name,
        file=__file__,
        function="update_custom_field",
    )
    payload = {field_name: value}
    try:
        result = fub_put(f"/people/{contact_id}", json=payload)
        log_event(
            "fub",
            "update_custom_field",
            "success",
            contact_id=contact_id,
            detail=field_name,
            file=__file__,
            function="update_custom_field",
        )
        return result
    except Exception as exc:
        log_event(
            "fub",
            "update_custom_field",
            "failure",
            detail=str(exc),
            contact_id=contact_id,
            exc_info=exc,
            file=__file__,
            function="update_custom_field",
        )
        raise


def enroll_in_action_plan(contact_id: str, plan_id: int) -> dict:
    """Enroll a FUB contact in an action plan."""
    log_event(
        "fub",
        "enroll_action_plan",
        "start",
        contact_id=contact_id,
        file=__file__,
        function="enroll_in_action_plan",
    )
    payload = {"personId": int(contact_id), "actionPlanId": int(plan_id)}
    try:
        result = fub_post("/actionPlansPeople", json=payload)
        try:
            body_detail = json.dumps(result, default=str)
        except (TypeError, ValueError):
            body_detail = str(result)
        if len(body_detail) > 300:
            body_detail = body_detail[:300]
        log_event(
            "fub",
            "enroll_action_plan",
            "success",
            detail=body_detail,
            contact_id=contact_id,
            file=__file__,
            function="enroll_in_action_plan",
        )
        return result
    except Exception as exc:
        log_event(
            "fub",
            "enroll_action_plan",
            "failure",
            detail=str(exc),
            contact_id=contact_id,
            exc_info=exc,
            file=__file__,
            function="enroll_in_action_plan",
        )
        raise


def add_tags_to_contact(contact_id: str, tags: list[str]) -> dict:
    """Add tags to a FUB contact without replacing existing tags."""
    if not tags:
        return {}

    log_event(
        "fub",
        "add_tags",
        "start",
        contact_id=contact_id,
        file=__file__,
        function="add_tags_to_contact",
    )
    payload = {"tags": tags}
    try:
        result = fub_put(f"/people/{contact_id}?mergeTags=true", json=payload)
        log_event(
            "fub",
            "add_tags",
            "success",
            contact_id=contact_id,
            file=__file__,
            function="add_tags_to_contact",
        )
        return result
    except Exception as exc:
        log_event(
            "fub",
            "add_tags",
            "failure",
            detail=str(exc),
            contact_id=contact_id,
            exc_info=exc,
            file=__file__,
            function="add_tags_to_contact",
        )
        raise


def create_contact(payload: dict) -> dict:
    """POST a new FUB person record. Caller supplies assignedUserId and fields."""
    log_event(
        "fub",
        "create_contact",
        "start",
        file=__file__,
        function="create_contact",
    )
    try:
        result = fub_post("/people", json=payload)
        contact_id = str((result or {}).get("id") or "")
        log_event(
            "fub",
            "create_contact",
            "success",
            contact_id=contact_id,
            file=__file__,
            function="create_contact",
        )
        return result
    except Exception as exc:
        log_event(
            "fub",
            "create_contact",
            "failure",
            detail=str(exc),
            exc_info=exc,
            file=__file__,
            function="create_contact",
        )
        raise


def send_fub_email(contact_id: str, subject: str, body: str) -> dict:
    """POST an email to a FUB contact."""
    log_event(
        "fub",
        "send_email",
        "start",
        contact_id=contact_id,
        file=__file__,
        function="send_fub_email",
    )
    payload = {
        "personId": int(contact_id),
        "subject": subject,
        "message": body,
        "isHtml": False,
    }
    try:
        result = fub_post("/emails", json=payload)
        log_event(
            "fub",
            "send_email",
            "success",
            contact_id=contact_id,
            file=__file__,
            function="send_fub_email",
        )
        return result
    except Exception as exc:
        log_event(
            "fub",
            "send_email",
            "failure",
            detail=str(exc),
            contact_id=contact_id,
            exc_info=exc,
            file=__file__,
            function="send_fub_email",
        )
        raise
