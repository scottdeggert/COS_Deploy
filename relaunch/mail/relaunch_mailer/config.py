"""Environment-driven configuration — no hardcoded credentials or addresses."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def _require(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


@dataclass(frozen=True)
class Settings:
    lob_api_key: str
    csv_path: Path
    pdf_dir: Path
    log_dir: Path
    sender_name: str
    sender_address_line1: str
    sender_address_city: str
    sender_address_state: str
    sender_address_zip: str

    @classmethod
    def from_env(cls) -> Settings:
        return cls(
            lob_api_key=_require("LOB_API_KEY"),
            csv_path=Path(_require("CSV_PATH")).expanduser(),
            pdf_dir=Path(_require("PDF_DIR")).expanduser(),
            log_dir=Path(os.environ.get("LOG_DIR", "./logs")).expanduser(),
            sender_name=_require("SENDER_NAME"),
            sender_address_line1=_require("SENDER_ADDRESS_LINE1"),
            sender_address_city=_require("SENDER_ADDRESS_CITY"),
            sender_address_state=_require("SENDER_ADDRESS_STATE"),
            sender_address_zip=_require("SENDER_ADDRESS_ZIP"),
        )

    @classmethod
    def from_env_optional_lob(cls) -> Settings:
        """Like from_env but requires LOB_API_KEY for send modes."""
        key = os.environ.get("LOB_API_KEY", "").strip()
        if not key:
            raise RuntimeError(
                "LOB_API_KEY is required for send modes. "
                "Add your Lob sandbox key (test_...) to .env — see .env.example"
            )
        return cls.from_env()


# QR code URL is campaign-level, not PII — identical for every letter.
QR_CODE_URL = (
    "https://relaunch.brightworkrealty.com"
    "?utm_source=direct-mail&utm_medium=qr&utm_campaign=relaunch&utm_content=q3-2026"
)

# Base QR fields. "pages" is filled from batches/{batch_id}/manifest.json qr_page.
QR_CODE_BASE = {
    "position": "relative",
    "redirect_url": QR_CODE_URL,
    "width": "1.3",
    "top": "4.0",
    "left": "0.75",
}

# Backward-compatible default used only when no batch manifest is available.
QR_CODE = {**QR_CODE_BASE, "pages": "8"}
