"""SQLite-backed durable webhook queue and burst circuit breaker state."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timedelta, timezone
from typing import Any

from app.config import (
    LOGS_DIR,
    WEBHOOK_BURST_THRESHOLD,
    WEBHOOK_BURST_WINDOW_SECONDS,
    WEBHOOK_QUEUE_DB_PATH,
)
from tools.logger import log_event

_DB_PATH = WEBHOOK_QUEUE_DB_PATH
_TERMINAL_STATUSES = frozenset({"done", "failed", "dropped_burst"})


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(dt: datetime) -> str:
    return dt.isoformat()


def _connect() -> sqlite3.Connection:
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(_DB_PATH), timeout=30.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=30000")
    return conn


def init_db() -> None:
    """Create queue and burst tables if missing."""
    with _connect() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                received_at TEXT NOT NULL,
                event_type TEXT NOT NULL,
                payload TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending',
                attempts INTEGER NOT NULL DEFAULT 0,
                last_error TEXT
            );
            CREATE INDEX IF NOT EXISTS idx_events_status_id
                ON events(status, id);
            CREATE INDEX IF NOT EXISTS idx_events_type_received
                ON events(event_type, received_at);
            CREATE TABLE IF NOT EXISTS burst_state (
                event_type TEXT PRIMARY KEY,
                cooldown_until TEXT,
                last_alert_at TEXT
            );
            """
        )
        conn.commit()


def _resource_ids_from_payload(payload: dict[str, Any]) -> list[str]:
    resource_ids = payload.get("resourceIds") or []
    if not isinstance(resource_ids, list):
        return []
    return [str(raw_id) for raw_id in resource_ids]


def _contact_id_range(resource_ids: list[str]) -> str:
    if not resource_ids:
        return "none"
    numeric = sorted(int(value) for value in resource_ids if value.isdigit())
    if not numeric:
        return f"{resource_ids[0]}..{resource_ids[-1]}"
    return f"{numeric[0]}..{numeric[-1]}"


def _count_recent_events(conn: sqlite3.Connection, event_type: str) -> int:
    cutoff = _iso(_utc_now() - timedelta(seconds=WEBHOOK_BURST_WINDOW_SECONDS))
    row = conn.execute(
        """
        SELECT COUNT(*) AS total
        FROM events
        WHERE event_type = ?
          AND received_at >= ?
        """,
        (event_type, cutoff),
    ).fetchone()
    return int(row["total"]) if row else 0


def _get_burst_state(
    conn: sqlite3.Connection, event_type: str
) -> sqlite3.Row | None:
    return conn.execute(
        "SELECT event_type, cooldown_until, last_alert_at FROM burst_state WHERE event_type = ?",
        (event_type,),
    ).fetchone()


def _is_in_cooldown(conn: sqlite3.Connection, event_type: str) -> bool:
    row = _get_burst_state(conn, event_type)
    if row is None or not row["cooldown_until"]:
        return False
    try:
        cooldown_until = datetime.fromisoformat(str(row["cooldown_until"]))
    except ValueError:
        return False
    if cooldown_until.tzinfo is None:
        cooldown_until = cooldown_until.replace(tzinfo=timezone.utc)
    return _utc_now() < cooldown_until


def _enter_burst_cooldown(
    conn: sqlite3.Connection,
    event_type: str,
    resource_ids: list[str],
) -> bool:
    """Enter cooldown and send one monitor alert. Returns True if newly entered."""
    now = _utc_now()
    row = _get_burst_state(conn, event_type)
    last_alert_at = str(row["last_alert_at"]) if row and row["last_alert_at"] else ""
    recently_alerted = False
    if last_alert_at:
        try:
            parsed = datetime.fromisoformat(last_alert_at)
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            recently_alerted = (now - parsed).total_seconds() < WEBHOOK_BURST_WINDOW_SECONDS
        except ValueError:
            recently_alerted = False

    cooldown_until = _iso(now + timedelta(seconds=WEBHOOK_BURST_WINDOW_SECONDS))
    conn.execute(
        """
        INSERT INTO burst_state (event_type, cooldown_until, last_alert_at)
        VALUES (?, ?, ?)
        ON CONFLICT(event_type) DO UPDATE SET
            cooldown_until = excluded.cooldown_until,
            last_alert_at = CASE
                WHEN excluded.last_alert_at IS NOT NULL THEN excluded.last_alert_at
                ELSE burst_state.last_alert_at
            END
        """,
        (event_type, cooldown_until, _iso(now) if not recently_alerted else last_alert_at),
    )

    if recently_alerted:
        return False

    from tools.telegram import send_operator_alert

    recent_count = _count_recent_events(conn, event_type)
    message = (
        f"Webhook burst circuit breaker engaged\n"
        f"event_type={event_type}\n"
        f"count={recent_count} in {WEBHOOK_BURST_WINDOW_SECONDS}s\n"
        f"contact_id_range={_contact_id_range(resource_ids)}"
    )
    send_operator_alert(message)
    log_event(
        "webhook",
        "burst_circuit",
        "start",
        detail=(
            f"event_type={event_type} count={recent_count} "
            f"contact_id_range={_contact_id_range(resource_ids)}"
        ),
        file=__file__,
        function="_enter_burst_cooldown",
    )
    return True


