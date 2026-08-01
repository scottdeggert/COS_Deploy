#!/usr/bin/env python3
"""Manual debug/test harness for CMA request handling.

Not called by any production path. Invoke directly when testing Cloud CMA
end to end outside Telegram.

Set COS_DIAGNOSTIC_MODE=1 before running so failures log without operator
Telegram alerts.

Usage:
    COS_DIAGNOSTIC_MODE=1 venv/bin/python scripts/debug_invoke_cma.py \\
        "863 Augusta Drive, Moraga, CA" [reply_chat_id]
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from app.config import CLIENT_ID
from app.schemas import InboundMessage, RoutedIntent
from handlers import cma
from tools.telegram import send_long_message

ADDRESS = sys.argv[1] if len(sys.argv) > 1 else "123 Main St, Lafayette, CA"
REPLY_CHAT_ID = sys.argv[2] if len(sys.argv) > 2 else None

msg = InboundMessage(
    chat_id=REPLY_CHAT_ID or "direct",
    raw_text=f"Generate a CMA for {ADDRESS}",
    timestamp=int(time.time()),
    client_id=CLIENT_ID,
)

intent = RoutedIntent(
    original_message=msg,
    intent_type="cma_request",
    entity=ADDRESS,
    confidence=1.0,
)

result = cma.handle(intent)

if REPLY_CHAT_ID and result.telegram_output:
    send_long_message(result.telegram_output, chat_id=REPLY_CHAT_ID)

print(result.telegram_output)
