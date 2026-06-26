"""Telegram bot client for send/receive messaging."""

import os
import sys

import requests

from tools.logger import log_event

TELEGRAM_API = "https://api.telegram.org"
BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")
OPERATOR_CHAT_ID = os.environ.get("OPERATOR_TELEGRAM_CHAT_ID", "")
MONITOR_CHAT_ID = os.environ.get("TELEGRAM_MONITOR_CHAT_ID", "")

session = requests.Session()
_original_request = session.request


def _request_with_timeout(method: str, url: str, **kwargs) -> requests.Response:
    kwargs.setdefault("timeout", 10)
    return _original_request(method, url, **kwargs)


session.request = _request_with_timeout  # type: ignore[method-assign]


def send_message(text: str, chat_id: str = None, parse_mode: str | None = None) -> bool:
    url = f"{TELEGRAM_API}/bot{BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": chat_id or CHAT_ID,
        "text": text,
    }
    if parse_mode is not None:
        payload["parse_mode"] = parse_mode
    try:
        resp = session.post(url, json=payload)
        if resp.ok:
            return True
        print(f"sendMessage failed: {resp.status_code}", file=sys.stderr)
        return False
    except requests.RequestException as exc:
        print(f"sendMessage error: {exc}", file=sys.stderr)
        return False


def send_long_message(text: str, chat_id: str = None) -> None:
    """Send a message that may exceed Telegram's 4096-char limit.

    Splits on double newlines to preserve formatting, never mid-sentence.
    Falls back to hard split at 4000 chars if no clean break is found.
    """
    MAX_LEN = 4000  # Leave headroom below 4096 hard limit
    target = chat_id or CHAT_ID

    if len(text) <= MAX_LEN:
        send_message(text, chat_id=target)
        return

    chunks = []
    current = ""

    for paragraph in text.split("\n\n"):
        candidate = (current + "\n\n" + paragraph).lstrip("\n") if current else paragraph
        if len(candidate) <= MAX_LEN:
            current = candidate
        else:
            if current:
                chunks.append(current)
            # Paragraph itself exceeds limit — hard split
            while len(paragraph) > MAX_LEN:
                chunks.append(paragraph[:MAX_LEN])
                paragraph = paragraph[MAX_LEN:]
            current = paragraph

    if current:
        chunks.append(current)

    for chunk in chunks:
        send_message(chunk, chat_id=target)


def send_inline_message(text: str, reply_markup: dict, chat_id: str = None) -> bool:
    url = f"{TELEGRAM_API}/bot{BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": chat_id or CHAT_ID,
        "text": text,
        "reply_markup": reply_markup,
    }
    try:
        resp = session.post(url, json=payload)
        if resp.ok:
            return True
        print(f"sendMessage failed: {resp.status_code}", file=sys.stderr)
        return False
    except requests.RequestException as exc:
        print(f"sendMessage error: {exc}", file=sys.stderr)
        return False


def send_operator_alert(message: str) -> None:
    """Send a plain-text alert to the operator channel. Never raises."""
    try:
        if not OPERATOR_CHAT_ID:
            log_event(
                "monitoring",
                "operator_alert",
                "fallback",
                detail="OPERATOR_TELEGRAM_CHAT_ID not set",
                file=__file__,
                function="send_operator_alert",
            )
            return

        url = f"{TELEGRAM_API}/bot{BOT_TOKEN}/sendMessage"
        payload = {
            "chat_id": OPERATOR_CHAT_ID,
            "text": message,
        }
        resp = session.post(url, json=payload)
        if resp.ok:
            log_event(
                "monitoring",
                "operator_alert",
                "success",
                file=__file__,
                function="send_operator_alert",
            )
        else:
            log_event(
                "monitoring",
                "operator_alert",
                "failure",
                detail=f"HTTP {resp.status_code}",
                file=__file__,
                function="send_operator_alert",
            )
    except Exception as exc:
        log_event(
            "monitoring",
            "operator_alert",
            "failure",
            detail=str(exc),
            exc_info=exc,
        )


def send_monitor_copy(text: str) -> None:
    """Mirror a message to the operator monitor channel. Never raises."""
    if not MONITOR_CHAT_ID:
        return
    try:
        send_message(text, chat_id=MONITOR_CHAT_ID)
    except Exception:
        pass


def get_updates(offset: int = 0, timeout: int = 10) -> list[dict]:
    url = f"{TELEGRAM_API}/bot{BOT_TOKEN}/getUpdates"
    params = {"offset": offset, "timeout": timeout}
    try:
        resp = session.get(url, params=params, timeout=timeout + 5)
        if not resp.ok:
            print(f"getUpdates failed: {resp.status_code}", file=sys.stderr)
            return []
        return resp.json().get("result", [])
    except requests.RequestException as exc:
        print(f"getUpdates error: {exc}", file=sys.stderr)
        return []


def extract_message(update: dict) -> dict | None:
    message = update.get("message")
    if not message:
        return None
    text = message.get("text")
    if not text:
        return None
    chat = message.get("chat", {})
    sender = message.get("from", {})
    return {
        "update_id": update["update_id"],
        "chat_id": str(chat.get("id", "")),
        "text": text,
        "from_name": sender.get("first_name", ""),
    }


if __name__ == "__main__":
    test_msg = "Chief of Staff is online. Pre-appointment brief system ready."
    success = send_message(test_msg)
    if success:
        print("Message sent successfully")
    else:
        print("Failed to send message")
