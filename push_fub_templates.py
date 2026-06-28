#!/usr/bin/env python3
"""
Push plain-text email templates from Ben Olsen sequence files to Follow Up Boss.

Reads EMAIL steps from clients/ben-olsen/sequences/*.md, skips Day 0
(Telegram approval) and HTML template steps, and POSTs the rest to FUB /v1/templates.

Usage:
  python scripts/push_fub_templates.py              # dry run (default)
  python scripts/push_fub_templates.py --live       # POST templates to FUB

Requires FUB_API_KEY in the environment for --live mode.
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

FUB_BASE_URL = "https://api.followupboss.com/v1"

SEQUENCE_FILES = [
    "zillow-seller.md",
    "zillow-buyer.md",
    "homelight.md",
    "off-market-buyer.md",
    "buy-before-you-sell.md",
    "mcc-estimator.md",
    "expired-packet.md",
    "senior-workshop.md",
    "quiet-listing.md",
    "brightflip.md",
    "final-offer.md",
    "relaunch.md",
    "general-buyer.md",
    "agent-referral.md",
    "portal-seller.md",
    "portal-buyer.md",
]

STEP_HEADING_RE = re.compile(
    r"^(?:#{1,2}\s+)?Step\s+\S+\s+—\s+Day\s+(\d+)\s+Email(?:\s*\([^)]*\))?\s*$",
    re.MULTILINE | re.IGNORECASE,
)
PATH_HEADING_RE = re.compile(
    r"^###\s+(Seller path|Buyer path)\s*$",
    re.MULTILINE | re.IGNORECASE,
)
SUBJECT_RE = re.compile(
    r"^\*{0,2}Subject:\*{0,2}\s*(.+?)\s*$",
    re.MULTILINE | re.IGNORECASE,
)
HTML_TEMPLATE_RE = re.compile(
    r"(?:\*\*Template:\*\*|Template:)\s*[`']?[^\n`']*\.html[`']?",
    re.IGNORECASE,
)
NON_EMAIL_STEP_RE = re.compile(
    r"^(?:#{1,2}\s+)?Step\s+\S+\s+—\s+Day\s+\d+\s+(?:SMS|Task|Call)",
    re.MULTILINE | re.IGNORECASE,
)
SKIP_BODY_PREFIXES = (
    "fub auto-sends",
    "pause-on-response:",
    "path a:",
    "path b:",
    "**body:**",
    "body:",
)


@dataclass
class EmailTemplate:
    sequence_slug: str
    day: int
    subject: str
    body: str
    path_label: str | None = None

    @property
    def name(self) -> str:
        base = f"{self.sequence_slug} - Day {self.day} - {self.subject}"
        if self.path_label:
            return f"{base} ({self.path_label})"
        return base


def repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def sequences_dir() -> Path:
    return repo_root() / "clients" / "ben-olsen" / "sequences"


def is_html_step(heading_line: str, section_text: str) -> bool:
    if "(html" in heading_line.lower():
        return True
    if HTML_TEMPLATE_RE.search(section_text):
        return True
    if re.search(r"\.html\b", section_text, re.IGNORECASE) and re.search(
        r"(?:template:|rendered html|\[placeholder)", section_text, re.IGNORECASE
    ):
        return True
    return False


def strip_markdown(text: str) -> str:
    lines: list[str] = []
    for line in text.splitlines():
        stripped = line.strip()
        if re.fullmatch(r"-{3,}", stripped):
            continue
        line = re.sub(r"^#{1,6}\s+", "", line)
        line = re.sub(r"\*\*(.+?)\*\*", r"\1", line)
        line = re.sub(r"\*(.+?)\*", r"\1", line)
        line = re.sub(r"`(.+?)`", r"\1", line)
        lines.append(line.rstrip())
    return "\n".join(lines).strip()


def should_skip_body_line(line: str) -> bool:
    lowered = line.strip().lower()
    if not lowered:
        return False
    return any(lowered.startswith(prefix) for prefix in SKIP_BODY_PREFIXES)


def extract_body_after_subject(block: str, subject_match: re.Match[str]) -> str:
    remainder = block[subject_match.end() :].lstrip("\n")
    body_lines: list[str] = []
    for line in remainder.splitlines():
        if PATH_HEADING_RE.match(line):
            break
        if STEP_HEADING_RE.match(line):
            break
        if should_skip_body_line(line):
            continue
        body_lines.append(line)
    return strip_markdown("\n".join(body_lines))


def parse_path_blocks(section_text: str) -> list[tuple[str | None, str]]:
    path_matches = list(PATH_HEADING_RE.finditer(section_text))
    if not path_matches:
        return [(None, section_text)]

    blocks: list[tuple[str | None, str]] = []
    for index, match in enumerate(path_matches):
        start = match.end()
        end = (
            path_matches[index + 1].start()
            if index + 1 < len(path_matches)
            else len(section_text)
        )
        label = match.group(1).lower().replace(" path", "")
        blocks.append((label, section_text[start:end]))
    return blocks


def fetch_existing_templates(api_key: str) -> dict[str, int]:
    credentials = base64.b64encode(f"{api_key}:".encode("utf-8")).decode("ascii")
    existing: dict[str, int] = {}
    offset = 0
    limit = 200
    while True:
        request = Request(
            f"{FUB_BASE_URL}/templates?limit={limit}&offset={offset}",
            headers={"Authorization": f"Basic {credentials}"},
            method="GET",
        )
        try:
            with urlopen(request, timeout=30) as response:
                data = json.loads(response.read().decode("utf-8"))
        except (HTTPError, URLError) as exc:
            print(f"WARNING: Could not fetch existing templates: {exc}", file=sys.stderr)
            return existing
        for t in data.get("templates", []):
            existing[t["name"]] = t["id"]
        total = data.get("_metadata", {}).get("total", 0)
        offset += limit
        if offset >= total:
            break
    return existing


def put_template(api_key: str, template_id: int, template: EmailTemplate) -> tuple[bool, str]:
    payload = {
        "name": template.name,
        "subject": template.subject,
        "body": template.body,
    }
    credentials = base64.b64encode(f"{api_key}:".encode("utf-8")).decode("ascii")
    request = Request(
        f"{FUB_BASE_URL}/templates/{template_id}",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Basic {credentials}",
            "Content-Type": "application/json",
        },
        method="PUT",
    )
    try:
        with urlopen(request, timeout=30) as response:
            body = response.read().decode("utf-8")
            return True, body
    except HTTPError as exc:
        error_body = exc.read().decode("utf-8", errors="replace")
        return False, f"HTTP {exc.code}: {error_body}"
    except URLError as exc:
        return False, str(exc.reason)


def post_template(api_key: str, template: EmailTemplate) -> tuple[bool, str]:
    payload = {
        "name": template.name,
        "subject": template.subject,
        "body": template.body,
    }
    credentials = base64.b64encode(f"{api_key}:".encode("utf-8")).decode("ascii")
    request = Request(
        f"{FUB_BASE_URL}/templates",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Basic {credentials}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urlopen(request, timeout=30) as response:
            body = response.read().decode("utf-8")
            return True, body
    except HTTPError as exc:
        error_body = exc.read().decode("utf-8", errors="replace")
        return False, f"HTTP {exc.code}: {error_body}"
    except URLError as exc:
        return False, str(exc.reason)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--live",
        action="store_true",
        help="POST templates to FUB (default is dry run)",
    )
    args = parser.parse_args()

    seq_dir = sequences_dir()
    if not seq_dir.is_dir():
        print(f"Sequences directory not found: {seq_dir}", file=sys.stderr)
        return 1

    total_found = 0
    skipped_html = 0
    skipped_day0 = 0
    created = 0
    failed = 0

    api_key = os.environ.get("FUB_API_KEY", "")
    if args.live and not api_key:
        print("FUB_API_KEY environment variable is required for --live mode.", file=sys.stderr)
        return 1

    existing_templates: dict[str, int] = {}
    if args.live:
        print("Fetching existing templates from FUB...")
        existing_templates = fetch_existing_templates(api_key)
        print(f"Found {len(existing_templates)} existing templates.")

    updated = 0
    for filename in SEQUENCE_FILES:
        path = seq_dir / filename
        if not path.is_file():
            print(f"WARNING: missing sequence file: {path}", file=sys.stderr)
            continue

        sequence_slug = path.stem
        content = path.read_text(encoding="utf-8")
        step_matches = list(STEP_HEADING_RE.finditer(content))

        print(f"\n=== {sequence_slug} ===")

        for index, match in enumerate(step_matches):
            day = int(match.group(1))
            heading_line = match.group(0)
            section_start = match.end()
            section_end = (
                step_matches[index + 1].start()
                if index + 1 < len(step_matches)
                else len(content)
            )
            section_text = content[section_start:section_end]
            non_email_match = NON_EMAIL_STEP_RE.search(section_text)
            if non_email_match:
                section_text = section_text[:non_email_match.start()]
            total_found += 1

            if is_html_step(heading_line, section_text):
                skipped_html += 1
                subject_match = SUBJECT_RE.search(section_text)
                subject_hint = subject_match.group(1).strip() if subject_match else heading_line
                print(f"  SKIP (HTML): Day {day} — {subject_hint}")
                continue

            if day == 0:
                skipped_day0 += 1
                subject_match = SUBJECT_RE.search(section_text)
                subject_hint = subject_match.group(1).strip() if subject_match else heading_line
                print(f"  SKIP (Day 0): Day {day} — {subject_hint}")
                continue

            for path_label, block in parse_path_blocks(section_text):
                subject_match = SUBJECT_RE.search(block)
                if not subject_match:
                    print(f"  WARNING: Day {day} email missing Subject line", file=sys.stderr)
                    continue

                subject = subject_match.group(1).strip()
                subject = re.sub(r"\*\*(.+?)\*\*", r"\1", subject)
                subject = re.sub(r"`(.+?)`", r"\1", subject).strip()
                body = extract_body_after_subject(block, subject_match)
                template = EmailTemplate(
                    sequence_slug=sequence_slug,
                    day=day,
                    subject=subject,
                    body=body,
                    path_label=path_label,
                )

                preview = template.body[:100].replace("\n", "\\n")
                if len(template.body) > 100:
                    preview += "..."

                if args.live:
                    if template.name in existing_templates:
                        ok, response = put_template(api_key, existing_templates[template.name], template)
                        action = "UPDATED"
                    else:
                        ok, response = post_template(api_key, template)
                        action = "CREATED"
                    if ok:
                        if action == "UPDATED":
                            updated += 1
                        else:
                            created += 1
                        print(f"  {action}: {template.name}")
                    else:
                        failed += 1
                        print(f"  FAIL: {template.name} — {response}")
                else:
                    print(f"  {template.name}")
                    print(f"    Subject: {template.subject}")
                    print(f"    Body: {preview}")

    print("\n--- Summary ---")
    print(f"Total templates found: {total_found}")
    print(f"Skipped (HTML): {skipped_html}")
    print(f"Skipped (Day 0): {skipped_day0}")
    print(f"Successfully created: {created}")
    print(f"Failed: {failed}")
    if not args.live:
        print("(Dry run — pass --live to POST to FUB)")

    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
