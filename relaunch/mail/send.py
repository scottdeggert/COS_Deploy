"""
relaunch.mail.send — Lob send entrypoint for APPROVE SEND callbacks.

Default mode is sandbox (test_ key, one letter). --send-all against a live_
key is blocked until a confirmed sandbox_test success is logged in
relaunch/logs/pipeline.log.

--addresses sends only the listed property addresses (CLI resend path).
That path does not touch pipeline_state.json or the APPROVE SEND guard.
"""

from __future__ import annotations

import argparse
import csv
import os
import re
import sys
from pathlib import Path

from dotenv import load_dotenv

RELAUNCH_ROOT = Path(__file__).resolve().parent.parent
REPO_ROOT = RELAUNCH_ROOT.parent
MAIL_DIR = Path(__file__).resolve().parent
LOGS_DIR = RELAUNCH_ROOT / "logs"
BATCHES_DIR = RELAUNCH_ROOT / "batches"
PIPELINE_LOG = LOGS_DIR / "pipeline.log"

# Allow relaunch_mailer.* imports whether run as -m or as a script.
if str(MAIL_DIR) not in sys.path:
    sys.path.insert(0, str(MAIL_DIR))
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from relaunch_mailer.config import Settings  # noqa: E402
from relaunch_mailer.filter import (  # noqa: E402
    Action,
    LOB_TO_NAME_MAX,
    ProcessedRow,
    process_rows,
)
from relaunch_mailer.lob_client import (  # noqa: E402
    build_letter_payload,
    print_send_result,
    send_letter,
)
from relaunch_mailer.run_log import log_path, write_run_log  # noqa: E402


def _load_env() -> None:
    load_dotenv(RELAUNCH_ROOT / ".env", override=True)
    load_dotenv(REPO_ROOT / ".env", override=False)


def _log(message: str) -> None:
    from datetime import datetime
    from zoneinfo import ZoneInfo

    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(tz=ZoneInfo("America/Los_Angeles")).strftime(
        "%Y-%m-%d %H:%M:%S %Z"
    )
    line = f"[{stamp}] {message}\n"
    with PIPELINE_LOG.open("a", encoding="utf-8") as fh:
        fh.write(line)
    print(line, end="")


def _sandbox_confirmed() -> bool:
    """True when pipeline.log records a successful sandbox Lob send."""
    if not PIPELINE_LOG.is_file():
        return False
    text = PIPELINE_LOG.read_text(encoding="utf-8", errors="replace")
    return "sandbox_test success letter_id=" in text


def _batch_paths(batch_id: str) -> tuple[Path, Path]:
    batch_dir = BATCHES_DIR / batch_id
    csv_path = batch_dir / "properties.csv"
    pdf_dir = batch_dir / "output"
    if not csv_path.is_file():
        raise FileNotFoundError(f"Batch CSV missing: {csv_path}")
    if not pdf_dir.is_dir():
        raise FileNotFoundError(f"Batch PDF dir missing: {pdf_dir}")
    return csv_path, pdf_dir