def _maybe_exit_burst_cooldown(conn: sqlite3.Connection, event_type: str) -> None:
    if _is_in_cooldown(conn, event_type):
        return
    row = _get_burst_state(conn, event_type)
    if row is None or not row["cooldown_until"]:
        return
    log_event(
        "webhook",
        "burst_circuit",
        "success",
        detail=f"event_type={event_type} cooldown ended",
        file=__file__,
        function="_maybe_exit_burst_cooldown",
    )
    conn.execute(
        "UPDATE burst_state SET cooldown_until = NULL WHERE event_type = ?",
        (event_type,),
    )


def enqueue_event(payload: dict[str, Any]) -> int:
    """Persist one webhook payload. Returns row id and terminal/non-terminal status."""
    init_db()
    event_type = str(payload.get("event") or "unknown")
    resource_ids = _resource_ids_from_payload(payload)
    received_at = _iso(_utc_now())
    payload_json = json.dumps(payload, separators=(",", ":"))

    with _connect() as conn:
        conn.execute("BEGIN IMMEDIATE")
        try:
            _maybe_exit_burst_cooldown(conn, event_type)

            status = "pending"
            if _is_in_cooldown(conn, event_type):
                status = "dropped_burst"
            else:
                recent_count = _count_recent_events(conn, event_type)
                if recent_count >= WEBHOOK_BURST_THRESHOLD:
                    _enter_burst_cooldown(conn, event_type, resource_ids)
                    status = "dropped_burst"

            cursor = conn.execute(
                """
                INSERT INTO events (received_at, event_type, payload, status, attempts)
                VALUES (?, ?, ?, ?, 0)
                """,
                (received_at, event_type, payload_json, status),
            )
            conn.commit()
            return int(cursor.lastrowid)
        except Exception:
            conn.rollback()
            raise


def reset_stale_processing(max_age_seconds: int) -> int:
    """Return processing rows to pending if older than max_age_seconds."""
    init_db()
    cutoff = _iso(_utc_now() - timedelta(seconds=max_age_seconds))
    with _connect() as conn:
        cursor = conn.execute(
            """
            UPDATE events
            SET status = 'pending'
            WHERE status = 'processing'
              AND received_at <= ?
            """,
            (cutoff,),
        )
        conn.commit()
        return int(cursor.rowcount)


def reclaim_all_processing() -> int:
    """Return all processing rows to pending (startup recovery)."""
    init_db()
    with _connect() as conn:
        cursor = conn.execute(
            """
            UPDATE events
            SET status = 'pending'
            WHERE status = 'processing'
            """
        )
        conn.commit()
        return int(cursor.rowcount)


def claim_next_event() -> dict[str, Any] | None:
    """Atomically claim the oldest pending event."""
    init_db()
    with _connect() as conn:
        conn.execute("BEGIN IMMEDIATE")
        row = conn.execute(
            """
            SELECT id, received_at, event_type, payload, status, attempts, last_error
            FROM events
            WHERE status = 'pending'
            ORDER BY id ASC
            LIMIT 1
            """
        ).fetchone()
        if row is None:
            conn.commit()
            return None

        updated = conn.execute(
            """
            UPDATE events
            SET status = 'processing', attempts = attempts + 1
            WHERE id = ? AND status = 'pending'
            """,
            (row["id"],),
        )
        if updated.rowcount != 1:
            conn.commit()
            return None
        conn.commit()
        return {
            "id": int(row["id"]),
            "received_at": str(row["received_at"]),
            "event_type": str(row["event_type"]),
            "payload": json.loads(str(row["payload"])),
            "status": "processing",
            "attempts": int(row["attempts"]) + 1,
            "last_error": row["last_error"],
        }


def mark_event_done(event_id: int) -> None:
    with _connect() as conn:
        conn.execute(
            "UPDATE events SET status = 'done', last_error = NULL WHERE id = ?",
            (event_id,),
        )
        conn.commit()


def mark_event_failed(event_id: int, error: str) -> None:
    with _connect() as conn:
        conn.execute(
            "UPDATE events SET status = 'failed', last_error = ? WHERE id = ?",
            (error[:2000], event_id),
        )
        conn.commit()


def count_events_by_status() -> dict[str, int]:
    init_db()
    with _connect() as conn:
        rows = conn.execute(
            "SELECT status, COUNT(*) AS total FROM events GROUP BY status"
        ).fetchall()
    return {str(row["status"]): int(row["total"]) for row in rows}
