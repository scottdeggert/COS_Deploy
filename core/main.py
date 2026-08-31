"""CoS Agent entry point.

Wires transport, router, handlers, and scheduler together.
This file orchestrates; it contains no business logic.

Usage:
    python -m core.main
"""

from __future__ import annotations

import json
import os
import signal
import subprocess
import sys
import tempfile
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

from app.config import CLIENT_ID, CLIENTS_DIR, TELEGRAM_MONITOR_CHAT_ID
from app.schemas import InboundCallback, InboundMessage
from core.router import ConversationBuffer, classify_intent, is_admin_chat
from core.scheduler import SimpleScheduler, morning_digest, pre_appointment_check
from core.transport import poll
from handlers import brief, cma, generative, hot_leads, lead_alert, status
from tools.logger import log_event
from tools.telegram import (
    BOT_TOKEN,
    TELEGRAM_API,
    send_operator_alert,
    session as telegram_session,
)

_buffer = ConversationBuffer()

_PIPELINE_STATE_PATH = Path("/root/COS_Deploy/relaunch/logs/pipeline_state.json")
_PIPELINE_LOGS_DIR = _PIPELINE_STATE_PATH.parent


def _edit_telegram_message(
    chat_id: str, message_id: int, text: str, *, remove_keyboard: bool = True
) -> None:
    """Edit an existing Telegram message. Best-effort; never raises."""
    if not chat_id or not message_id:
        return
    url = f"{TELEGRAM_API}/bot{BOT_TOKEN}/editMessageText"
    payload: dict = {
        "chat_id": chat_id,
        "message_id": message_id,
        "text": text,
    }
    if remove_keyboard:
        payload["reply_markup"] = {"inline_keyboard": []}
    try:
        telegram_session.post(url, json=payload, timeout=10)
    except Exception:
        pass


def _load_pipeline_state() -> dict:
    if not _PIPELINE_STATE_PATH.is_file():
        return {}
    try:
        payload = json.loads(_PIPELINE_STATE_PATH.read_text(encoding="utf-8"))
        return payload if isinstance(payload, dict) else {}
    except (OSError, json.JSONDecodeError, TypeError):
        return {}


