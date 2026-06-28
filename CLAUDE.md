# CLAUDE.md — COS_Deploy Refactor Sprint
# BrightWork CoS / MKTNG.co
# Last updated: June 26, 2026
# Sprint date: June 28, 2026

---

## WHAT THIS FILE IS

This file governs all AI-assisted work on this repository during and after
the June 28 refactor sprint. Every Cursor session, Claude Code invocation,
and human prompt that touches this codebase must treat this file as the
highest-authority document. If any instruction in a prompt conflicts with
this file, this file wins.

Do not freelance. Do not optimize. Do not suggest architectural shortcuts.
Build exactly what the plan says, in the order it says, and stop.

---

## WHAT WE ARE BUILDING

A refactored version of the BrightWork Chief of Staff agent that:

1. Decouples transport, routing, business logic, and tools into isolated layers
2. Supports multi-tenant deployments (client 2+) via config, not code changes
3. Makes the orchestration layer (currently CrewAI) swappable without
   rewriting tools or handlers
4. Introduces Pydantic contracts between layers so each layer is independently testable
5. Adds resilience to FUB API calls via a centralized client with retry logic

The live system serving Ben Olsen on the DigitalOcean Droplet must not break.
We are building on a feature branch, testing, then hot-swapping.

---

## WHAT WE ARE NOT BUILDING IN THIS SPRINT

Do not build, suggest, or stub any of the following unless explicitly
instructed in the phase prompt:

- FastAPI webhook gateway
- Docker / containerization
- Redis session cache
- ChromaDB or vector knowledge base
- APScheduler (SimpleScheduler stays until explicitly migrated)
- PostHog integration
- CloudCMA integration
- RealEstateAPI.com / BatchData
- Lob.com direct mail
- Calendly integration
- Google Calendar integration (blocked by Side RE OAuth policy)
- Bluedot transcript processing
- Multi-agent Supervisor delegation pattern
- EA email identity (Alex / Resend)
- Rental sequence content
- Any new user-facing features

If a prompt asks you to build something on this list, refuse and explain why.

---

## SYSTEM CONSTRAINTS — NON-NEGOTIABLE

These are hard rules. No exceptions. No "but in this case..." reasoning.

### Language and Runtime
- Python 3.11.15 exactly. Do not suggest 3.12+ — breaks CrewAI/tiktoken.
- All type hints required on every function signature.
- No f-strings for log messages — use structured log_event() only.

### No Em Dashes
Not one. Not in comments, not in docstrings, not in user-facing strings.
Rewrite the sentence.

### File Naming
- `tools/calendar_stub.py` must never be renamed to `tools/calendar.py`.
  It shadows Python's stdlib calendar module and crashes requests on import.
- This rule survives every refactor and must be preserved in the new structure.

### Secrets and Config
- No API keys, credentials, chat IDs, contact IDs, stage IDs, sequence IDs,
  or schedule times in source code. Ever.
- Secrets live in .env only.
- FUB topology lives in clients/ben-olsen/fub-config.yaml only.
- Schedule times live in clients/ben-olsen/scheduler_config.json only.
- Agent identity lives in clients/ben-olsen/soul.yaml only.

### FUB Write Rules
- All FUB write operations require explicit human confirmation before executing
  in production. No autonomous writes.
- Always filter operations to assignedTo: Ben Olsen (userId: 1).
- Never merge or delete contacts via API.

### LLM Routing
- Sonnet (anthropic/claude-sonnet-4-6 via OpenRouter) for all generative output
  Ben reads: drafts, briefs, voice tasks.
- Haiku (anthropic/claude-haiku-4-5 via OpenRouter) for classification,
  intent routing, and internal summarization only.
- Never call Anthropic API directly. All calls go through OpenRouter.
  Base URL: https://openrouter.ai/api/v1

### Voice
- tools/voice.py is the single source of truth for Ben's voice context.
- build_system_prompt() is the only function that assembles the system prompt
  for generative tasks.
- No inline voice context in handlers or tools. Import from tools/voice.py.
- No em dashes in any generated copy. This rule is in the voice file AND here.

