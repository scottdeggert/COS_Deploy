"""
FUB writeback after a successful live Lob send (--send-all only).

Upserts a dormant Ben-assigned contact and tags it for attribution:
  source:direct-mail, mailer:expired-{batch_id}, expired-listing

Must not run on --sandbox-test. Callers: relaunch.mail.send.run_send_all and
mailer.py --send-all only.

Failures are queued under relaunch/logs/fub_writeback_queue.json and retried
on the next cron tick. Writeback never blocks the Lob send path.
"""

from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

from tools.fub import search_contacts
from tools.fub_write import add_tags_to_contact, create_contact

RELAUNCH_ROOT = Path(__file__).resolve().parent.parent
REPO_ROOT = RELAUNCH_ROOT.parent
LOGS_DIR = RELAUNCH_ROOT / "logs"
QUEUE_PATH = LOGS_DIR / "fub_writeback_queue.json"
PIPELINE_LOG = LOGS_DIR / "pipeline.log"


def _log(message: str) -> None:
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    line = f"[{stamp}] fub_writeback {message}\n"
    with PIPELINE_LOG.open("a", encoding="utf-8") as fh:
        fh.write(line)
    print(line, end="")


def _load_fub_user_id() -> int:
    client_id = os.environ.get("CLIENT_ID", "ben-olsen").strip() or "ben-olsen"
    path = REPO_ROOT / "clients" / client_id / "fub-config.yaml"
    with path.open(encoding="utf-8") as fh:
        cfg = yaml.safe_load(fh) or {}
    return int(cfg.get("fub_user_id") or 1)


def _load_queue() -> list[dict[str, Any]]:
    if not QUEUE_PATH.is_file():
        return []
    try:
        payload = json.loads(QUEUE_PATH.read_text(encoding="utf-8"))
        return payload if isinstance(payload, list) else []
    except (OSError, json.JSONDecodeError, TypeError):
        return []


def _save_queue(items: list[dict[str, Any]]) -> None:
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(
        dir=str(LOGS_DIR),
        prefix="fub_writeback_queue.",
        suffix=".tmp",
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(items, fh, indent=2)
            fh.write("\n")
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(temp_name, QUEUE_PATH)
    except Exception:
        try:
            os.unlink(temp_name)
        except OSError:
            pass
        raise


def _enqueue(item: dict[str, Any]) -> None:
    queue = _load_queue()
    queue.append(item)
    _save_queue(queue)


def _norm_name(first: str, last: str) -> str:
    return " ".join(f"{first} {last}".split()).casefold()


def _find_existing_contact_id(first: str, last: str) -> str | None:
    """Best-effort exact name match among Ben-assigned search hits."""
    results = search_contacts(f"{first} {last}".strip(), limit=25)
    people = []
    if isinstance(results, dict):
        primary = results.get("primary") or {}
        if primary.get("id"):
            people.append(primary)
    elif isinstance(results, list):
        people = results

    target = _norm_name(first, last)
    for person in people:
        candidate = _norm_name(
            str(person.get("firstName") or ""),
            str(person.get("lastName") or ""),
        )
        if candidate == target:
            return str(person.get("id"))
    return None


def _attribution_tags(batch_id: str) -> list[str]:
    return [
        "source:direct-mail",
        f"mailer:expired-{batch_id}",
        "expired-listing",
    ]


def _build_create_payload(item: dict[str, Any]) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "firstName": item["first_name"],
        "lastName": item["last_name"],
        "assignedUserId": _load_fub_user_id(),
        "tags": _attribution_tags(item["batch_id"]),
    }
    street = (item.get("street") or "").strip()
    city = (item.get("city") or "").strip()
    state = (item.get("state") or "CA").strip()
    zip_code = (item.get("zip") or "").strip()
    if street:
        payload["addresses"] = [
            {
                "type": "home",
                "street": street,
                "city": city,
                "state": state,
                "code": zip_code,
            }
        ]
    return payload


def writeback_sent_row(item: dict[str, Any]) -> str:
    """
    Upsert contact + tags for one SENT row. Returns contact_id on success.
    Raises on failure (caller enqueues).
    """
    first = (item.get("first_name") or "").strip()
    last = (item.get("last_name") or "").strip()
    if not first:
        raise ValueError("missing first_name for writeback")

    contact_id = _find_existing_contact_id(first, last)
    if contact_id:
        add_tags_to_contact(contact_id, _attribution_tags(item["batch_id"]))
        return contact_id

    created = create_contact(_build_create_payload(item))
    contact_id = str((created or {}).get("id") or "")
    if not contact_id:
        raise RuntimeError("create_contact returned no id")
    # Tags are included on create; merge again for idempotency.
    add_tags_to_contact(contact_id, _attribution_tags(item["batch_id"]))
    return contact_id


def queue_writeback_for_sent(
    *,
    batch_id: str,
    property_address: str,
    first_name: str,
    last_name: str,
    street: str,
    city: str,
    state: str,
    zip_code: str,
    lob_letter_id: str,
) -> None:
    """Enqueue then attempt immediate writeback; failures stay queued."""
    item = {
        "batch_id": batch_id,
        "property_address": property_address,
        "first_name": first_name,
        "last_name": last_name,
        "street": street,
        "city": city,
        "state": state,
        "zip": zip_code,
        "lob_letter_id": lob_letter_id,
        "attempts": 0,
        "last_error": "",
        "queued_at": datetime.now(timezone.utc).isoformat(),
    }
    try:
        contact_id = writeback_sent_row(item)
        _log(
            f"success property={property_address} contact_id={contact_id} "
            f"batch_id={batch_id} lob_letter_id={lob_letter_id}"
        )
    except Exception as exc:
        item["attempts"] = 1
        item["last_error"] = str(exc)
        _enqueue(item)
        _log(
            f"queued property={property_address} batch_id={batch_id} "
            f"error={exc}"
        )


def retry_pending_writebacks() -> dict[str, int]:
    """Retry queued writebacks. Safe to call on every cron tick."""
    queue = _load_queue()
    if not queue:
        return {"pending": 0, "success": 0, "failed": 0}

    remaining: list[dict[str, Any]] = []
    success = 0
    failed = 0
    for item in queue:
        try:
            contact_id = writeback_sent_row(item)
            success += 1
            _log(
                f"retry_success property={item.get('property_address')} "
                f"contact_id={contact_id}"
            )
        except Exception as exc:
            item["attempts"] = int(item.get("attempts") or 0) + 1
            item["last_error"] = str(exc)
            remaining.append(item)
            failed += 1
            _log(
                f"retry_failure property={item.get('property_address')} "
                f"attempts={item['attempts']} error={exc}"
            )

    _save_queue(remaining)
    return {"pending": len(remaining), "success": success, "failed": failed}