def _load_rows(csv_path: Path) -> list[dict[str, str]]:
    with csv_path.open(newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def _norm_address(value: str) -> str:
    text = (value or "").casefold().replace(".", "")
    return re.sub(r"\s+", " ", text).strip()


def _select_address_rows(
    results: list[ProcessedRow],
    addresses: list[str],
) -> tuple[list[ProcessedRow], list[str]]:
    """Match requested addresses to SENT rows. Returns (matched, unmatched)."""
    by_norm = {
        _norm_address(row.property_address): row
        for row in results
        if row.action == Action.SENT
    }
    matched: list[ProcessedRow] = []
    unmatched: list[str] = []
    seen: set[str] = set()
    for raw in addresses:
        key = _norm_address(raw)
        if not key:
            continue
        row = by_norm.get(key)
        if row is None:
            unmatched.append(raw)
            continue
        if key in seen:
            continue
        seen.add(key)
        matched.append(row)
    return matched, unmatched


def run_sandbox_test(batch_id: str) -> int:
    csv_path, pdf_dir = _batch_paths(batch_id)
    os.environ["CSV_PATH"] = str(csv_path)
    os.environ["PDF_DIR"] = str(pdf_dir)
    os.environ["LOG_DIR"] = str(LOGS_DIR)

    settings = Settings.from_env_optional_lob()
    if not settings.lob_api_key.startswith("test_"):
        _log("sandbox_test refused: LOB_API_KEY is not a test_ key")
        print("ERROR: sandbox send requires a Lob test_ key", file=sys.stderr)
        return 1

    rows = _load_rows(csv_path)
    results = process_rows(rows, pdf_dir)
    send_rows = [r for r in results if r.action == Action.SENT]
    if not send_rows:
        _log(f"sandbox_test failed batch_id={batch_id} reason=no_sent_rows")
        print("ERROR: No SENT rows in batch; cannot sandbox send.", file=sys.stderr)
        return 1

    target = send_rows[0]
    _log(
        f"sandbox_test start batch_id={batch_id} "
        f"property={target.property_address}"
    )
    print(f"\n=== Sandbox Test — batch {batch_id} ===")
    print(f"Property: {target.property_address}")
    print(f"Recipient: {target.recipient_name}")
    print(f"Mail to: {target.mail_address_used}")
    print(f"PDF: {target.pdf_path}")

    lob_result = send_letter(target, settings)
    print_send_result(lob_result)

    lob_map = {
        target.property_address: (
            lob_result.letter_id,
            lob_result.http_status,
            lob_result.error,
        )
    }
    out = write_run_log(results, log_path(LOGS_DIR), lob_results=lob_map)
    print(f"\nRun log written: {out}")

    if lob_result.letter_id:
        _log(
            f"sandbox_test success letter_id={lob_result.letter_id} "
            f"batch_id={batch_id} property={target.property_address} "
            f"run_log={out}"
        )
        print(f"\nSandbox test succeeded: letter_id={lob_result.letter_id}")
        return 0

    _log(
        f"sandbox_test failure batch_id={batch_id} "
        f"http={lob_result.http_status} error={lob_result.error[:200]}"
    )
    return 1


def run_send_all(batch_id: str) -> int:
    csv_path, pdf_dir = _batch_paths(batch_id)
    os.environ["CSV_PATH"] = str(csv_path)
    os.environ["PDF_DIR"] = str(pdf_dir)
    os.environ["LOG_DIR"] = str(LOGS_DIR)

    settings = Settings.from_env_optional_lob()
    if settings.lob_api_key.startswith("test_"):
        print(
            "ERROR: --send-all refuses to run with a sandbox (test_) key.",
            file=sys.stderr,
        )
        return 1
    if not settings.lob_api_key.startswith("live_"):
        print("ERROR: --send-all requires a live_ Lob key.", file=sys.stderr)
        return 1
    if not _sandbox_confirmed():
        _log(
            "send_all refused: no confirmed sandbox_test success in pipeline.log"
        )
        print(
            "ERROR: --send-all blocked until a sandbox_test success is logged in "
            "relaunch/logs/pipeline.log",
            file=sys.stderr,
        )
        return 1

    from fub_writeback import queue_writeback_for_sent

    rows = _load_rows(csv_path)
    results = process_rows(rows, pdf_dir)
    send_rows = [r for r in results if r.action == Action.SENT]
    lob_map: dict[str, tuple[str, int | None, str]] = {}
    for row in send_rows:
        lob_result = send_letter(row, settings)
        lob_map[row.property_address] = (
            lob_result.letter_id,
            lob_result.http_status,
            lob_result.error,
        )
        status = "OK" if lob_result.letter_id else "FAILED"
        print(
            f"  {status}: {row.property_address} -> "
            f"{lob_result.letter_id or lob_result.error}"
        )
        if lob_result.letter_id:
            src = row.source_row or {}
            queue_writeback_for_sent(
                batch_id=batch_id,
                property_address=row.property_address,
                first_name=(src.get("public.owner1FirstName") or "").strip(),
                last_name=(src.get("public.owner1LastName") or "").strip(),
                street=row.mail_address.line1,
                city=row.mail_address.city,
                state=row.mail_address.state,
                zip_code=row.mail_address.zip,
                lob_letter_id=lob_result.letter_id,
            )

    out = write_run_log(results, log_path(LOGS_DIR), lob_results=lob_map)
    _log(f"send_all complete batch_id={batch_id} run_log={out}")
    print(f"\nRun log written: {out}")
    return 0


def _to_override_from_args(
    to_name: str | None,
    to_line1: str | None,
    to_city: str | None,
    to_state: str | None,
    to_zip: str | None,
) -> dict[str, str] | None:
    fields = {
        "name": (to_name or "").strip(),
        "address_line1": (to_line1 or "").strip(),
        "address_city": (to_city or "").strip(),
        "address_state": (to_state or "").strip(),
        "address_zip": (to_zip or "").strip(),
    }
    if not any(fields.values()):
        return None
    missing = [k for k, v in fields.items() if not v]
    if missing:
        raise ValueError(
            "to override requires all of --to-name, --to-address-line1, "
            f"--to-address-city, --to-address-state, --to-address-zip "
            f"(missing: {', '.join(missing)})"
        )
    return fields


def run_send_addresses(
    batch_id: str,
    addresses: list[str],
    *,
    dry_run: bool = False,
    to_override: dict[str, str] | None = None,
) -> int:
    """
    Send (or dry-run) only the listed property addresses.

    CLI-only resend path. Does not read or write pipeline_state.json and does
    not go through core.main APPROVE SEND / send_initiated_at guard.

    Optional to_override replaces only Lob `to` (PDF file and `from` unchanged).
    When to_override is set, FUB writeback is skipped (sample / redirect send).
    """
    csv_path, pdf_dir = _batch_paths(batch_id)
    os.environ["CSV_PATH"] = str(csv_path)
    os.environ["PDF_DIR"] = str(pdf_dir)
    os.environ["LOG_DIR"] = str(LOGS_DIR)

    rows = _load_rows(csv_path)
    # Dry-run skips FUB suppression (read-only name check). Live send still checks.
    results = process_rows(
        rows,
        pdf_dir,
        check_fub_suppression=not dry_run,
    )
    targets, unmatched = _select_address_rows(results, addresses)
    if unmatched:
        print("ERROR: address(es) not found as SENT rows:", file=sys.stderr)
        for addr in unmatched:
            print(f"  - {addr}", file=sys.stderr)
        return 1
    if not targets:
        print("ERROR: no addresses selected.", file=sys.stderr)
        return 1

    mode_label = "DRY-RUN" if dry_run else "LIVE"
    print(
        f"\n=== Targeted send [{mode_label}] — batch {batch_id} "
        f"({len(targets)} row(s)) ==="
    )
    for row in targets:
        effective_name = (
            to_override["name"] if to_override else row.recipient_name
        )
        name_ok = len(effective_name) <= LOB_TO_NAME_MAX
        print(f"Property: {row.property_address}")
        print(f"  PDF (unchanged): {row.pdf_path}")
        if to_override:
            print(f"  to override: {to_override}")
            print(f"  row recipient (not mailed): {row.recipient_name!r}")
        else:
            print(f"  to.name: {row.recipient_name!r} ({len(row.recipient_name)} chars)")
            print(f"  Mail to: {row.mail_address_used}")
        print(f"  <=40: {name_ok}")

    settings = Settings.from_env_optional_lob()

    if dry_run:
        import json

        over = []
        for row in targets:
            payload = build_letter_payload(
                row, settings, to_override=to_override
            )
            to_name = payload["to"]["name"]
            if len(to_name) > LOB_TO_NAME_MAX:
                over.append(row.property_address)
            print(f"\n--- Lob payload for {row.property_address} ---")
            print(json.dumps(payload, indent=2))
            print(
                f"from unchanged from SENDER_*: "
                f"{payload['from']['name']}, {payload['from']['address_line1']}"
            )
        if over:
            print(
                f"\nDRY-RUN FAIL: {len(over)} name(s) still over {LOB_TO_NAME_MAX} chars",
                file=sys.stderr,
            )
            return 1
        print("\nDRY-RUN OK: no Lob calls made. pipeline_state.json untouched.")
        return 0

    if settings.lob_api_key.startswith("test_"):
        print(
            "ERROR: --addresses live send refuses a sandbox (test_) key.",
            file=sys.stderr,
        )
        return 1
    if not settings.lob_api_key.startswith("live_"):
        print("ERROR: --addresses live send requires a live_ Lob key.", file=sys.stderr)
        return 1
    if not _sandbox_confirmed():
        _log(
            "send_addresses refused: no confirmed sandbox_test success in pipeline.log"
        )
        print(
            "ERROR: live --addresses blocked until a sandbox_test success is logged in "
            "relaunch/logs/pipeline.log",
            file=sys.stderr,
        )
        return 1

    from fub_writeback import queue_writeback_for_sent

    lob_map: dict[str, tuple[str, int | None, str]] = {}
    fail_count = 0
    for row in targets:
        lob_result = send_letter(row, settings, to_override=to_override)
        lob_map[row.property_address] = (
            lob_result.letter_id,
            lob_result.http_status,
            lob_result.error,
        )
        status = "OK" if lob_result.letter_id else "FAILED"
        if not lob_result.letter_id:
            fail_count += 1
        print(
            f"  {status}: {row.property_address} -> "
            f"{lob_result.letter_id or lob_result.error}"
        )
        # Sample / redirected to: do not write back as if mailed to the owner.
        if lob_result.letter_id and to_override is None:
            src = row.source_row or {}
            queue_writeback_for_sent(
                batch_id=batch_id,
                property_address=row.property_address,
                first_name=(src.get("public.owner1FirstName") or "").strip(),
                last_name=(src.get("public.owner1LastName") or "").strip(),
                street=row.mail_address.line1,
                city=row.mail_address.city,
                state=row.mail_address.state,
                zip_code=row.mail_address.zip,
                lob_letter_id=lob_result.letter_id,
            )

    # Run log covers only the targeted rows (not the full batch).
    out = write_run_log(targets, log_path(LOGS_DIR), lob_results=lob_map)
    _log(
        f"send_addresses complete batch_id={batch_id} "
        f"count={len(targets)} failures={fail_count} "
        f"to_override={1 if to_override else 0} run_log={out}"
    )
    print(f"\nRun log written: {out}")
    return 1 if fail_count else 0


def main(argv: list[str] | None = None) -> int:
    _load_env()
    parser = argparse.ArgumentParser(description="Relaunch Lob send for a batch")
    parser.add_argument("--batch-id", required=True, help="Batch id, e.g. 2026-08")
    parser.add_argument(
        "--send-all",
        action="store_true",
        help="Send all SENT rows (live_ key; requires prior sandbox_test success)",
    )
    parser.add_argument(
        "--sandbox-test",
        action="store_true",
        help="Send one SENT row with test_ key (default when neither flag set)",
    )
    parser.add_argument(
        "--addresses",
        nargs="+",
        metavar="ADDRESS",
        help=(
            "Send only these property addresses (listing form). "
            "Does not use APPROVE SEND / send_initiated_at guard."
        ),
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="With --addresses: print Lob payload; no Lob calls",
    )
    parser.add_argument("--to-name", help="Override Lob to.name (with --addresses)")
    parser.add_argument(
        "--to-address-line1",
        help="Override Lob to.address_line1 (with --addresses)",
    )
    parser.add_argument(
        "--to-address-city",
        help="Override Lob to.address_city (with --addresses)",
    )
    parser.add_argument(
        "--to-address-state",
        help="Override Lob to.address_state (with --addresses)",
    )
    parser.add_argument(
        "--to-address-zip",
        help="Override Lob to.address_zip (with --addresses)",
    )
    args = parser.parse_args(argv)

    mode_flags = sum(
        bool(x) for x in (args.send_all, args.sandbox_test, args.addresses)
    )
    if mode_flags > 1:
        parser.error(
            "Specify only one of --sandbox-test, --send-all, or --addresses"
        )
    if args.dry_run and not args.addresses:
        parser.error("--dry-run requires --addresses")

    to_override = None
    try:
        to_override = _to_override_from_args(
            args.to_name,
            args.to_address_line1,
            args.to_address_city,
            args.to_address_state,
            args.to_address_zip,
        )
    except ValueError as exc:
        parser.error(str(exc))
    if to_override and not args.addresses:
        parser.error("to override flags require --addresses")

    if args.addresses:
        return run_send_addresses(
            args.batch_id,
            args.addresses,
            dry_run=args.dry_run,
            to_override=to_override,
        )

    if args.send_all:
        return run_send_all(args.batch_id)

    # Default CLI path: sandbox test (one letter on test_ key).
    # APPROVE SEND callback invokes this module with --send-all.
    return run_sandbox_test(args.batch_id)


if __name__ == "__main__":
    raise SystemExit(main())
