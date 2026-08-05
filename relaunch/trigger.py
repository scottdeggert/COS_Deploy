"""
relaunch.trigger — cron entrypoint for the monthly expired-listings pipeline.

Flow: monthly gate → pull → scrub → generate → suppression → operator Telegram
approve card. Lob send happens only after APPROVE SEND callback.
"""

from __future__ import annotations

import csv
import json
import os
import secrets
import subprocess
import sys
import tempfile
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from dotenv import load_dotenv

RELAUNCH_ROOT = Path(__file__).resolve().parent
REPO_ROOT = RELAUNCH_ROOT.parent
PULL_DIR = RELAUNCH_ROOT / "pull"
LOGS_DIR = RELAUNCH_ROOT / "logs"
BATCHES_DIR = RELAUNCH_ROOT / "batches"
STATE_PATH = LOGS_DIR / "pipeline_state.json"
PIPELINE_LOG = LOGS_DIR / "pipeline.log"
PACIFIC = ZoneInfo("America/Los_Angeles")
VENV_PYTHON = REPO_ROOT / "venv" / "bin" / "python"
REVIEW_BASE_URL = "https://webhook.brightworkrealty.com/relaunch/batches"


def _load_env() -> None:
    # Relaunch-scoped secrets first (LOB_*), then repo .env for shared keys.
    load_dotenv(RELAUNCH_ROOT / ".env", override=True)
    load_dotenv(REPO_ROOT / ".env", override=False)


def _log(message: str) -> None:
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(tz=PACIFIC).strftime("%Y-%m-%d %H:%M:%S %Z")
    line = f"[{stamp}] {message}\n"
    with PIPELINE_LOG.open("a", encoding="utf-8") as fh:
        fh.write(line)
    print(line, end="")


def _load_state() -> dict:
    if not STATE_PATH.is_file():
        return {}
    try:
        with STATE_PATH.open(encoding="utf-8") as fh:
            payload = json.load(fh)
        return payload if isinstance(payload, dict) else {}
    except (OSError, json.JSONDecodeError, TypeError):
        return {}


