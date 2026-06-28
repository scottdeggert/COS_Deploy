"""Centralized configuration loader.

This is the single place where environment variables are read.
All other modules import from here instead of calling os.environ directly
or loading dotenv themselves.

Import order matters: this module must be imported before any tools/
or agents/ modules in the entry point.
"""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

# Load .env from repo root regardless of working directory
_ENV_PATH = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(_ENV_PATH, override=True)


def _require(key: str) -> str:
    value = os.environ.get(key, "").strip()
    if not value:
        raise EnvironmentError(
            f"Required environment variable '{key}' is not set. "
            f"Check your .env file at {_ENV_PATH}"
        )
    return value


def _optional(key: str, default: str = "") -> str:
    return os.environ.get(key, default).strip()


# LLM Inference
OPENROUTER_API_KEY: str = _require("OPENROUTER_API_KEY")
OPENROUTER_URL: str = "https://openrouter.ai/api/v1/chat/completions"
SONNET_MODEL: str = "anthropic/claude-sonnet-4-6"
HAIKU_MODEL: str = "anthropic/claude-haiku-4-5"

# Follow Up Boss
FUB_API_KEY: str = _require("FUB_API_KEY")
FUB_BASE_URL: str = "https://api.followupboss.com/v1"

# Telegram
TELEGRAM_BOT_TOKEN: str = _require("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID: str = _require("TELEGRAM_CHAT_ID")
TELEGRAM_MONITOR_CHAT_ID: str = _require("TELEGRAM_MONITOR_CHAT_ID")
OPERATOR_TELEGRAM_CHAT_ID: str = _require("OPERATOR_TELEGRAM_CHAT_ID")

# Tenant
CLIENT_ID: str = _optional("CLIENT_ID", "ben-olsen")
HEALTH_CHECK_CONTACT_ID: str = _optional("HEALTH_CHECK_CONTACT_ID")

# Paths
REPO_ROOT: Path = Path(__file__).resolve().parent.parent
CLIENTS_DIR: Path = REPO_ROOT / "clients"
LOGS_DIR: Path = REPO_ROOT / "logs"
