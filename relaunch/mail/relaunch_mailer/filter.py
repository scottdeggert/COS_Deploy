"""Hold-back filtering and recipient / mailing-address construction."""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

from relaunch_mailer.pdf_match import PdfMatchResult, build_pdf_index, match_pdf

# Repo root on path so relaunch.scrub.fub_suppression is importable from mail cwd.
_REPO_ROOT = Path(__file__).resolve().parents[3]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from relaunch.scrub.fub_suppression import check_row_suppression  # noqa: E402


class Action(str, Enum):
    SENT = "SENT"
    HELD_PENDING = "HELD_PENDING"
    HELD_ENTITY = "HELD_ENTITY"
    HELD_UNMATCHED = "HELD_UNMATCHED"
    HELD_SUPPRESSED = "HELD_SUPPRESSED"


def _is_blank(value: str | None) -> bool:
    return value is None or str(value).strip() == ""


@dataclass
class MailAddress:
    line1: str
    city: str
    state: str
    zip: str

    def formatted(self) -> str:
        return f"{self.line1}, {self.city}, {self.state} {self.zip}"


@dataclass
class ProcessedRow:
    """One input CSV row after filtering and address construction."""

    property_address: str
    recipient_name: str
    mail_address: MailAddress
    action: Action
    pdf_path: Path | None = None
    expected_pdf: str = ""
    notes: list[str] = field(default_factory=list)
    source_row: dict[str, str] = field(default_factory=dict, repr=False)

    @property
    def mail_address_used(self) -> str:
        return self.mail_address.formatted()

    @property
    def error(self) -> str:
        return "; ".join(self.notes)


def _property_address(row: dict[str, str]) -> str:
    street = row.get("listing.address.unparsedAddress", "").strip()
    city = row.get("listing.address.city", "").strip()
    state = row.get("listing.address.stateOrProvince", "CA").strip()
    zip_code = row.get("listing.address.zipCode", "").strip()
    return f"{street}, {city}, {state} {zip_code}".strip(", ")


# Lob rejects to.name longer than 40 characters (HTTP 422).
LOB_TO_NAME_MAX = 40


def build_recipient_name(row: dict[str, str]) -> str:
    """
    Build Lob to.name. Prefer full dual-owner form; if over Lob's 40-char
    limit, shorten to real name forms (never mid-word character clip):
      1. "{Owner1 First} & {Owner2 First} {Shared Last}" when last names match
      2. First owner only ("{Owner1 First} {Owner1 Last}")
    """
    o1f = (row.get("public.owner1FirstName") or "").strip()
    o1l = (row.get("public.owner1LastName") or "").strip()
    o2f = (row.get("public.owner2FirstName") or "").strip()
    o2l = (row.get("public.owner2LastName") or "").strip()
    company = (row.get("public.companyName") or "").strip()

    if _is_blank(o1f) and company:
        return company

    owner1 = f"{o1f} {o1l}".strip()
    name = owner1
    if o2f:
        suffix = f"{o2f} {o2l}".strip()
        if suffix:
            name = f"{owner1} & {suffix}"

    if len(name) <= LOB_TO_NAME_MAX:
        return name

    if o2f and o1l and o2l and o1l.casefold() == o2l.casefold():
        shared = f"{o1f} & {o2f} {o1l}".strip()
        if shared and len(shared) <= LOB_TO_NAME_MAX:
            return shared

    return owner1


def build_mail_address(row: dict[str, str]) -> tuple[MailAddress, list[str]]:
    """
    Prefer public.mailAddress.*; fall back to property address with a flag.
    """
    mail_street = (row.get("public.mailAddress.address") or "").strip()
    mail_city = (row.get("public.mailAddress.city") or "").strip()
    mail_state = (row.get("public.mailAddress.state") or "").strip()
    mail_zip = (row.get("public.mailAddress.zip") or "").strip()

    notes: list[str] = []
    if _is_blank(mail_street):
        mail_street = (row.get("public.address.address") or row.get("listing.address.unparsedAddress") or "").strip()
        mail_city = (row.get("public.address.city") or row.get("listing.address.city") or "").strip()
        mail_state = (row.get("public.address.state") or row.get("listing.address.stateOrProvince") or "CA").strip()
        mail_zip = (row.get("public.address.zip") or row.get("listing.address.zipCode") or "").strip()
        notes.append("ADDRESS_FALLBACK_USED")

    return MailAddress(line1=mail_street, city=mail_city, state=mail_state, zip=mail_zip), notes


def classify_row(row: dict[str, str], pdf_match: PdfMatchResult) -> Action:
    status = (row.get("listing.customStatus") or "").strip()
    o1f = row.get("public.owner1FirstName")
    company = row.get("public.companyName")

    if status == "Pending":
        return Action.HELD_PENDING
    if _is_blank(o1f) and not _is_blank(company):
        return Action.HELD_ENTITY
    if pdf_match.pdf_path is None:
        return Action.HELD_UNMATCHED
    return Action.SENT


def process_rows(
    rows: list[dict[str, str]],
    pdf_dir: Path,
    *,
    check_fub_suppression: bool = True,
) -> list[ProcessedRow]:
    """Apply hold-back rules and build recipient data for every input row."""
    pdf_index = build_pdf_index(pdf_dir)
    results: list[ProcessedRow] = []

    for row in rows:
        city = (row.get("listing.address.city") or "").strip()
        street = (row.get("listing.address.unparsedAddress") or "").strip()
        pdf_match = match_pdf(city, street, pdf_index)
        action = classify_row(row, pdf_match)

        recipient = build_recipient_name(row)
        mail_address, notes = build_mail_address(row)

        if action == Action.HELD_UNMATCHED and pdf_match.expected_filename:
            notes.append(f"expected_pdf={pdf_match.expected_filename}")

        if action == Action.SENT and check_fub_suppression:
            outcome = check_row_suppression(row)
            if outcome.hold:
                action = Action.HELD_SUPPRESSED
                notes.append(outcome.reason)
            else:
                if outcome.reason:
                    notes.append(outcome.reason)
                if outcome.review:
                    notes.append("FLAG_HUMAN_REVIEW")

        results.append(
            ProcessedRow(
                property_address=_property_address(row),
                recipient_name=recipient,
                mail_address=mail_address,
                action=action,
                pdf_path=pdf_match.pdf_path if action == Action.SENT else None,
                expected_pdf=pdf_match.expected_filename,
                notes=notes,
                source_row=row,
            )
        )

    return results


def summarize(results: list[ProcessedRow]) -> dict[str, int]:
    counts: dict[str, int] = {a.value: 0 for a in Action}
    counts["FLAG_HUMAN_REVIEW"] = 0
    for row in results:
        counts[row.action.value] += 1
        if "FLAG_HUMAN_REVIEW" in row.notes:
            counts["FLAG_HUMAN_REVIEW"] += 1
    return counts
