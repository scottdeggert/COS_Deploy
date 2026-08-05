"""Salutation tests for known June-export trust-adjacent individuals.

Unit tests cover salutation logic only. Optional PDF fixtures for those
addresses are written under relaunch/tests/fixtures/ — never into a live
batch output directory.
"""

from __future__ import annotations

import csv
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from batch_generate import _owner_salutation

GENERATE_DIR = Path(__file__).resolve().parent
RELAUNCH_ROOT = GENERATE_DIR.parent
FIXTURES_DIR = RELAUNCH_ROOT / "tests" / "fixtures"
JUNE_EXPORT = (
    RELAUNCH_ROOT
    / "_source"
    / "reapi"
    / "data_exports"
    / "Ben"
    / "2026-06"
    / "Expired_Listings.csv"
)
VENV_PYTHON = RELAUNCH_ROOT.parent / "venv" / "bin" / "python"


class OwnerSalutationTests(unittest.TestCase):
    def test_152_tharp_dr_maralyn_cantor(self):
        row = {
            "listing.address.unparsedAddress": "152 Tharp Dr",
            "public.owner1FirstName": "Maralyn",
            "public.owner1LastName": "Cantor",
            "public.companyName": "",
            "public.owner2Company": "The Maralyn Cantor Living Trust",
            "public.owner2LastName": "The Maralyn Cantor Living Trust",
        }
        salutation = _owner_salutation(row)
        self.assertNotEqual(salutation, "Dear Homeowner,")
        self.assertEqual(salutation, "Dear Maralyn,")

    def test_61_sullivan_dr_maria_gerontides(self):
        row = {
            "listing.address.unparsedAddress": "61 Sullivan Dr",
            "public.owner1FirstName": "Maria",
            "public.owner1LastName": "Gerontides",
            "public.companyName": "",
            "public.owner2Company": "The Maria Gerontides Trust",
            "public.owner2LastName": "The Maria Gerontides Trust",
        }
        salutation = _owner_salutation(row)
        self.assertNotEqual(salutation, "Dear Homeowner,")
        self.assertEqual(salutation, "Dear Maria,")

    def test_entity_company_falls_back(self):
        row = {
            "public.owner1FirstName": "",
            "public.owner1LastName": "Sagestone Custom Homes Llc",
            "public.companyName": "Sagestone Custom Homes Llc",
            "public.owner2Company": "",
        }
        self.assertEqual(_owner_salutation(row), "Dear Homeowner,")

    def test_owner2_first_name_salutation_when_owner1_blank(self):
        row = {
            "public.owner1FirstName": "",
            "public.owner1LastName": "Smith Family Trust",
            "public.owner2FirstName": "Jane",
            "public.owner2LastName": "Smith",
            "public.companyName": "Smith Family Trust",
        }
        self.assertEqual(_owner_salutation(row), "Dear Jane,")


def write_salutation_fixture_pdfs() -> list[Path]:
    """
    Generate Tharp/Sullivan fixture PDFs into relaunch/tests/fixtures/.
    Uses --skip-api stub content so this never writes into a live batch.
    """
    if not JUNE_EXPORT.is_file():
        raise FileNotFoundError(f"June export missing: {JUNE_EXPORT}")

    FIXTURES_DIR.mkdir(parents=True, exist_ok=True)
    wanted = {"152 Tharp Dr", "61 Sullivan Dr"}
    with JUNE_EXPORT.open(newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        fieldnames = reader.fieldnames or []
        rows = [
            r
            for r in reader
            if (r.get("listing.address.unparsedAddress") or "").strip() in wanted
        ]
    if len(rows) != 2:
        raise RuntimeError(f"Expected 2 June fixture rows, found {len(rows)}")

    with tempfile.NamedTemporaryFile(
        mode="w",
        suffix=".csv",
        delete=False,
        encoding="utf-8",
        newline="",
    ) as tmp:
        writer = csv.DictWriter(tmp, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
        tmp_csv = Path(tmp.name)

    python = str(VENV_PYTHON if VENV_PYTHON.is_file() else sys.executable)
    completed = subprocess.run(
        [
            python,
            str(GENERATE_DIR / "batch_generate.py"),
            "--csv",
            str(tmp_csv),
            "--output-dir",
            str(FIXTURES_DIR),
            "--skip-api",
            "--auto-confirm",
        ],
        cwd=str(GENERATE_DIR),
        check=False,
    )
    tmp_csv.unlink(missing_ok=True)
    if completed.returncode != 0:
        raise RuntimeError("batch_generate fixture write failed")

    pdfs = sorted(FIXTURES_DIR.glob("*.pdf"))
    if len(pdfs) < 2:
        raise RuntimeError(f"Expected fixture PDFs in {FIXTURES_DIR}, found {pdfs}")
    return pdfs


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--write-fixtures":
        paths = write_salutation_fixture_pdfs()
        for path in paths:
            print(path)
        raise SystemExit(0)
    unittest.main()