def _save_state(state: dict) -> None:
    """Atomically persist state via temp file + fsync + os.replace."""
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(
        dir=str(LOGS_DIR),
        prefix="pipeline_state.",
        suffix=".tmp",
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(state, fh, indent=2)
            fh.write("\n")
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(temp_name, STATE_PATH)
    except Exception:
        try:
            os.unlink(temp_name)
        except OSError:
            pass
        raise


def _month_key(now: datetime | None = None) -> str:
    now = now or datetime.now(tz=PACIFIC)
    return now.strftime("%Y-%m")


def _run(cmd: list[str], cwd: Path | None = None, *, step: str) -> None:
    env = os.environ.copy()
    env.setdefault("PYTHONPATH", str(REPO_ROOT))
    completed = subprocess.run(
        cmd,
        cwd=str(cwd) if cwd else None,
        env=env,
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.stdout:
        print(completed.stdout, end="")
    if completed.stderr:
        print(completed.stderr, end="", file=sys.stderr)
    if completed.returncode != 0:
        tail = (completed.stderr or completed.stdout or "").strip()
        detail = tail[-500:] if tail else f"exit={completed.returncode}"
        raise RuntimeError(f"step={step} failed: {detail}")


def _latest_expired_csv(client: str = "Ben") -> Path:
    export_root = PULL_DIR / "data_exports" / client
    if not export_root.is_dir():
        raise FileNotFoundError(f"No export directory at {export_root}")
    months = sorted(
        (p for p in export_root.iterdir() if p.is_dir()),
        key=lambda p: p.name,
    )
    if not months:
        raise FileNotFoundError(f"No monthly export folders under {export_root}")
    candidate = months[-1] / "Expired_Listings.csv"
    if not candidate.is_file():
        raise FileNotFoundError(f"Expired_Listings.csv missing at {candidate}")
    return candidate


def _count_csv_rows(path: Path) -> int:
    with path.open(newline="", encoding="utf-8") as fh:
        return sum(1 for _ in csv.DictReader(fh))


def _build_review_map(batch_dir: Path, output_dir: Path) -> dict[str, str]:
    """
    Map opaque tokens -> on-disk PDF filenames for the review/Lob URL surface.
    Written to batches/{batch_id}/review_map.json.
    """
    mapping: dict[str, str] = {}
    for pdf in sorted(output_dir.glob("*.pdf")):
        token = secrets.token_urlsafe(16)
        mapping[token] = pdf.name
    path = batch_dir / "review_map.json"
    fd, temp_name = tempfile.mkstemp(
        dir=str(batch_dir),
        prefix="review_map.",
        suffix=".tmp",
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(mapping, fh, indent=2)
            fh.write("\n")
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(temp_name, path)
    except Exception:
        try:
            os.unlink(temp_name)
        except OSError:
            pass
        raise
    return mapping


def _failed_step_from_error(exc: Exception) -> str:
    text = str(exc)
    if text.startswith("step=") and " failed:" in text:
        return text.split(" failed:", 1)[0].removeprefix("step=")
    for name in ("pull", "scrub", "generate", "suppression", "telegram_approve_card"):
        if name in text:
            return name
    return "unknown"


def _alert_pipeline_failure(month: str, step: str, error: str) -> None:
    if str(REPO_ROOT) not in sys.path:
        sys.path.insert(0, str(REPO_ROOT))
    from tools.telegram import send_operator_alert

    message = (
        f"RELAUNCH PIPELINE FAILURE\n"
        f"month={month}\n"
        f"step={step}\n"
        f"error={error}"
    )
    send_operator_alert(message)
    _log(f"step=telegram_failure_alert success month={month} step={step}")


def _run_suppression(batch_id: str, scrubbed_csv: Path, output_dir: Path) -> dict:
    if str(REPO_ROOT) not in sys.path:
        sys.path.insert(0, str(REPO_ROOT))
    mail_dir = RELAUNCH_ROOT / "mail"
    if str(mail_dir) not in sys.path:
        sys.path.insert(0, str(mail_dir))

    from relaunch_mailer.filter import Action, process_rows, summarize

    with scrubbed_csv.open(newline="", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    results = process_rows(rows, output_dir)
    counts = summarize(results)
    ready = counts.get(Action.SENT.value, 0)
    _log(
        f"step=suppression success batch_id={batch_id} "
        f"ready={ready} held_suppressed={counts.get(Action.HELD_SUPPRESSED.value, 0)} "
        f"held_unmatched={counts.get(Action.HELD_UNMATCHED.value, 0)} "
        f"flag_human_review={counts.get('FLAG_HUMAN_REVIEW', 0)}"
    )
    return counts


def _load_scrub_report(batch_dir: Path) -> dict[str, int]:
    path = batch_dir / "scrub_report.json"
    if not path.is_file():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    counts = payload.get("counts") if isinstance(payload, dict) else {}
    if not isinstance(counts, dict):
        return {}
    return {str(k): int(v) for k, v in counts.items() if isinstance(v, int)}


def _notify_operator(
    batch_id: str,
    *,
    pulled: int,
    scrubbed_kept: int,
    scrubbed_out: int,
    scrub_counts: dict[str, int],
    mail_counts: dict[str, int],
) -> None:
    if str(REPO_ROOT) not in sys.path:
        sys.path.insert(0, str(REPO_ROOT))

    from app.config import OPERATOR_TELEGRAM_CHAT_ID
    from tools.telegram import send_inline_message

    ready = mail_counts.get("SENT", 0)
    review_url = f"{REVIEW_BASE_URL}/{batch_id}/"
    text = (
        f"Relaunch batch {batch_id} ready for review.\n"
        f"\n"
        f"Pulled: {pulled}\n"
        f"Scrubbed out: {scrubbed_out} (kept {scrubbed_kept})\n"
        f"Held back:\n"
        f"  HELD_PENDING: {scrub_counts.get('HELD_PENDING', 0)}\n"
        f"  HELD_ENTITY: {scrub_counts.get('HELD_ENTITY', 0)}\n"
        f"  HELD_AMBIGUOUS_OWNER: {scrub_counts.get('HELD_AMBIGUOUS_OWNER', 0)}\n"
        f"  HELD_UNMATCHED: {mail_counts.get('HELD_UNMATCHED', 0)}\n"
        f"  HELD_SUPPRESSED: {mail_counts.get('HELD_SUPPRESSED', 0)}\n"
        f"  FLAG_HUMAN_REVIEW: {mail_counts.get('FLAG_HUMAN_REVIEW', 0)}\n"
        f"Ready to send: {ready}\n"
        f"\n"
        f"Review PDFs (auth required): {review_url}"
    )
    markup = {
        "inline_keyboard": [
            [
                {
                    "text": "APPROVE SEND",
                    "callback_data": f"relaunch_send:{batch_id}",
                }
            ]
        ]
    }
    result = send_inline_message(
        text,
        markup,
        chat_id=str(OPERATOR_TELEGRAM_CHAT_ID),
    )
    if result:
        _log(
            f"step=telegram_approve_card success batch_id={batch_id} "
            f"ready={ready} review_url={review_url}"
        )
        _log(f"telegram_message_text={text!r}")
    else:
        _log(
            f"step=telegram_approve_card failure batch_id={batch_id} "
            f"error={result.error}"
        )
        raise RuntimeError(f"step=telegram_approve_card failed: {result.error}")


def run_pipeline() -> int:
    _load_env()
    month = _month_key()
    state = _load_state()
    last_batch_month = str(state.get("last_batch_month") or "")

    if last_batch_month == month:
        _log(f"decision=already_ran_this_month month={month}")
        return 0

    _log(f"decision=started month={month}")

    state = _load_state()
    state["last_batch_month"] = month
    state["last_batch_started_at"] = datetime.now(tz=PACIFIC).isoformat()
    state["last_batch_status"] = "started"
    _save_state(state)

    batch_dir = BATCHES_DIR / month
    output_dir = batch_dir / "output"
    scrubbed_csv = batch_dir / "properties.csv"
    batch_dir.mkdir(parents=True, exist_ok=True)
    output_dir.mkdir(parents=True, exist_ok=True)

    python = str(VENV_PYTHON if VENV_PYTHON.is_file() else sys.executable)
    current_step = "pull"

    try:
        _log("step=pull start")
        current_step = "pull"
        pull_env = os.environ.copy()
        pull_env.setdefault("RELAUNCH_MODULES", "expired")
        pull_env.setdefault("PYTHONPATH", str(REPO_ROOT))
        pull_completed = subprocess.run(
            [python, "extract_all_leads.py"],
            cwd=str(PULL_DIR),
            env=pull_env,
            check=False,
            capture_output=True,
            text=True,
        )
        if pull_completed.stdout:
            print(pull_completed.stdout, end="")
        if pull_completed.stderr:
            print(pull_completed.stderr, end="", file=sys.stderr)
        if pull_completed.returncode != 0:
            tail = (pull_completed.stderr or pull_completed.stdout or "").strip()
            detail = tail[-500:] if tail else f"exit={pull_completed.returncode}"
            raise RuntimeError(f"step=pull failed: {detail}")
        _log("step=pull success")

        expired_csv = _latest_expired_csv("Ben")
        pulled = _count_csv_rows(expired_csv)
        _log(f"step=scrub start input={expired_csv} pulled={pulled}")
        current_step = "scrub"
        _run(
            [
                python,
                str(RELAUNCH_ROOT / "scrub" / "scrub_batch.py"),
                "--input",
                str(expired_csv),
                "--output",
                str(scrubbed_csv),
            ],
            step="scrub",
        )
        scrubbed_kept = _count_csv_rows(scrubbed_csv)
        scrubbed_out = max(pulled - scrubbed_kept, 0)
        scrub_counts = _load_scrub_report(batch_dir)
        _log(
            f"step=scrub success kept={scrubbed_kept} scrubbed_out={scrubbed_out} "
            f"held_entity={scrub_counts.get('HELD_ENTITY', 0)} "
            f"held_ambiguous_owner={scrub_counts.get('HELD_AMBIGUOUS_OWNER', 0)}"
        )

        _log(f"step=generate start csv={scrubbed_csv} output_dir={output_dir}")
        current_step = "generate"
        _run(
            [
                python,
                str(RELAUNCH_ROOT / "generate" / "batch_generate.py"),
                "--csv",
                str(scrubbed_csv),
                "--output-dir",
                str(output_dir),
                "--auto-confirm",
            ],
            cwd=RELAUNCH_ROOT / "generate",
            step="generate",
        )
        pdf_count = len(list(output_dir.glob("*.pdf")))
        _log(f"step=generate success pdf_count={pdf_count} output_dir={output_dir}")

        current_step = "review_map"
        review_map = _build_review_map(batch_dir, output_dir)
        _log(f"step=review_map success tokens={len(review_map)}")

        current_step = "suppression"
        mail_counts = _run_suppression(month, scrubbed_csv, output_dir)

        current_step = "telegram_approve_card"
        _notify_operator(
            month,
            pulled=pulled,
            scrubbed_kept=scrubbed_kept,
            scrubbed_out=scrubbed_out,
            scrub_counts=scrub_counts,
            mail_counts=mail_counts,
        )

        state = _load_state()
        state["last_batch_month"] = month
        state["last_batch_completed_at"] = datetime.now(tz=PACIFIC).isoformat()
        state["last_batch_status"] = "awaiting_approve"
        state["last_batch_pdf_count"] = pdf_count
        state["last_batch_output_dir"] = str(output_dir)
        state["last_batch_ready_to_send"] = mail_counts.get("SENT", 0)
        state["last_batch_mail_counts"] = mail_counts
        _save_state(state)
        _log(
            f"pipeline=complete month={month} pdf_count={pdf_count} "
            f"status=awaiting_approve"
        )
        return 0
    except Exception as exc:
        step = _failed_step_from_error(exc) or current_step
        state = _load_state()
        state["last_batch_month"] = month
        state["last_batch_status"] = "failed"
        state["last_batch_error"] = str(exc)
        state["last_batch_failed_step"] = step
        _save_state(state)
        _log(f"pipeline=failure month={month} step={step} error={exc}")
        try:
            _alert_pipeline_failure(month, step, str(exc))
        except Exception as alert_exc:
            _log(f"step=telegram_failure_alert failure error={alert_exc}")
        return 1


def _retry_fub_writebacks() -> None:
    """Non-blocking retry of queued post-send FUB writebacks."""
    try:
        from relaunch.mail.fub_writeback import retry_pending_writebacks

        counts = retry_pending_writebacks()
        if counts.get("pending") or counts.get("success") or counts.get("failed"):
            _log(
                "step=fub_writeback_retry "
                f"success={counts.get('success', 0)} "
                f"failed={counts.get('failed', 0)} "
                f"pending={counts.get('pending', 0)}"
            )
    except Exception as exc:
        _log(f"step=fub_writeback_retry error={exc}")


def main() -> int:
    _load_env()
    _retry_fub_writebacks()
    return run_pipeline()


if __name__ == "__main__":
    raise SystemExit(main())
