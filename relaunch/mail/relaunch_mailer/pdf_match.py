"""Exact PDF filename matching derived from brightwork_reports packet output."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class PdfMatchResult:
    """Outcome of matching one CSV row to the packets folder."""

    expected_filename: str
    pdf_path: Path | None
    ambiguous: bool = False


def slugify_street(unparsed_address: str) -> str:
    """
    Street slug used in packet filenames.

    Observed convention (batch_generate.slugify_address):
      '23 Timber Ln' -> '23_Timber_Ln'
      '46 Merrill Cir N' -> '46_Merrill_Cir_N'
      '2 Normandy Lane' -> '2_Normandy_Lane'

    Takes the street portion only (before the first comma), strips punctuation,
    collapses whitespace to underscores, truncates to 60 characters.
    """
    street = unparsed_address.split(",")[0].strip()
    clean = re.sub(r"[^\w\s]", "", street)
    clean = re.sub(r"\s+", "_", clean)
    return clean[:60]


def expected_pdf_filename(city: str, unparsed_address: str) -> str:
    """Return the exact filename expected for a property row."""
    # batch_generate slugifies spaces in city (Walnut Creek -> Walnut_Creek).
    city_slug = re.sub(r"\s+", "_", (city or "").strip())
    return f"{city_slug}_{slugify_street(unparsed_address)}.pdf"


def build_pdf_index(pdf_dir: Path) -> dict[str, Path]:
    """Map lowercase filename -> absolute path for every *.pdf in pdf_dir."""
    index: dict[str, Path] = {}
    for path in sorted(pdf_dir.glob("*.pdf")):
        key = path.name.lower()
        index[key] = path
    return index


def match_pdf(
    city: str,
    unparsed_address: str,
    pdf_index: dict[str, Path],
) -> PdfMatchResult:
    """
    Match one row to exactly one PDF by deterministic filename.

    Returns pdf_path=None when missing or ambiguous (duplicate expected names).
    """
    filename = expected_pdf_filename(city, unparsed_address)
    key = filename.lower()
    path = pdf_index.get(key)
    return PdfMatchResult(expected_filename=filename, pdf_path=path, ambiguous=False)


def list_packet_pdfs(pdf_dir: Path) -> list[str]:
    """Return sorted PDF basenames in the packets folder."""
    return sorted(p.name for p in pdf_dir.glob("*.pdf"))
