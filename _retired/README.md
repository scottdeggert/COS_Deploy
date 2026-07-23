# Retired modules (pre-refactor, not executed in production)

Moved 2026-07-23. Supervisord runs `python -m core.main`; nothing here is imported by the live tree.

| Path | Was | Live replacement |
|---|---|---|
| `agents/crewai/bot.py` | Monolithic Telegram bot + duplicate scheduler | `core/main.py`, `core/transport.py`, `core/router.py`, `handlers/*`, `core/scheduler.py` |
| `agents/crewai/main.py` | CLI entry to bot.py | `python -m core.main` |
| `tools/scheduler.py` | Legacy SimpleScheduler (bot.py only) | `core/scheduler.py` |
| `tools/intent_router.py` | Haiku classifier (bot.py only) | `core/router.py` |

Still live under `agents/crewai/`: `crew.py`, `config/agents.yaml`, `config/tasks.yaml` (used by `handlers/brief.py`).

Bot-only behaviors not carried forward (see Part 1C inventory): "Buenos dias" greeting variant, startup callback drain, hardcoded 8:30 schedule registration, count-only hot-leads digest copy.
