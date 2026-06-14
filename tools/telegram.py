"""Telegram bot client for send/receive messaging."""

import os
import sys

import requests

from tools.logger import log_event

TELEGRAM_API = "https://api.telegram.org"
BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")
OPERATOR_CHAT_ID = os.environ.get("OPERATOR_TELEGRAM_CHAT_ID", "")

session = requests.Session()
_original_request = session.request


def _request_with_timeout(method: str, url: str, **kwargs) -> requests.Response:
    kwargs.setdefault("timeout", 10)
    return _original_request(method, url, **kwargs)


session.request = _request_with_timeout  # type: ignore[method-assign]


def send_message(text: str, chat_id: str = None) -> bool:
    url = f"{TELEGRAM_API}/bot{BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": chat_id or CHAT_ID,
        "text": text,
        "parse_mode": "Markdown",
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
            )
            return

        url = f"{TELEGRAM_API}/bot{BOT_TOKEN}/sendMessage"
        payload = {
            "chat_id": OPERATOR_CHAT_ID,
            "text": message,
        }
        resp = session.post(url, json=payload)
        if resp.ok:
            log_event("monitoring", "operator_alert", "success")
        else:
            log_event(
                "monitoring",
                "operator_alert",
                "failure",
                detail=f"HTTP {resp.status_code}",
            )
    except Exception as exc:
        log_event(
            "monitoring",
            "operator_alert",
            "failure",
            detail=str(exc),
        )


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
