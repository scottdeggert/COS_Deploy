"""Background consumer for durable FUB webhook queue."""

from __future__ import annotations

import signal
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.config import WEBHOOK_CONSUMER_POLL_SECONDS
from services.webhook_db import (
    claim_next_event,
    init_db,
    mark_event_done,
    mark_event_failed,
    reclaim_all_processing,
)
from tools.logger import log_event


def _shutdown_handler(signum: int, _frame: object) -> None:
    log_event(
        "webhook_consumer",
        "shutdown",
        "success",
        detail=f"signal={signum}",
        file=__file__,
        function="_shutdown_handler",
    )
    raise SystemExit(0)


def _dispatch_payload(payload: dict) -> None:
    from tools.webhook_server import _process_fub_event

    _process_fub_event(payload)


def run_consumer() -> None:
    init_db()
    # Residual risk: if Telegram send succeeds but the process dies before
    # _mark_notified(), reclaim replay can still duplicate Ben's alert.
    reclaimed = reclaim_all_processing()
    if reclaimed:
        log_event(
            "webhook_consumer",
            "reclaim_processing",
            "success",
            detail=f"count={reclaimed}",
            file=__file__,
            function="run_consumer",
        )

    log_event(
        "webhook_consumer",
        "start",
        "success",
        file=__file__,
        function="run_consumer",
    )

    while True:
        event = claim_next_event()
        if event is None:
            time.sleep(WEBHOOK_CONSUMER_POLL_SECONDS)
            continue

        event_id = int(event["id"])
        payload = event["payload"]
        try:
            _dispatch_payload(payload)
            mark_event_done(event_id)
            log_event(
                "webhook_consumer",
                "process_event",
                "success",
                detail=f"event_id={event_id} event={payload.get('event', 'unknown')}",
                file=__file__,
                function="run_consumer",
            )
        except Exception as exc:
            mark_event_failed(event_id, str(exc))
            log_event(
                "webhook_consumer",
                "process_event",
                "failure",
                detail=f"event_id={event_id} error={exc}",
                exc_info=exc,
                file=__file__,
                function="run_consumer",
            )


def main() -> None:
    signal.signal(signal.SIGTERM, _shutdown_handler)
    signal.signal(signal.SIGINT, _shutdown_handler)
    run_consumer()


if __name__ == "__main__":
    main()
