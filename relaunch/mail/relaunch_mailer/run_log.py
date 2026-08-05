"""Timestamped run-log CSV output."""

from __future__ import annotations

import csv
from datetime import datetime, timezone
from pathlib import Path

from relaunch_mailer.filter import ProcessedRow


LOG_COLUMNS = [
    "property_address",
    "recipient_name",
    "mail_address_used",
    "action",
    "lob_letter_id",
    "http_status",
    "error",
]


def log_path(log_dir: Path) -> Path:
    log_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return log_dir / f"run-log_{stamp}.csv"


def write_run_log(
    rows: list[ProcessedRow],
    path: Path,
    *,
    lob_results: dict[str, tuple[str, int | None, str]] | None = None,
) -> Path:
    """
    Write one row per property. lob_results maps property_address ->
    (letter_id, http_status, error).
    """
    lob_results = lob_results or {}
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=LOG_COLUMNS)
        writer.writeheader()
        for row in rows:
            letter_id, http_status, extra_error = lob_results.get(
                row.property_address, ("", "", "")
            )
            errors = [e for e in [row.error, extra_error] if e]
            writer.writerow(
                {
                    "property_address": row.property_address,
                    "recipient_name": row.recipient_name,
                    "mail_address_used": row.mail_address_used,
                    "action": row.action.value,
                    "lob_letter_id": letter_id,
                    "http_status": http_status if http_status != "" else "",
                    "error": "; ".join(errors),
                }
            )
    return path
