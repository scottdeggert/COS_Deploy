"""Hot leads handler -- list cooling leads and optionally draft outreach."""

from __future__ import annotations

from app.schemas import HandlerResult, RoutedIntent
from tools.hot_leads import get_hot_leads_going_cold
from tools.logger import log_event
from tools.telegram import send_operator_alert

FALLBACK_MESSAGE = (
    "I ran into a problem checking hot leads. Check FUB directly: "
    "https://app.followupboss.com"
)


def handle(intent: RoutedIntent) -> HandlerResult:
    """Handle hot_leads and hot_leads_list intents."""
    log_event(
        "hot_leads", "handle", "start",
        file=__file__, function="handle",
    )
    try:
        cold = get_hot_leads_going_cold(days_silent=14)
        if not cold:
            return HandlerResult(
                success=True,
                telegram_output="No Hot 90 Days leads going cold right now. Pipeline looks healthy.",
            )

        lines = [f"Here are your {len(cold)} hot leads going cold:\n"]
        for lead in cold:
            lines.append(
                f"* {lead['name']} -- {lead['stage']} -- "
                f"last activity {lead['last_activity']} ({lead['days_silent']} days ago)"
            )
        lines.append(
            "\nWant me to draft outreach for one or all of these? "
            "Reply with a name or \"draft all\"."
        )
        log_event(
            "hot_leads", "handle", "success",
            detail=f"{len(cold)} leads found",
            file=__file__, function="handle",
        )
        return HandlerResult(success=True, telegram_output="\n".join(lines))
    except Exception as exc:
        log_event(
            "hot_leads", "handle", "failure",
            detail=str(exc), exc_info=exc,
            file=__file__, function="handle",
        )
        send_operator_alert(f"Hot leads handler failed: {exc}")
        return HandlerResult(
            success=False,
            telegram_output=FALLBACK_MESSAGE,
            error_details=str(exc),
        )
