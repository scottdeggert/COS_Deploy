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
FUB_X_SYSTEM: str = _require("FUB_X_SYSTEM")
FUB_X_SYSTEM_KEY: str = _require("FUB_X_SYSTEM_KEY")

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

# FUB cross-process rate limiter (token bucket in logs/webhook_queue.db)
FUB_RATE_LIMIT_KEY: str = "fub_global"
FUB_RATE_LIMIT_CAPACITY: float = float(_optional("FUB_RATE_LIMIT_CAPACITY", "18"))
FUB_RATE_LIMIT_REFILL_PER_SECOND: float = float(
    _optional("FUB_RATE_LIMIT_REFILL_PER_SECOND", "1.8")
)
FUB_429_MAX_ATTEMPTS: int = int(_optional("FUB_429_MAX_ATTEMPTS", "5"))
FUB_429_BACKOFF_BASE_SECONDS: float = float(
    _optional("FUB_429_BACKOFF_BASE_SECONDS", "2")
)
FUB_429_BACKOFF_MAX_SECONDS: float = float(
    _optional("FUB_429_BACKOFF_MAX_SECONDS", "32")
)

# Webhook durable queue
WEBHOOK_QUEUE_DB_PATH: Path = LOGS_DIR / "webhook_queue.db"
WEBHOOK_CONSUMER_POLL_SECONDS: float = float(
    _optional("WEBHOOK_CONSUMER_POLL_SECONDS", "0.5")
)
WEBHOOK_CONSUMER_STALE_PROCESSING_SECONDS: int = int(
    _optional("WEBHOOK_CONSUMER_STALE_PROCESSING_SECONDS", "300")
)
WEBHOOK_BURST_THRESHOLD: int = int(_optional("WEBHOOK_BURST_THRESHOLD", "50"))
WEBHOOK_BURST_WINDOW_SECONDS: int = int(
    _optional("WEBHOOK_BURST_WINDOW_SECONDS", "60")
)

# Lead alert idempotency (consumer reclaim after mid-processing kill)
LEAD_ALERT_PROCESSING_STALE_SECONDS: int = int(
    _optional("LEAD_ALERT_PROCESSING_STALE_SECONDS", "300")
)

# Simulation guard: crash/idempotency tests must use an isolated queue DB
COS_SIMULATE_WEBHOOK_FAILURE: bool = _optional(
    "COS_SIMULATE_WEBHOOK_FAILURE", ""
).lower() in ("1", "true", "yes")

# Diagnostic probes: log FUB failures normally, suppress Telegram operator alerts
COS_DIAGNOSTIC_MODE: bool = _optional("COS_DIAGNOSTIC_MODE", "").lower() in (
    "1",
    "true",
    "yes",
)

# Cloud CMA (Phase 1: impromptu generation + tracked delivery)
CLOUDCMA_API_KEY: str = _optional("CLOUDCMA_API_KEY")
CLOUDCMA_WIDGET_URL: str = (
    _optional("CLOUDCMA_WIDGET_URL") or "https://cloudcma.com/cmas/widget"
)
CMA_REDIRECT_BASE: str = (
    _optional("CMA_REDIRECT_BASE") or "https://webhook.brightworkrealty.com"
)
_cma_pdf_archive = _optional("CMA_PDF_ARCHIVE_DIR")
CMA_PDF_ARCHIVE_DIR: Path = (
    Path(_cma_pdf_archive) if _cma_pdf_archive else REPO_ROOT / "logs" / "cma_pdfs"
)

# PostHog (optional interim analytics seam; no-op when unset)
POSTHOG_API_KEY: str = _optional("POSTHOG_API_KEY")
POSTHOG_HOST: str = _optional("POSTHOG_HOST")
POSTHOG_PROJECT_ID: str = _optional("POSTHOG_PROJECT_ID")


def require_test_webhook_queue_for_simulation() -> None:
    """Refuse simulate-failure mode unless the queue DB path is a test file."""
    if not COS_SIMULATE_WEBHOOK_FAILURE:
        return
    if "test" not in str(WEBHOOK_QUEUE_DB_PATH).lower():
        raise EnvironmentError(
            "COS_SIMULATE_WEBHOOK_FAILURE is set but WEBHOOK_QUEUE_DB_PATH does not "
            f"contain 'test': {WEBHOOK_QUEUE_DB_PATH}. Use e.g. logs/webhook_queue.test.db"
        )


require_test_webhook_queue_for_simulation()
