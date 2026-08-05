"""CMA job registry backed by logs/cma_registry.json.

Keyed by job_id. Atomic read/write via tools/atomic_json.
"""

from __future__ import annotations

import threading
from datetime import datetime, timezone
from typing import Any

from app.config import LOGS_DIR
from app.schemas import CmaJob
from tools.atomic_json import load_json_dict, save_json_atomic
from tools.logger import log_event

REGISTRY_PATH = LOGS_DIR / "cma_registry.json"
_lock = threading.Lock()


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load_unlocked() -> dict[str, Any]:
    return load_json_dict(REGISTRY_PATH, default={})


def _save_unlocked(registry: dict[str, Any]) -> None:
    save_json_atomic(REGISTRY_PATH, registry, prefix="cma_registry.")


def _normalize_job_raw(raw: dict[str, Any]) -> dict[str, Any]:
    """Ensure legacy records validate after schema field additions."""
    out = dict(raw)
    if "reply_chat_id" not in out:
        out["reply_chat_id"] = ""
    # Pre-pattern-3 contact jobs were always delivery-eligible.
    if "send_target_contact_id" not in out:
        contact_id = out.get("contact_id")
        out["send_target_contact_id"] = contact_id if contact_id else None
    return out


def _validate_job_raw(raw: dict[str, Any], context: str) -> CmaJob | None:
    try:
        return CmaJob.model_validate(_normalize_job_raw(raw))
    except Exception as exc:
        log_event(
            "cma_registry",
            context,
            "failure",
            detail=f"invalid job record: {exc}",
            file=__file__,
            function=context,
        )
        return None


def upsert_job(job: CmaJob) -> None:
    """Insert or replace a CmaJob by job_id."""
    with _lock:
        registry = _load_unlocked()
        registry[job.job_id] = job.model_dump()
        _save_unlocked(registry)


def get_job(job_id: str) -> CmaJob | None:
    """Return the job for job_id, or None if missing."""
    with _lock:
        registry = _load_unlocked()
        raw = registry.get(job_id)
    if not isinstance(raw, dict):
        return None
    return _validate_job_raw(raw, "get_job")


def get_job_by_token(token: str) -> CmaJob | None:
    """Return the job whose token matches, or None."""
    with _lock:
        registry = _load_unlocked()
        for raw in registry.values():
            if isinstance(raw, dict) and raw.get("token") == token:
                return _validate_job_raw(raw, "get_job_by_token")
    return None


def mark_ready(
    job_id: str,
    *,
    source_pdf_url: str,
    archived_pdf_path: str,
    tracking_url: str,
) -> CmaJob | None:
    """Mark a pending job ready. Returns updated job, or None if unknown."""
    with _lock:
        registry = _load_unlocked()
        raw = registry.get(job_id)
        if not isinstance(raw, dict):
            return None
        job = _validate_job_raw(raw, "mark_ready")
        if job is None:
            return None
        job.status = "ready"
        job.source_pdf_url = source_pdf_url
        job.archived_pdf_path = archived_pdf_path
        job.tracking_url = tracking_url
        job.ready_at = _utc_now()
        registry[job_id] = job.model_dump()
        _save_unlocked(registry)
        return job


def mark_failed(job_id: str) -> CmaJob | None:
    """Mark a job failed. Returns updated job, or None if unknown."""
    with _lock:
        registry = _load_unlocked()
        raw = registry.get(job_id)
        if not isinstance(raw, dict):
            return None
        job = _validate_job_raw(raw, "mark_failed")
        if job is None:
            return None
        job.status = "failed"
        registry[job_id] = job.model_dump()
        _save_unlocked(registry)
        return job


def record_open(token: str) -> CmaJob | None:
    """Increment open_count and set last_opened_at. Returns updated job or None."""
    with _lock:
        registry = _load_unlocked()
        job_id = None
        raw = None
        for key, value in registry.items():
            if isinstance(value, dict) and value.get("token") == token:
                job_id = key
                raw = value
                break
        if job_id is None or not isinstance(raw, dict):
            return None
        job = _validate_job_raw(raw, "record_open")
        if job is None:
            return None
        job.open_count = int(job.open_count or 0) + 1
        job.last_opened_at = _utc_now()
        registry[job_id] = job.model_dump()
        _save_unlocked(registry)
        return job
