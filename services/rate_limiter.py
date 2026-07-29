"""Cross-process FUB token bucket backed by SQLite."""

from __future__ import annotations

import sqlite3
import time
from datetime import datetime, timezone

import requests

from app.config import (
    FUB_RATE_LIMIT_CAPACITY,
    FUB_RATE_LIMIT_KEY,
    FUB_RATE_LIMIT_REFILL_PER_SECOND,
    LOGS_DIR,
    WEBHOOK_QUEUE_DB_PATH,
)
from tools.logger import log_event

_DB_PATH = WEBHOOK_QUEUE_DB_PATH
_HEADERS_FALLBACK_LOGGED = False


def _connect() -> sqlite3.Connection:
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(_DB_PATH), timeout=30.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=30000")
    return conn


def init_rate_limit_table() -> None:
    with _connect() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS rate_limit (
                key TEXT PRIMARY KEY,
                tokens REAL NOT NULL,
                last_refill TEXT NOT NULL,
                capacity REAL NOT NULL,
                refill_rate REAL NOT NULL
            );
            """
        )
        row = conn.execute(
            "SELECT key FROM rate_limit WHERE key = ?",
            (FUB_RATE_LIMIT_KEY,),
        ).fetchone()
        if row is None:
            now = datetime.now(timezone.utc).isoformat()
            conn.execute(
                """
                INSERT INTO rate_limit (key, tokens, last_refill, capacity, refill_rate)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    FUB_RATE_LIMIT_KEY,
                    FUB_RATE_LIMIT_CAPACITY,
                    now,
                    FUB_RATE_LIMIT_CAPACITY,
                    FUB_RATE_LIMIT_REFILL_PER_SECOND,
                ),
            )
        conn.commit()


def _parse_iso(value: str) -> datetime:
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed


def _refill_tokens(
    tokens: float,
    last_refill: datetime,
    capacity: float,
    refill_rate: float,
) -> tuple[float, datetime]:
    now = datetime.now(timezone.utc)
    elapsed = max((now - last_refill).total_seconds(), 0.0)
    if elapsed <= 0:
        return tokens, last_refill
    refilled = min(capacity, tokens + elapsed * refill_rate)
    return refilled, now


def acquire_fub_token() -> None:
    """Block until one FUB request token is available."""
    init_rate_limit_table()
    while True:
        wait_seconds = 0.05
        with _connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            row = conn.execute(
                """
                SELECT tokens, last_refill, capacity, refill_rate
                FROM rate_limit
                WHERE key = ?
                """,
                (FUB_RATE_LIMIT_KEY,),
            ).fetchone()
            if row is None:
                now = datetime.now(timezone.utc).isoformat()
                conn.execute(
                    """
                    INSERT INTO rate_limit (key, tokens, last_refill, capacity, refill_rate)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        FUB_RATE_LIMIT_KEY,
                        FUB_RATE_LIMIT_CAPACITY - 1.0,
                        now,
                        FUB_RATE_LIMIT_CAPACITY,
                        FUB_RATE_LIMIT_REFILL_PER_SECOND,
                    ),
                )
                conn.commit()
                return

            tokens = float(row["tokens"])
            last_refill = _parse_iso(str(row["last_refill"]))
            capacity = float(row["capacity"])
            refill_rate = float(row["refill_rate"])
            tokens, refreshed_at = _refill_tokens(
                tokens, last_refill, capacity, refill_rate
            )

            if tokens >= 1.0:
                conn.execute(
                    """
                    UPDATE rate_limit
                    SET tokens = ?, last_refill = ?
                    WHERE key = ?
                    """,
                    (tokens - 1.0, refreshed_at.isoformat(), FUB_RATE_LIMIT_KEY),
                )
                conn.commit()
                return

            deficit = 1.0 - tokens
            wait_seconds = max(deficit / max(refill_rate, 0.01), 0.05)
            conn.execute(
                """
                UPDATE rate_limit
                SET tokens = ?, last_refill = ?
                WHERE key = ?
                """,
                (tokens, refreshed_at.isoformat(), FUB_RATE_LIMIT_KEY),
            )
            conn.commit()
        time.sleep(wait_seconds)


def update_from_response(response: requests.Response) -> None:
    """Adjust bucket capacity from FUB X-RateLimit headers when present."""
    global _HEADERS_FALLBACK_LOGGED
    limit_header = response.headers.get("X-RateLimit-Limit")
    remaining_header = response.headers.get("X-RateLimit-Remaining")
    if not limit_header and not remaining_header:
        if not _HEADERS_FALLBACK_LOGGED:
            _HEADERS_FALLBACK_LOGGED = True
            log_event(
                "fub_client",
                "rate_limit_headers",
                "fallback",
                detail="X-RateLimit headers absent; using config defaults",
                file=__file__,
                function="update_from_response",
            )
        return

    init_rate_limit_table()
    with _connect() as conn:
        conn.execute("BEGIN IMMEDIATE")
        row = conn.execute(
            """
            SELECT tokens, last_refill, capacity, refill_rate
            FROM rate_limit
            WHERE key = ?
            """,
            (FUB_RATE_LIMIT_KEY,),
        ).fetchone()
        if row is None:
            conn.commit()
            return

        capacity = float(row["capacity"])
        tokens = float(row["tokens"])
        last_refill = str(row["last_refill"])
        refill_rate = float(row["refill_rate"])

        if limit_header:
            try:
                header_capacity = max(float(limit_header), 1.0)
                capacity = header_capacity
                refill_rate = max(header_capacity / 10.0, 0.1)
            except ValueError:
                pass

        if remaining_header:
            try:
                tokens = min(tokens, max(float(remaining_header), 0.0))
            except ValueError:
                pass

        conn.execute(
            """
            UPDATE rate_limit
            SET tokens = ?, last_refill = ?, capacity = ?, refill_rate = ?
            WHERE key = ?
            """,
            (tokens, last_refill, capacity, refill_rate, FUB_RATE_LIMIT_KEY),
        )
        conn.commit()
