"""Telegram long-poll transport layer.

This module is responsible for receiving messages from Telegram and
passing them to the router. It contains no business logic.

If Telegram polling behavior ever changes (e.g., migrating to webhooks),
only this file changes. The router and handlers are unaffected.
"""

from __future__ import annotations

import time
from typing import Callable

from app.config import CLIENT_ID, TELEGRAM_CHAT_ID, TELEGRAM_MONITOR_CHAT_ID
from app.schemas import InboundCallback, InboundMessage
from tools.logger import log_event
from tools.telegram import (
    BOT_TOKEN,
    TELEGRAM_API,
    extract_message,
    get_updates,
    send_monitor_copy,
    session as telegram_session,
)

POLL_TIMEOUT = 30


def _answer_callback_query(callback_query_id: str) -> None:
    if not callback_query_id:
        return
    url = f"{TELEGRAM_API}/bot{BOT_TOKEN}/answerCallbackQuery"
    payload = {"callback_query_id": callback_query_id}
    try:
        telegram_session.post(url, json=payload, timeout=10)
    except Exception:
        pass


def _drain_stale_updates() -> int:
    """Acknowledge queued updates on startup without executing them."""
    offset = 0
    while True:
        updates = get_updates(offset=offset, timeout=0)
        if not updates:
            break
        for update in updates:
            offset = update.get("update_id", 0) + 1
            callback_query = update.get("callback_query")
            if callback_query:
                _answer_callback_query(callback_query.get("id", ""))
    return offset


def poll(
    on_message: Callable[[InboundMessage], str | None],
    on_callback: Callable[[InboundCallback], str | None],
) -> None:
    """Start the polling loop. Blocks indefinitely.

    on_message: called with each InboundMessage; return value sent to Ben.
    on_callback: called with each InboundCallback; return value sent to Ben.
    """
    configured_chat_id = str(TELEGRAM_CHAT_ID)
    monitor_chat_id = str(TELEGRAM_MONITOR_CHAT_ID)
    offset = _drain_stale_updates()

    from tools.telegram import send_long_message

    while True:
        updates = get_updates(offset=offset, timeout=POLL_TIMEOUT)
        for update in updates:
            update_id = update.get("update_id", 0)
            offset = update_id + 1

            message = extract_message(update)
            if message:
                chat_id = message["chat_id"]
                if chat_id in (configured_chat_id, monitor_chat_id):
                    text = message["text"]
                    ts = int(time.time())

                    log_event(
                        "transport", "inbound", "success",
                        detail=text, file=__file__, function="poll",
                    )
                    send_monitor_copy(f"[BEN -> CoS] {text}")

                    inbound = InboundMessage(
                        chat_id=chat_id,
                        raw_text=text,
                        timestamp=ts,
                        client_id=CLIENT_ID,
                    )
                    reply = on_message(inbound)
                    if reply is not None:
                        send_long_message(reply, chat_id=chat_id)
                        send_monitor_copy(f"[BEN] {text}\n[CoS] {reply[:500]}")
                        log_event(
                            "transport", "outbound", "success",
                            detail=reply[:200], file=__file__, function="poll",
                        )

            callback_query = update.get("callback_query")
            if callback_query:
                callback_id = callback_query.get("id", "")
                _answer_callback_query(callback_id)
                cb_chat_id = str(
                    callback_query.get("message", {}).get("chat", {}).get("id", "")
                )
                if cb_chat_id == configured_chat_id:
                    inbound_cb = InboundCallback(
                        chat_id=cb_chat_id,
                        callback_query_id=callback_id,
                        data=callback_query.get("data", ""),
                        message_id=callback_query.get("message", {}).get("message_id", 0),
                        client_id=CLIENT_ID,
                    )
                    reply = on_callback(inbound_cb)
                    if reply is not None:
                        send_long_message(reply, chat_id=cb_chat_id)
