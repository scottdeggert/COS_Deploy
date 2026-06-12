"""Telegram bot client for send/receive messaging."""

import os
import sys

import requests

TELEGRAM_API = "https://api.telegram.org"
BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")

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


def get_updates(offset: int = 0) -> list[dict]:
    url = f"{TELEGRAM_API}/bot{BOT_TOKEN}/getUpdates"
    params = {"offset": offset, "timeout": 10}
    try:
        resp = session.get(url, params=params, timeout=15)
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
    test_msg = "Scout is online. Pre-appointment brief system ready."
    success = send_message(test_msg)
    if success:
        print("Message sent successfully")
    else:
        print("Failed to send message")