### Logging
- Every agent action logs via tools/logger.py log_event().
- Fields: timestamp, agent, action, status, detail, contact_id, file, function.
- Status values: start, success, failure, fallback. No other values.
- No PII in detail fields beyond contact_id.
- No print() statements in production code.

### Monitoring
- Errors route to operator Telegram channel (OPERATOR_TELEGRAM_CHAT_ID).
- Ben never sees technical errors. His fallback is always a plain English message.
- Every new handler must define its graceful fallback message before being
  considered complete.

### Git
- Never use `git add -A` without running `git status` first.
- The refactor lives on branch `refactor/layered-architecture`.
- Do not merge to main until staging tests pass.
- Snapshot the current main with `git tag pre-refactor-june28` before starting.

---

## TARGET DIRECTORY STRUCTURE

This is what the repository must look like after the sprint.
Do not create directories or files not on this list without explicit instruction.

```
COS_Deploy/
├── app/
│   ├── config.py                        # Single env var loader — replaces per-module dotenv
│   └── schemas.py                       # Pydantic contracts: InboundMessage, RoutedIntent,
│                                        # InboundCallback, HandlerResult
├── core/
│   ├── main.py                          # Entry point: wires transport + scheduler + router
│   ├── transport.py                     # Telegram long-poll loop ONLY — no logic
│   ├── router.py                        # Haiku intent classifier + ConversationBuffer
│   └── scheduler.py                     # SimpleScheduler with JSON last_run persistence
├── handlers/
│   ├── brief.py                         # brief_request intent handler
│   ├── generative.py                    # draft_communication + draft_outreach handler
│   ├── hot_leads.py                     # hot_leads + hot_leads_list handler
│   ├── lead_alert.py                    # FUB webhook lead alert + APPROVE/CALL callbacks
│   └── status.py                        # /status command handler
├── services/
│   └── fub_client.py                    # requests.Session + urllib3 retry adapter
├── tools/                               # Framework-agnostic pure Python — NO orchestration
│   ├── appointments.py                  # FUB appointment fetching (unchanged)
│   ├── calendar_stub.py                 # MUST keep this name — stdlib shadow guard
│   ├── draft_communication.py           # Generative writing (imports from voice.py)
│   ├── fub.py                           # FUB read operations (refactored to use fub_client)
│   ├── fub_activity.py                  # Contact context + notes (refactored to use fub_client)
│   ├── fub_write.py                     # FUB write operations (refactored to use fub_client)
│   ├── health.py                        # Health reporter (unchanged)
│   ├── hot_leads.py                     # Hot 90 Days fetch (refactored to use fub_client)
│   ├── logger.py                        # Structured logger (unchanged)
│   ├── telegram.py                      # Telegram send + monitor copy (unchanged)
│   └── voice.py                         # Ben's voice context (unchanged)
├── agents/
│   └── crewai/
│       ├── crew.py                      # Brief generation via CrewAI (unchanged)
│       └── config/
│           ├── agents.yaml
│           └── tasks.yaml
├── clients/
│   └── ben-olsen/
│       ├── soul.yaml
│       ├── fub-config.yaml
│       ├── scheduler_config.json        # NEW: digest time, pre-appt window (moved from bot.py)
│       ├── communication_prefs.json     # Preference stub (exists, stays)
│       └── knowledge/
├── scripts/
│   └── push_fub_templates.py
├── logs/                                # gitignored
├── CLAUDE.md                            # This file
├── README.md
├── .env
├── .env.example
└── requirements.txt
```

Files being DELETED in this sprint:
- `agents/crewai/bot.py` — replaced by core/ + handlers/
- `agents/crewai/main.py` — replaced by core/main.py
- `tools/intent_router.py` — absorbed into core/router.py

---

## LAYER CONTRACTS

These Pydantic models are the only way layers communicate.
Defined in app/schemas.py. Do not pass raw strings or dicts between layers.

