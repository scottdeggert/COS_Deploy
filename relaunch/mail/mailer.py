#!/usr/bin/env python3
"""CLI for relaunch-mailer: filter-only, sandbox test, or full send."""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

from dotenv import load_dotenv

from relaunch_mailer.config import Settings
from relaunch_mailer.filter import Action, process_rows, summarize
from relaunch_mailer.lob_client import print_send_result, send_letter
from relaunch_mailer.pdf_match import list_packet_pdfs
from relaunch_mailer.run_log import log_path, write_run_log


def load_csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def print_scrub_holds(csv_path: Path) -> None:
    report_path = csv_path.resolve().parent / "scrub_report.json"
    if not report_path.is_file():
        return
    try:
        payload = json.loads(report_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return
    held = payload.get("held") if isinstance(payload, dict) else []
    counts = payload.get("counts") if isinstance(payload, dict) else {}
    if not isinstance(held, list):
        return
    print("\n=== Scrub Holds (pre-generation) ===")
    if isinstance(counts, dict):
        for key in ("HELD_PENDING", "HELD_ENTITY", "HELD_AMBIGUOUS_OWNER"):
            print(f"  {key}: {counts.get(key, 0)}")
    for item in held:
        if not isinstance(item, dict):
            continue
        reason = item.get("reason", "")
        if reason in ("HELD_ENTITY", "HELD_AMBIGUOUS_OWNER", "HELD_PENDING"):
            print(f"  {reason:22} {item.get('address', '')}")


def print_investigation(pdf_dir: Path, csv_path: Path) -> None:
    print_scrub_holds(csv_path)
    pdfs = list_packet_pdfs(pdf_dir)
    print(f"\n=== PDF Investigation ===")
    print(f"Packets folder: {pdf_dir}")
    print(f"PDF count: {len(pdfs)}")
    print("\nAll packet filenames:")
    for name in pdfs:
        print(f"  {name}")

    print("\nNaming convention (observed from batch_generate.py output):")
    print("  {listing.address.city}_{street_slug}.pdf")
    print("  street_slug = unparsedAddress before comma, strip punctuation,")
    print("                spaces -> underscores, max 60 chars")
    print('  Example: "23 Timber Ln" + Lafayette -> Lafayette_23_Timber_Ln.pdf')


def print_filter_summary(results: list) -> None:
    counts = summarize(results)
    print("\n=== Filter Summary ===")
    for action in Action:
        print(f"  {action.value}: {counts[action.value]}")
    print(f"  FLAG_HUMAN_REVIEW: {counts.get('FLAG_HUMAN_REVIEW', 0)}")
    print(f"  TOTAL: {len(results)}")

    print("\n=== Row Detail ===")
    for row in results:
        extra = f" [{row.error}]" if row.error else ""
        print(f"  {row.action.value:18} {row.property_address}{extra}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Relaunch packet mailer via Lob")
    parser.add_argument(
        "--filter-only",
        action="store_true",
        help="Run hold-back filtering only; no Lob API calls",
    )
    parser.add_argument(
        "--sandbox-test",
        action="store_true",
        help="Send exactly one SENT row via Lob sandbox key, then stop",
    )
    parser.add_argument(
        "--send-all",
        action="store_true",
        help="Send all SENT rows (requires production key; use with care)",
    )
    parser.add_argument(
        "--investigate",
        action="store_true",
        help="Print PDF folder inventory and naming convention",
    )
    args = parser.parse_args()

    load_dotenv()

    if not any([args.filter_only, args.sandbox_test, args.send_all, args.investigate]):
        parser.error("Specify one of: --filter-only, --sandbox-test, --send-all, --investigate")

    csv_path = Path(__import__("os").environ.get("CSV_PATH", "")).expanduser()
    pdf_dir = Path(__import__("os").environ.get("PDF_DIR", "")).expanduser()

    if not csv_path or not str(csv_path):
        print("ERROR: CSV_PATH not set in environment/.env", file=sys.stderr)
        return 1
    if not pdf_dir or not str(pdf_dir):
        print("ERROR: PDF_DIR not set in environment/.env", file=sys.stderr)
        return 1

    rows = load_csv_rows(csv_path)
    if args.investigate:
        print_investigation(pdf_dir, csv_path)

    results = process_rows(rows, pdf_dir)

    if args.filter_only or args.investigate:
        print_filter_summary(results)
        if args.filter_only:
            log_dir = Path(__import__("os").environ.get("LOG_DIR", "./logs")).expanduser()
            out = write_run_log(results, log_path(log_dir))
            print(f"\nRun log written: {out}")
            return 0

    if args.sandbox_test or args.send_all:
        settings = Settings.from_env_optional_lob()
        send_rows = [r for r in results if r.action == Action.SENT]

        if args.sandbox_test:
            if not settings.lob_api_key.startswith("test_"):
                print(
                    "ERROR: --sandbox-test requires a Lob sandbox key (test_...)",
                    file=sys.stderr,
                )
                return 1
            if not send_rows:
                print("ERROR: No rows marked SENT; cannot run sandbox test.", file=sys.stderr)
                print_filter_summary(results)
                return 1
            target = send_rows[0]
            print(f"\n=== Sandbox Test — single record ===")
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
            out = write_run_log(results, log_path(settings.log_dir), lob_results=lob_map)
            print(f"\nRun log written: {out}")

            if lob_result.letter_id:
                print(f"\nSandbox test succeeded: letter_id={lob_result.letter_id}")
                return 0
            return 1

        if args.send_all:
            if settings.lob_api_key.startswith("test_"):
                print(
                    "ERROR: --send-all refuses to run with a sandbox (test_) key.",
                    file=sys.stderr,
                )
                return 1
            from fub_writeback import queue_writeback_for_sent

            batch_id = Path(csv_path).resolve().parent.name
            lob_map: dict[str, tuple[str, int | None, str]] = {}
            for row in send_rows:
                lob_result = send_letter(row, settings)
                lob_map[row.property_address] = (
                    lob_result.letter_id,
                    lob_result.http_status,
                    lob_result.error,
                )
                status = "OK" if lob_result.letter_id else "FAILED"
                print(f"  {status}: {row.property_address} -> {lob_result.letter_id or lob_result.error}")
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

            out = write_run_log(results, log_path(settings.log_dir), lob_results=lob_map)
            print(f"\nRun log written: {out}")
            return 0

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
