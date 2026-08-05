#!/usr/bin/env python3
"""Manual debug/test harness for send_cma callback handling.

Not called by any production path. Invoke directly when testing CMA delivery
enrollment outside Telegram (bypasses TELEGRAM_CHAT_ID callback gate).

Set COS_DIAGNOSTIC_MODE=1 before running so failures log without operator
Telegram alerts.

Usage:
    COS_DIAGNOSTIC_MODE=1 venv/bin/python scripts/debug_invoke_send_cma.py \\
        <job_id_or_token>
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from app.config import CLIENT_ID
from app.schemas import InboundCallback
from handlers import lead_alert
from tools.cma_registry import get_job, get_job_by_token

if len(sys.argv) < 2:
    print("Usage: debug_invoke_send_cma.py <job_id_or_token>", file=sys.stderr)
    sys.exit(1)

ref = sys.argv[1].strip()
job = get_job(ref)
if job is None:
    job = get_job_by_token(ref)

if job is None:
    print(f"Error: no CMA job found for job_id or token: {ref}", file=sys.stderr)
    sys.exit(1)

if not job.contact_id:
    print(
        f"Error: job {job.job_id} has no contact_id. "
        "Address-only CMAs cannot enroll a delivery sequence.",
        file=sys.stderr,
    )
    sys.exit(1)

callback = InboundCallback(
    chat_id=str(job.reply_chat_id or ""),
    callback_query_id="debug_invoke_send_cma",
    data=f"send_cma:{job.job_id}",
    message_id=0,
    client_id=CLIENT_ID,
)

result = lead_alert.handle_callback(callback)

print(result.telegram_output)
if result.error_details:
    print(f"error_details: {result.error_details}", file=sys.stderr)
sys.exit(0 if result.success else 1)