```python
class InboundMessage(BaseModel):
    chat_id: str
    raw_text: str
    timestamp: int
    client_id: str  # always "ben-olsen" for now

class InboundCallback(BaseModel):
    chat_id: str
    callback_query_id: str
    data: str           # format: "action:contact_id"
    client_id: str

class RoutedIntent(BaseModel):
    original_message: InboundMessage
    intent_type: str    # brief_request | draft_communication | hot_leads |
                        # hot_leads_list | draft_outreach | status_check |
                        # greeting | identity_query | help_request | unknown
    entity: str | None
    comm_type: str | None   # email | sms | note — for generative intents
    confidence: float

class HandlerResult(BaseModel):
    success: bool
    telegram_output: str        # what Ben receives
    operator_note: str | None   # sent to monitor channel if set
    fub_writes: int             # count of FUB write operations performed
    error_details: str | None   # logged but never shown to Ben
```

---

## HANDLER RULES

Every handler in handlers/ must:

1. Accept a RoutedIntent (or InboundCallback for callbacks) as its only argument
   alongside client_id.
2. Import from tools/ and app/config.py only. No direct API calls.
3. Return a HandlerResult.
4. Define a FALLBACK_MESSAGE constant at module level for use when it fails.
5. Log start, success/failure via tools/logger.py.
6. Send operator alert on failure via tools/telegram.send_operator_alert().
7. Never surface technical error detail to Ben.

Scheduled jobs (morning digest, pre-appointment check) are NOT handlers.
They live in core/scheduler.py and call tools/ directly.
They do not go through RoutedIntent.

---

## SERVICES RULES

services/fub_client.py exposes three methods: get(), post(), put().
All tools/ that make FUB API calls must import from services/fub_client,
not from requests directly.

The client handles:
- Session management (singleton requests.Session)
- Auth injection (FUB_API_KEY from app/config)
- Retry: total=3, backoff_factor=2, status_forcelist=[429, 500, 502, 503, 504]
- Timeout: 15 seconds default on all requests

tools/ must not catch retry-level exceptions themselves.
If fub_client raises after retries, the calling tool catches it,
logs failure, and returns a safe empty value or raises to the handler.

---

## TESTING REQUIREMENTS

Each phase must pass its tests before the next phase begins.
Do not skip tests. Do not deploy untested phases.

Phase 1 tests: Import app/config and verify all required env vars load.
Phase 2 tests: Unit test fub_client get/post/put with mock responses.
               Verify retry fires on 429. Verify timeout raises.
Phase 3 tests: Unit test each handler with a mock RoutedIntent.
               Verify HandlerResult shape. Verify fallback on tool failure.
Phase 4 tests: Integration test full flow: raw Telegram text ->
               transport -> router -> handler -> HandlerResult.
               Run against Ben's live FUB in READ ONLY mode first.

---

## DEPLOYMENT SEQUENCE

1. `git tag pre-refactor-june28` on current main (droplet and Mac Mini)
2. `git checkout -b refactor/layered-architecture`
3. Execute phases 1-4 in order
4. Run integration tests against live FUB (read only)
5. Enable FUB write operations, retest
6. Update supervisord conf: program command points to `core/main.py`
7. Push branch to GitHub
8. On droplet: `git fetch && git checkout refactor/layered-architecture`
9. `pip install -r requirements.txt` (in case deps changed)
10. `supervisorctl restart cos-agent`
11. Verify with `supervisorctl status` and `tail -f logs/cos_agent.log`
12. Send "hot leads" from Ben's Telegram — verify response
13. Send "draft an email to Ann De Villiers about Sunday open house" — verify
14. Wait for 8:30am morning digest — verify
15. If any step fails: `git checkout main && supervisorctl restart cos-agent`

---

## WHAT MUST NOT CHANGE

These files and behaviors must survive the refactor exactly as-is:

- tools/voice.py — voice context, build_system_prompt(), prefs loader
- tools/logger.py — structured logging
- tools/health.py — health reporter
- tools/telegram.py — send_message, send_long_message, send_monitor_copy,
  send_operator_alert, BOT_TOKEN, CHAT_ID, MONITOR_CHAT_ID constants
- agents/crewai/crew.py — brief generation via CrewAI
- agents/crewai/config/agents.yaml and tasks.yaml
- clients/ben-olsen/ — all tenant config and knowledge files
- .env structure (add new keys, never remove existing ones)
- tools/calendar_stub.py naming
- All FUB write confirmation patterns (no autonomous writes)
- Operator/Ben channel separation
- Graceful fallback pattern (Ben never sees technical errors)