def _save_pipeline_state(state: dict) -> None:
    """Atomic write: temp file in logs/, flush, fsync, os.replace."""
    _PIPELINE_LOGS_DIR.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(
        dir=str(_PIPELINE_LOGS_DIR),
        prefix="pipeline_state.",
        suffix=".tmp",
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(state, fh, indent=2)
            fh.write("\n")
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(temp_name, _PIPELINE_STATE_PATH)
    except Exception:
        try:
            os.unlink(temp_name)
        except OSError:
            pass
        raise


def _mark_send_initiated(batch_id: str) -> str | None:
    """
    Atomically record send_initiated_at for batch_id.
    Returns prior timestamp if already initiated (caller must refuse), else None.
    """
    state = _load_pipeline_state()
    prior_batch = str(state.get("send_initiated_batch_id") or "").strip()
    prior_at = str(state.get("send_initiated_at") or "").strip()
    if prior_batch == batch_id and prior_at:
        return prior_at

    # Reload immediately before save so we do not overwrite a newer write.
    state = _load_pipeline_state()
    prior_batch = str(state.get("send_initiated_batch_id") or "").strip()
    prior_at = str(state.get("send_initiated_at") or "").strip()
    if prior_batch == batch_id and prior_at:
        return prior_at

    initiated_at = datetime.now(timezone.utc).isoformat()
    state["send_initiated_batch_id"] = batch_id
    state["send_initiated_at"] = initiated_at
    _save_pipeline_state(state)
    return None


def _format_send_outcome(completed: subprocess.CompletedProcess[str]) -> str:
    stdout = completed.stdout or ""
    stderr = completed.stderr or ""
    combined = stdout + "\n" + stderr
    ok_count = sum(
        1 for line in stdout.splitlines() if line.lstrip().startswith("OK:")
    )
    fail_count = sum(
        1 for line in stdout.splitlines() if line.lstrip().startswith("FAILED:")
    )
    run_log = ""
    for line in combined.splitlines():
        if "Run log written:" in line:
            run_log = line.split("Run log written:", 1)[1].strip()
        elif "run_log=" in line and not run_log:
            run_log = line.split("run_log=", 1)[1].strip()

    if completed.returncode == 0:
        parts = [
            "Relaunch send complete.",
            f"Letters sent: {ok_count}",
            f"Failures: {fail_count}",
        ]
        if run_log:
            parts.append(f"Run log: {run_log}")
        return "\n".join(parts)

    # Refusal / hard failure (e.g. test_ key gate).
    err_lines = [ln.strip() for ln in stderr.splitlines() if ln.strip()]
    err_hint = err_lines[-1] if err_lines else f"exit={completed.returncode}"
    parts = [
        "Relaunch send failed.",
        err_hint[:300],
        f"Letters sent: {ok_count}",
        f"Failures: {fail_count}",
    ]
    if run_log:
        parts.append(f"Run log: {run_log}")
    return "\n".join(parts)


def _handle_relaunch_send(callback: InboundCallback) -> str | None:
    """APPROVE SEND: live --send-all path with ack, idempotency, outcome edit."""
    batch_id = (callback.data or "").split(":", 1)[1].strip()
    if not batch_id:
        return "Relaunch send ignored: missing batch id."

    prior = _mark_send_initiated(batch_id)
    if prior is not None:
        refuse = f"Relaunch send already initiated at {prior}."
        _edit_telegram_message(
            callback.chat_id,
            callback.message_id,
            refuse,
            remove_keyboard=True,
        )
        log_event(
            "relaunch",
            "approve_send",
            "fallback",
            detail=f"batch_id={batch_id} already_initiated_at={prior}",
            file=__file__,
            function="_handle_relaunch_send",
        )
        return refuse

    # Show Sending... and strip the button before launch.
    _edit_telegram_message(
        callback.chat_id,
        callback.message_id,
        f"Relaunch batch {batch_id}\n\nSending...",
        remove_keyboard=True,
    )

    cmd = [
        "/root/COS_Deploy/venv/bin/python",
        "-m",
        "relaunch.mail.send",
        "--batch-id",
        batch_id,
        "--send-all",
    ]
    log_event(
        "relaunch",
        "approve_send",
        "start",
        detail=f"batch_id={batch_id}",
        file=__file__,
        function="_handle_relaunch_send",
    )
    completed = subprocess.run(
        cmd,
        cwd="/root/COS_Deploy",
        check=False,
        capture_output=True,
        text=True,
    )
    outcome = _format_send_outcome(completed)
    _edit_telegram_message(
        callback.chat_id,
        callback.message_id,
        outcome,
        remove_keyboard=True,
    )

    if completed.returncode == 0:
        log_event(
            "relaunch",
            "approve_send",
            "success",
            detail=f"batch_id={batch_id}",
            file=__file__,
            function="_handle_relaunch_send",
        )
    else:
        log_event(
            "relaunch",
            "approve_send",
            "failure",
            detail=f"batch_id={batch_id} exit={completed.returncode}",
            file=__file__,
            function="_handle_relaunch_send",
        )
    # Outcome already edited onto the approve card; no second chat message.
    return None


def _route_message(message: InboundMessage) -> str | None:
    """Classify intent and dispatch to handler. Return reply string or None."""
    _buffer.add("user", message.raw_text)
    intent = classify_intent(message, _buffer)

    if intent.intent_type == "greeting":
        return generative.handle_greeting(intent).telegram_output

    if intent.intent_type == "identity_query":
        return generative.handle_identity(intent).telegram_output

    if intent.intent_type == "help_request":
        return generative.handle_help(intent).telegram_output

    if intent.intent_type == "brief_request":
        result = brief.handle(intent)
        return result.telegram_output

    if intent.intent_type in ("hot_leads", "hot_leads_list"):
        result = hot_leads.handle(intent)
        return result.telegram_output

    if intent.intent_type in ("draft_outreach", "draft_communication"):
        result = generative.handle(intent)
        return result.telegram_output

    if intent.intent_type == "cma_request":
        result = cma.handle(intent)
        return result.telegram_output

    if intent.intent_type == "status_check":
        if not is_admin_chat(intent.original_message.chat_id):
            return generative.handle_fallback(intent).telegram_output
        lines = int(intent.entity or 50)
        result = status.handle_status(lines)
        return result.telegram_output

    if intent.intent_type == "digest_test":
        if not is_admin_chat(intent.original_message.chat_id):
            return generative.handle_fallback(intent).telegram_output
        log_event(
            "digest_test", "morning_digest", "start",
            file=__file__, function="_route_message",
        )
        try:
            morning_digest(target_chat_id=str(TELEGRAM_MONITOR_CHAT_ID))
            log_event(
                "digest_test", "morning_digest", "success",
                file=__file__, function="_route_message",
            )
            return "Morning digest triggered manually. Sent to the monitor channel only."
        except Exception as exc:
            log_event(
                "digest_test", "morning_digest", "failure",
                detail=str(exc), exc_info=exc,
                file=__file__, function="_route_message",
            )
            send_operator_alert(f"Manual digest test failed: {exc}")
            return "Manual digest trigger failed. Check operator alerts."

    return generative.handle_fallback(intent).telegram_output


def _on_message(message: InboundMessage) -> str | None:
    reply = _route_message(message)
    if reply is not None:
        _buffer.add("assistant", reply)
    return reply


def _route_callback(callback: InboundCallback) -> str | None:
    """Route inline keyboard button presses to handlers."""
    data = callback.data or ""
    if data.startswith("relaunch_send:"):
        return _handle_relaunch_send(callback)

    result = lead_alert.handle_callback(callback)
    return result.telegram_output if result.telegram_output else None


def _build_scheduled_jobs(scheduler: SimpleScheduler) -> None:
    """Register all scheduled jobs. Job functions call tools/ directly."""
    config_path = CLIENTS_DIR / CLIENT_ID / "scheduler_config.json"
    with config_path.open(encoding="utf-8") as f:
        sched_config = json.load(f)

    digest_hour = sched_config["morning_digest"]["hour"]
    digest_minute = sched_config["morning_digest"]["minute"]
    appt_interval = sched_config["pre_appointment_check"]["interval_seconds"]

    scheduler.add_daily(
        hour=digest_hour, minute=digest_minute,
        job=morning_digest, name="morning_digest",
    )
    scheduler.add_interval(
        seconds=appt_interval,
        job=pre_appointment_check, name="pre_appointment_check",
    )


_WATCHDOG_RESPAWN_DELAY_SECONDS = 2


def _terminate_stale_watchdog_processes() -> None:
    """Kill orphaned tools.watchdog processes left after core.main restarts."""
    try:
        result = subprocess.run(
            ["pgrep", "-f", r"python -m tools\.watchdog"],
            capture_output=True,
            text=True,
            timeout=5,
        )
    except (OSError, subprocess.SubprocessError):
        return
    if result.returncode != 0:
        return
    for line in result.stdout.splitlines():
        if not line.strip().isdigit():
            continue
        pid = int(line.strip())
        try:
            os.kill(pid, signal.SIGTERM)
        except (ProcessLookupError, PermissionError):
            pass
    time.sleep(0.5)


def _watchdog_supervisor() -> None:
    """Keep a single tools/watchdog.py instance running."""
    while True:
        _terminate_stale_watchdog_processes()
        log_event(
            "watchdog",
            "supervisor",
            "start",
            file=__file__,
            function="_watchdog_supervisor",
        )
        proc = subprocess.run(
            [sys.executable, "-m", "tools.watchdog"],
            cwd=str(CLIENTS_DIR.parent),
        )
        if proc.returncode == 0:
            log_event(
                "watchdog",
                "lock_contention",
                "success",
                detail="exit code 0, lock held by another instance",
                file=__file__,
                function="_watchdog_supervisor",
            )
        else:
            log_event(
                "watchdog",
                "supervisor",
                "failure",
                detail=f"exit code {proc.returncode}",
                file=__file__,
                function="_watchdog_supervisor",
            )
        time.sleep(_WATCHDOG_RESPAWN_DELAY_SECONDS)


def _start_watchdog() -> None:
    thread = threading.Thread(target=_watchdog_supervisor, daemon=True)
    thread.start()


def main() -> None:
    """Start the CoS agent."""
    from app.config import HEALTH_CHECK_CONTACT_ID
    from tools.fub import get_contact_by_id

    log_event("cos_agent", "startup", "start", file=__file__, function="main")

    # Startup health check
    if HEALTH_CHECK_CONTACT_ID:
        try:
            get_contact_by_id(HEALTH_CHECK_CONTACT_ID)
            log_event(
                "cos_agent", "startup", "success",
                detail="FUB connectivity confirmed",
                file=__file__, function="main",
            )
        except Exception as exc:
            send_operator_alert(f"CoS Agent startup failed -- FUB check: {exc}")
            raise SystemExit(f"FUB connectivity check failed: {exc}")

    send_operator_alert("Trevor is online.")
    log_event("cos_agent", "startup", "success", file=__file__, function="main")

    _start_watchdog()

    # Start scheduler
    scheduler = SimpleScheduler()
    _build_scheduled_jobs(scheduler)
    scheduler.start()

    # Start buffer (already initialized at module level)
    log_event(
        "cos_agent", "buffer", "start",
        detail="ConversationBuffer loaded",
        file=__file__, function="main",
    )

    # Start polling loop (blocks)
    try:
        poll(on_message=_on_message, on_callback=_route_callback)
    except KeyboardInterrupt:
        send_operator_alert("Trevor going offline.")
        log_event("cos_agent", "shutdown", "success", file=__file__, function="main")


if __name__ == "__main__":
    main()
