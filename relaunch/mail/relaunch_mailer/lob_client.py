"""Lob Print & Mail letter creation."""

from __future__ import annotations

import base64
import json
from dataclasses import dataclass
from pathlib import Path

import requests

from relaunch_mailer.config import QR_CODE_BASE, Settings
from relaunch_mailer.filter import ProcessedRow

_BATCHES_ROOT = Path(__file__).resolve().parents[2] / "batches"
_REVIEW_BASE_URL = "https://webhook.brightworkrealty.com/relaunch/batches"


@dataclass
class LobSendResult:
    http_status: int | None
    letter_id: str
    error: str
    request_body: dict


def _batch_dir_for_pdf(path: Path) -> Path | None:
    resolved = path.resolve()
    try:
        rel = resolved.relative_to(_BATCHES_ROOT.resolve())
    except ValueError:
        return None
    parts = rel.parts
    if len(parts) >= 3 and parts[1] == "output":
        return _BATCHES_ROOT / parts[0]
    return None


def _load_manifest_qr_page(batch_dir: Path) -> int:
    manifest_path = batch_dir / "manifest.json"
    if not manifest_path.is_file():
        raise RuntimeError(
            f"Missing {manifest_path}; generate step must write qr_page before send"
        )
    try:
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"Cannot read manifest.json: {exc}") from exc
    qr_page = payload.get("qr_page")
    if qr_page is None:
        raise RuntimeError(f"manifest.json missing qr_page: {manifest_path}")
    try:
        return int(qr_page)
    except (TypeError, ValueError) as exc:
        raise RuntimeError(f"manifest qr_page is not an int: {qr_page!r}") from exc


def _opaque_token_for_filename(batch_dir: Path, filename: str) -> str | None:
    review_map_path = batch_dir / "review_map.json"
    if not review_map_path.is_file():
        return None
    try:
        mapping = json.loads(review_map_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(mapping, dict):
        return None
    for token, name in mapping.items():
        if name == filename:
            return str(token)
    return None


def _file_reference(path: Path) -> str:
    """
    Prefer an opaque public HTTPS URL (Lob rejects large inline base64).
    Fall back to a PDF data URI only for non-batch local files.
    """
    resolved = path.resolve()
    batch_dir = _batch_dir_for_pdf(resolved)
    if batch_dir is not None:
        batch_id = batch_dir.name
        token = _opaque_token_for_filename(batch_dir, resolved.name)
        if not token:
            raise RuntimeError(
                f"No opaque review token for {resolved.name} in "
                f"{batch_dir / 'review_map.json'}"
            )
        return f"{_REVIEW_BASE_URL}/{batch_id}/f/{token}.pdf"

    raw = base64.b64encode(resolved.read_bytes()).decode("ascii")
    return f"data:application/pdf;base64,{raw}"


def _qr_code_for_pdf(path: Path) -> dict:
    batch_dir = _batch_dir_for_pdf(Path(path))
    if batch_dir is None:
        raise RuntimeError(
            f"Cannot resolve batch dir for PDF {path}; refusing send without manifest"
        )
    qr_page = _load_manifest_qr_page(batch_dir)
    pages = str(qr_page)
    qr = {**QR_CODE_BASE, "pages": pages}
    if qr["pages"] != pages:
        raise RuntimeError(
            f"QR pages mismatch: manifest qr_page={qr_page} payload={qr['pages']}"
        )
    return qr


def build_letter_payload(
    row: ProcessedRow,
    settings: Settings,
    *,
    to_override: dict[str, str] | None = None,
) -> dict:
    """
    Build Lob letter JSON. PDF / qr_code / from come from the batch row and
    SENDER_* settings. Optional to_override replaces only the `to` object
    (name, address_line1, address_city, address_state, address_zip).
    """
    if row.pdf_path is None:
        raise ValueError("Cannot build Lob payload without a matched PDF")

    mail = row.mail_address
    pdf_path = Path(row.pdf_path)
    qr_code = _qr_code_for_pdf(pdf_path)
    manifest_page = _load_manifest_qr_page(_batch_dir_for_pdf(pdf_path))  # type: ignore[arg-type]
    if str(manifest_page) != qr_code["pages"]:
        raise RuntimeError(
            f"QR page mismatch before Lob send: manifest={manifest_page} "
            f"payload_pages={qr_code['pages']}"
        )

    if to_override is not None:
        required = (
            "name",
            "address_line1",
            "address_city",
            "address_state",
            "address_zip",
        )
        missing = [k for k in required if not (to_override.get(k) or "").strip()]
        if missing:
            raise ValueError(f"to_override missing fields: {', '.join(missing)}")
        to_block = {
            "name": to_override["name"].strip(),
            "address_line1": to_override["address_line1"].strip(),
            "address_city": to_override["address_city"].strip(),
            "address_state": to_override["address_state"].strip(),
            "address_zip": to_override["address_zip"].strip(),
        }
    else:
        to_block = {
            "name": row.recipient_name,
            "address_line1": mail.line1,
            "address_city": mail.city,
            "address_state": mail.state,
            "address_zip": mail.zip,
        }

    return {
        "description": f"Relaunch packet - {row.property_address}",
        "to": to_block,
        "from": {
            "name": settings.sender_name,
            "address_line1": settings.sender_address_line1,
            "address_city": settings.sender_address_city,
            "address_state": settings.sender_address_state,
            "address_zip": settings.sender_address_zip,
        },
        "file": _file_reference(pdf_path),
        "color": True,
        "double_sided": False,
        "use_type": "marketing",
        "qr_code": qr_code,
    }


def send_letter(
    row: ProcessedRow,
    settings: Settings,
    *,
    to_override: dict[str, str] | None = None,
) -> LobSendResult:
    payload = build_letter_payload(row, settings, to_override=to_override)
    file_ref = payload["file"]
    if file_ref.startswith("http://") or file_ref.startswith("https://"):
        display_file = file_ref
    elif file_ref.startswith("data:"):
        display_file = f"<data uri pdf, {len(file_ref)} chars>"
    else:
        display_file = f"<inline file, {len(file_ref)} chars>"
    display_payload = {**payload, "file": display_file}

    response = requests.post(
        "https://api.lob.com/v1/letters",
        auth=(settings.lob_api_key, ""),
        json=payload,
        timeout=120,
    )

    letter_id = ""
    error = ""
    if response.ok:
        body = response.json()
        letter_id = body.get("id", "")
    else:
        error = response.text

    return LobSendResult(
        http_status=response.status_code,
        letter_id=letter_id,
        error=error,
        request_body=display_payload,
    )


def print_send_result(result: LobSendResult) -> None:
    print("\n=== Lob API Response ===")
    print(f"HTTP status: {result.http_status}")
    print(f"letter_id: {result.letter_id or '(none)'}")
    if result.error:
        print(f"error: {result.error}")
    print("\n=== Request body (PDF redacted) ===")
    print(json.dumps(result.request_body, indent=2))
