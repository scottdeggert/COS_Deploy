"""
scrub_batch.py

Filter REAPI Expired_Listings export rows before packet generation.

Hold-backs:
  - Pending customStatus
  - Institutional entity ownership (entity_detection.is_true_entity)
  - Ambiguous ownership when no individual first name and no institutional keyword
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

from relaunch.scrub.entity_detection import is_true_entity


def _is_blank(value: str | None) -> bool:
    return value is None or str(value).strip() == ""


def should_hold(row: dict[str, str]) -> str | None:
    """Return hold reason, or None if the row is eligible for generation."""
    status = (row.get("listing.customStatus") or "").strip()

    if status == "Pending":
        return "HELD_PENDING"

    entity = is_true_entity(row)
    if entity is True:
        return "HELD_ENTITY"
    if entity is None:
        return "HELD_AMBIGUOUS_OWNER"

    return None


def scrub_csv(input_path: Path, output_path: Path) -> dict[str, int]:
    with input_path.open(newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        fieldnames = reader.fieldnames or []
        rows = list(reader)

    kept: list[dict[str, str]] = []
    held_rows: list[dict[str, str]] = []
    counts = {
        "input": len(rows),
        "kept": 0,
        "HELD_PENDING": 0,
        "HELD_ENTITY": 0,
        "HELD_AMBIGUOUS_OWNER": 0,
    }

    for row in rows:
        reason = should_hold(row)
        if reason:
            counts[reason] = counts.get(reason, 0) + 1
            held_rows.append(
                {
                    "address": (row.get("listing.address.unparsedAddress") or "").strip(),
                    "reason": reason,
                }
            )
            continue
        kept.append(row)

    counts["kept"] = len(kept)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(kept)

    report_path = output_path.parent / "scrub_report.json"
    report_path.write_text(
        json.dumps({"counts": counts, "held": held_rows}, indent=2) + "\n",
        encoding="utf-8",
    )

    return counts


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Scrub REAPI expired listings for generation")
    parser.add_argument("--input", required=True, help="Path to Expired_Listings.csv")
    parser.add_argument("--output", required=True, help="Path for scrubbed properties CSV")
    args = parser.parse_args(argv)

    input_path = Path(args.input)
    output_path = Path(args.output)
    if not input_path.is_file():
        print(f"Input not found: {input_path}", file=sys.stderr)
        return 1

    counts = scrub_csv(input_path, output_path)
    print(
        f"Scrub complete: input={counts['input']} kept={counts['kept']} "
        f"held_pending={counts['HELD_PENDING']} held_entity={counts['HELD_ENTITY']} "
        f"held_ambiguous_owner={counts['HELD_AMBIGUOUS_OWNER']} "
        f"→ {output_path}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
