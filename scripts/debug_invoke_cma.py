#!/usr/bin/env python3
"""Manual debug/test harness for CMA request handling via the real router.

Not called by any production path. Invoke directly when testing Cloud CMA
end to end outside Telegram.

This script passes the utterance through core.router.classify_intent (Haiku)
before handlers.cma.handle. It does not hand-build RoutedIntent slots, so
entity, entity_address, send_intent, and intent_type match what a live
Telegram message with the same text would produce. Keep it that way as
intent slots evolve.

Set COS_DIAGNOSTIC_MODE=1 before running so failures log without operator
Telegram alerts.

Usage:
    COS_DIAGNOSTIC_MODE=1 venv/bin/python scripts/debug_invoke_cma.py \\
        "Generate a CMA for 863 Augusta Drive, Moraga, CA" [reply_chat_id]

    COS_DIAGNOSTIC_MODE=1 venv/bin/python scripts/debug_invoke_cma.py \\
        "Send Scott Eggert a CMA for 768 Augusta Dr, Moraga, CA" [reply_chat_id]

Pass the full utterance as argv[1], not a bare address alone. The classifier
needs the CMA phrasing to return cma_request.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from app.config import CLIENT_ID
from app.schemas import InboundMessage
from core.router import ConversationBuffer, classify_intent
from handlers import cma
from tools.telegram import send_long_message

UTTERANCE = (
    sys.argv[1]
    if len(sys.argv) > 1
    else "Generate a CMA for 123 Main St, Lafayette, CA"
)
REPLY_CHAT_ID = sys.argv[2] if len(sys.argv) > 2 else None

msg = InboundMessage(
    chat_id=REPLY_CHAT_ID or "direct",
    raw_text=UTTERANCE,
    timestamp=int(time.time()),
    client_id=CLIENT_ID,
)

# Empty in-memory buffer: do not load production conversation_buffer.json,
# so this run classifies the utterance alone (no recent-turn bleed).
buffer = ConversationBuffer.__new__(ConversationBuffer)
buffer._turns = []

intent = classify_intent(msg, buffer)

print(
    "classified:"
    f" intent_type={intent.intent_type}"
    f" entity={intent.entity!r}"
    f" entity_address={intent.entity_address!r}"
    f" send_intent={intent.send_intent!r}"
    f" confidence={intent.confidence}"
)

if intent.intent_type != "cma_request":
    print(
        f"Classifier returned intent_type={intent.intent_type!r}, "
        "not cma_request. Not calling CMA handler."
    )
    sys.exit(1)

result = cma.handle(intent)

if REPLY_CHAT_ID and result.telegram_output:
    send_long_message(result.telegram_output, chat_id=REPLY_CHAT_ID)

print(result.telegram_output)
