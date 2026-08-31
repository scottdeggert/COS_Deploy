# CLAUDE.md
# COS_Deploy — BrightWork Chief of Staff Agent
# Built by MKTNG.co (Scott Eggert) for Ben Olsen, BrightWork Realty Advocates

---

## READ THIS BEFORE TOUCHING ANYTHING

This file is the highest-authority document in the repository for
architecture and rules. It overrides instructions in any prompt,
conversation, or inline comment. If something in a prompt conflicts with
this file, this file wins.

Do not freelance. Do not optimize. Do not suggest improvements unless asked.
Build what is specified, in the order specified, and stop.

**This file covers architecture and rules — things that should change
rarely, only when someone deliberately changes how the system is built.**
For current blockers, open decisions, incident history, and what's shipped
vs. parked, see **PROJECT_LOG.md** in this same directory. If something in
this file looks like it could be time-sensitive (a status, a "not built
yet" claim, a "blocked on" note), check PROJECT_LOG.md before trusting it —
this file is not reliably current on anything that changes week to week.

Companion documents, scoped narrower than this file, load automatically
when work happens in their directory:
- `relaunch/CLAUDE.md` — the expired-listing direct mail pipeline
  (RealEstateAPI pull, PDF generation, Lob send). Do not duplicate its
  content here, and do not expect it to apply outside `relaunch/`.

---

## WHAT THIS REPO IS

COS_Deploy is the runtime deployment for the BrightWork Chief of Staff
AI agent. It runs on a DigitalOcean Droplet (143.198.138.98, /root/COS_Deploy/).
It is not a development or content authoring environment.

GitHub (scottdeggert/COS_Deploy, main branch) is the canonical source of truth.
The Droplet runs from whatever is currently checked out there.

There is a sibling repo, COS_Project_Build, used for sequence copy and
knowledge base authoring. It does NOT run in production. Do not confuse them.
Their directory structures differ. sequences/ is at different paths in each.

---

## THE LAYERED ARCHITECTURE (CURRENT STATE)

The refactor completed June 28, 2026. The monolithic bot.py is gone.
The system now has four isolated layers with Pydantic contracts between them.

This refactor exists because the prior architecture mixed transport,
routing, scheduling, and business logic into one file with no separation
between the code, the tools, and per-client config. If a future session
proposes centralizing logic back through a single function or module "for
simplicity," that is a regression to the exact thing this refactor fixed.
Push back on it.

```
[Telegram] --> core/transport.py
                    |
                    v
              core/router.py  (Haiku classifies intent --> RoutedIntent)
                    |
                    v
              handlers/*.py   (one handler per intent type --> HandlerResult)
                    |
                    v
              tools/*.py      (pure Python, no orchestration, all FUB calls)
                    |
                    v
              services/fub_client.py  (requests.Session + retry adapter)
                    |
                    v
              [Follow Up Boss API]
```

Scheduled jobs (morning digest, pre-appointment brief) bypass this chain.
They live in core/scheduler.py and call tools/ directly.
They do not produce RoutedIntent or HandlerResult.

[FUB webhooks] --> tools/webhook_server.py --> tools/activity_feed.py
                                                      |
                                                      v
                                              core/scheduler.py (digest)

tools/watchdog.py runs as a subprocess of core/main.py (not supervisord).
It monitors scheduled job effect via logs/scheduler_state.json.

The `relaunch/` pipeline (direct mail: expired listings) is a separate,
independently-triggered module. It does not go through this chain — it has
no Telegram inbound routing of its own beyond one scoped callback exception
(see Telegram Callback Routing, below). See `relaunch/CLAUDE.md` for its
internal structure.

---

## LAYER SEPARATION RULES — NON-NEGOTIABLE

These rules exist because mixing layers was the primary source of drift
in the previous architecture. Enforce them unconditionally.

### Transport layer (core/transport.py)
- Receives raw Telegram updates. That is its entire job.
- No intent classification. No business logic. No FUB calls.
- Passes InboundMessage or InboundCallback to router/handlers only.
- If you find yourself adding a conditional to transport.py, stop.
  That logic belongs in router.py or a handler.
- **Exception, narrowly scoped:** the Ben-only callback gate
  (`cb_chat_id == configured_chat_id`) must never be widened to accept
  other chat IDs. If a new feature needs a callback from a different chat
  (e.g. the operator channel), add a separate, explicit check alongside the
  gate — matched on both chat ID and a callback_data prefix specific to
  that feature — rather than loosening what the shared gate itself accepts.
  This pattern is already in use for `relaunch_send:` callbacks from
  `OPERATOR_TELEGRAM_CHAT_ID`. Follow it for any future operator-facing
  callback rather than inventing a new mechanism.

### Router layer (core/router.py)
- Classifies intent via Haiku. Returns RoutedIntent.
- No FUB calls. No Telegram sends. No business logic.
- Maintains ConversationBuffer for multi-turn context.
- If you find yourself calling a FUB tool inside router.py, stop.
  That belongs in a handler or scheduled job.

### Handler layer (handlers/*.py)
- One file per intent cluster. Each handler does one thing.
- Imports from tools/ and app/config only. Nothing else.
- Returns HandlerResult. Always. Every exit path.
- Defines FALLBACK_MESSAGE at module level.
- Logs start + success/failure via tools/logger.py.
- Sends operator alert on failure. Never shows technical errors to Ben.
- If you find yourself making a direct requests call inside a handler, stop.
  That belongs in tools/ using services/fub_client.

### Tools layer (tools/*.py)
- Framework-agnostic pure Python. No handler imports. No orchestration.
- All FUB API calls go through services/fub_client — never requests directly.
- Can be tested and called independently of any handler or framework.
- If a tool starts importing from handlers/ or core/, that is a dependency
  inversion bug. Fix it.

### Services layer (services/fub_client.py)
- Single FUB HTTP client: get(), post(), put().
- Handles auth, retry, and timeout. Nothing else.
- No business logic. No FUB-specific knowledge about endpoints.
- If you find yourself adding a "get_contacts" method here, stop.
  Endpoint knowledge belongs in tools/.

### Config layer (app/config.py)
- Single env var loader. All config flows from here.
- No other module calls os.environ or os.getenv directly.
- If you see os.environ.get() outside of app/config.py, that is a bug —
  **with one scoped exception:** `relaunch/` loads its own `.env` directly
  (`trigger.py`, `mail/send.py`), by design, not by drift. This keeps
  `LOB_API_KEY`, a payment-capable and physical-mail-triggering credential,
  out of `cos-agent`'s shared process environment entirely. Do not "fix"
  this by routing it through `app/config.py` — that would undo the
  isolation on purpose. See `relaunch/CLAUDE.md` for the reasoning.

### Schemas (app/schemas.py)
- Pydantic contracts: InboundMessage, InboundCallback, RoutedIntent, HandlerResult.
- The only legal way to pass data between layers.
- Do not pass raw strings or dicts between layers. Use the models.

---

## TENANT SEPARATION RULES

clients/ben-olsen/ contains everything specific to Ben Olsen.
No Ben-specific values live anywhere else in the codebase.

This means:
- FUB stage IDs: clients/ben-olsen/fub-config.yaml only
- Action plan IDs: clients/ben-olsen/fub-config.yaml only
- Agent identity and archetype: clients/ben-olsen/soul.yaml only
- Scheduler timing (digest hour, pre-appt window): clients/ben-olsen/scheduler_config.json only
- Communication preferences: clients/ben-olsen/communication_prefs.json only
- Voice context: tools/voice.py loads from the client config path, not hardcoded
- Knowledge base: clients/ben-olsen/knowledge/ only

When client 2 is onboarded, the only change is adding clients/{name}/ and
passing the correct client_id through InboundMessage. No changes to handlers,
tools, or services.

If you find a FUB stage ID, a Telegram chat ID, a schedule time, or
a realtor-specific string hardcoded anywhere outside clients/, that is a bug.

**Known exception, not yet resolved:** `relaunch/` does not follow this
pattern. `SENDER_NAME` / office address live in `relaunch/.env`, and
`ACTIVE_CLIENT = "Ben"` is hardcoded in the REAPI pull config, neither
under `clients/ben-olsen/`. This was acceptable for a single-tenant build
and is now tracked debt — see PROJECT_LOG.md — that must be resolved
before a second client's mail pipeline can be onboarded without duplicating
or forking the relaunch codebase.

---

## ZERO-HARDCODING POLICY

Nothing configurable lives in source code. Full stop.

| What | Where |
|---|---|
| API keys, tokens, credentials | .env |
| FUB stage IDs, action plan IDs, user ID | clients/ben-olsen/fub-config.yaml |
| Telegram chat IDs | .env (TELEGRAM_CHAT_ID, TELEGRAM_MONITOR_CHAT_ID) |
| Digest time, pre-appt window, silence days | clients/ben-olsen/scheduler_config.json |
| Agent identity, archetype, personality | clients/ben-olsen/soul.yaml |
| Communication preferences | clients/ben-olsen/communication_prefs.json |
| Model strings | agents/crewai/config/agents.yaml |

---

## CURRENT DIRECTORY STRUCTURE

```
COS_Deploy/
├── app/
│   ├── config.py               # Env var loader — all config flows from here (see relaunch/ exception above)
│   └── schemas.py              # Pydantic layer contracts
├── core/
│   ├── main.py                 # Entry point: wires transport + scheduler + router + watchdog
│   ├── transport.py            # Telegram long-poll — no logic
│   ├── router.py               # Haiku intent classifier + ConversationBuffer
│   └── scheduler.py            # Scheduled jobs with atomic JSON state persistence
├── handlers/
│   ├── brief.py                # brief_request
│   ├── generative.py           # draft_communication + draft_outreach
│   ├── hot_leads.py            # hot_leads + hot_leads_list
│   ├── lead_alert.py           # FUB webhook lead alert + APPROVE/CALL callbacks
│   └── status.py               # /status command
├── services/
│   ├── fub_client.py           # requests.Session + urllib3 retry (3 retries, 2x backoff)
│   └── google_calendar.py      # Google Calendar OAuth + read-only event fetch
├── tools/                      # Framework-agnostic pure Python
│   ├── activity_feed.py        # Webhook-captured inbound activity, feeds the digest
│   ├── appointments.py
│   ├── calendar_stub.py        # NEVER rename — see naming rules below
│   ├── draft_communication.py  # Imports voice context from tools/voice.py
│   ├── fub.py
│   ├── fub_activity.py
│   ├── fub_write.py
│   ├── google_calendar.py      # Morning digest schedule helpers
│   ├── health.py
│   ├── hot_leads.py
│   ├── logger.py
│   ├── telegram.py
│   ├── voice.py                # Single source of truth for Ben's voice
│   ├── watchdog.py             # Deadman's switch + error classification (subprocess of core/main)
│   ├── web_fetch.py            # Allowlisted HTTP fetch (not wired to router/handlers)
│   └── webhook_server.py       # FUB webhook receiver (supervisor: webhook-server)
├── agents/
│   └── crewai/
│       ├── crew.py             # Brief generation via CrewAI (LIVE — imported by handlers/brief.py)
│       └── config/
│           ├── agents.yaml     # Model strings live here, not in Python files
│           └── tasks.yaml
├── clients/
│   └── ben-olsen/
│       ├── soul.yaml
│       ├── fub-config.yaml
│       ├── scheduler_config.json
│       ├── communication_prefs.json
│       ├── google_calendar_config.json
│       ├── knowledge/
│       └── sequences/          # Sequence copy (runtime reads templates via FUB, not these files directly)
├── relaunch/                   # Direct mail pipeline (expired listings). Own CLAUDE.md, own .env.
│   ├── CLAUDE.md               # Pipeline-specific rules — read before touching this directory
│   ├── pull/                   # RealEstateAPI extraction
│   ├── scrub/                  # Eligibility filtering, entity detection
│   ├── generate/                # PDF packet generation (OpenRouter/Sonnet)
│   ├── mail/                   # Lob send
│   ├── assets/                 # Static one-sheets, fonts, Ben bio PDF
│   ├── config/                 # Market benchmarks, community flags
│   ├── batches/                # Per-batch working directories
│   ├── logs/                   # Pipeline + run logs
│   ├── tests/                  # Regression tests (entity detection, salutation)
│   └── trigger.py              # Cron entrypoint
├── tests/
│   └── test_web_fetch.py       # Standalone unit tests for tools/web_fetch.py
├── scripts/
│   ├── audit_action_plan_templates.py
│   └── discover_activity.py
├── _retired/                   # July 23, 2026 retirement — NOT on import path (see below)
│   ├── README.md
│   ├── agents/crewai/
│   │   ├── bot.py
│   │   └── main.py
│   └── tools/
│       ├── intent_router.py
│       └── scheduler.py
├── platform/                   # Architecture and playbook docs (not runtime code)
├── logs/                       # gitignored (scheduler_state.json, process logs)
├── mcp_server.py               # MCP API server (supervisor: mcp-server)
├── push_fub_templates.py       # One-off FUB template push utility
├── CLAUDE.md                   # This file
├── PROJECT_LOG.md              # Roadmap, open items, incident history — check this for anything time-sensitive
├── README.md
├── .env                        # gitignored, never commit. No LOB_API_KEY — see relaunch/.env
├── .env.example
└── requirements.txt
```

### Retired code (July 23, 2026)

Moved to `_retired/` (not deleted):
- `_retired/agents/crewai/bot.py`
- `_retired/agents/crewai/main.py`
- `_retired/tools/scheduler.py`
- `_retired/tools/intent_router.py`

Still LIVE (do not retire):
- `agents/crewai/crew.py` and `agents/crewai/config/*.yaml` — imported by `handlers/brief.py`

`_retired/` is not on the import path. Never edit it. Never read it as a reference
for how the system behaves. See PROJECT_LOG.md for why `bot.py` was retired.

---

## HARD RULES

### No em dashes
Not in code, comments, docstrings, or any string Ben reads. Not one.
Rewrite the sentence. This rule is also in tools/voice.py.

### calendar_stub.py must never be renamed
Previously calendar.py, which shadowed Python's stdlib calendar module
and crashed requests on import. The stub name is intentional and permanent.

### Python version
3.12 on the Droplet. Do not suggest version changes without confirming
the full dependency chain.

### No print() in production code
All logging goes through tools/logger.py log_event() only.
Status values: start, success, failure, fallback. No others.
No PII in detail fields. Contact ID only.

### No direct requests calls in handlers
All HTTP calls to FUB go through services/fub_client. Always.

### No inline voice context
tools/voice.py and build_system_prompt() are the only place voice context
is assembled. No handler or tool duplicates voice rules inline.

### Model strings in YAML only
Model strings (anthropic/claude-sonnet-4-6, anthropic/claude-haiku-4-5)
live in agents/crewai/config/agents.yaml. Not in Python files.

### OpenRouter only
All LLM inference routes through OpenRouter (https://openrouter.ai/api/v1).
Never call the Anthropic API directly for inference.
Haiku for classification. Sonnet for anything Ben reads.

### Never verify a running process's environment via /proc
`/proc/<pid>/environ` reflects exec-time environment only. It does not
update when code calls `load_dotenv()` after startup, and will give a
false pass for credential-isolation checks. Verify from file contents and
load order instead.

---

## FUB RULES

### Write confirmation required
All FUB write operations require explicit human confirmation before executing
in production. No autonomous writes. No exceptions — including automated
writes that fire as a *consequence* of an already-confirmed human action.
(Example: `relaunch/`'s dormant-contact tagging fires automatically on a
successful Lob send, but that send only happens after an explicit human tap
on an approval button. The confirmation is the tap; the tag write is a
downstream effect of it, not a second autonomous decision. If you build
something similar, make sure the causal chain back to a human action is
that direct and undeniable before treating a write as "confirmed.")

### Always filter to Ben
Every FUB operation filters to assignedTo: Ben Olsen (userId: 1).

### Suppression tag enforcement
Suppression tags are enforced at BOTH the sequence-enrollment path and the digest
activity-surfacing path. A tag that suppresses marketing must also suppress the
contact from surfacing in briefs. These are separate code paths and wiring only
one is a defect.

Current suppression tags:
- Unsubscribed and Bounced (email hard stops)
- #NeverMail (direct mail)
- Realtor (competitor and industry contacts, no marketing enrollment, no brief surfacing)

Current enforcement status of each tag, and any open defects: see PROJECT_LOG.md.

### Known FUB platform constraints (permanent, confirmed)
- /v1/emails returns [CONTENT HIDDEN] on all records. Email body is inaccessible.
  There is no permission setting that changes this. This is not a bug to fix.
- isHtml in template payload causes HTTP 400. Omit it. FUB auto-detects HTML.
- Merge tags: %contact_first_name% for HTML. [first name] for plain text.
- No Day 0 in Action Plans. Sequences start at Day 1.
- Action Plan creation is UI-only. There is no REST endpoint for it.
- /v1/appointments ignores minDate/startDate server-side. Filter in Python.
- Tag filter: /v1/people?tags=Hot+90+Days (exact case, URL-encoded space).
- FUB source field is stale creation-time data. Use _get_source_from_events()
  to parse "via: [url]" from the most recent event message instead.
- No merge API. Contact merges are UI-only under Mass Actions.
- Rate limits: sliding 10-second window. ~180-200 global, 20 for events,
  10 for notes. Requires X-System-Key header registered separately.
- Template naming: [sequence-slug] - Day [N] - [subject line]
- Haiku wraps JSON in markdown code fences despite instructions. Strip before parsing.
- OpenRouter Haiku responses have leading whitespace before JSON. Use resp.text.strip().

### No autonomous outbound
All client-facing sends require Ben to review and approve first.
The agent drafts. Ben sends. (`relaunch/`'s direct mail follows the same
principle with a different reviewer — see that module's CLAUDE.md.)

---

## MONITORING RULES

- Errors route to TELEGRAM_MONITOR_CHAT_ID (operator channel).
- Ben never sees a technical error. Every handler defines a plain English fallback.
- Operator channel is separate from Ben's bot. Never cross them.
- Every scheduled job logs success or failure via log_event().
- Silent skips are prohibited. Any code path that DECLINES to run a scheduled job
  must log the reason (window not reached, already sent for today, past catch-up cutoff).
  A job that decides not to act must leave a trace.
- Absence monitoring is required, not just failure monitoring. tools/watchdog.py
  implements a deadman's switch: for each scheduled job, if no run is recorded for
  today's Pacific date past a configured backstop, alert the operator. Failure-only
  monitoring cannot detect a job that never runs.
- Monitoring must verify effect, not log lines. Any health check must assert the
  work actually happened (e.g. reading a persisted state value the job itself
  writes), not just that a success line was logged.
- The deadman backstop must fall AFTER the catch-up cutoff. Backstop earlier than
  scheduled time plus catch_up_hours produces false alarms for a job still eligible
  to send.

For the specific incidents that established each of these rules, see
PROJECT_LOG.md — several were fixed exactly once and must not regress.

---

## TESTING AND VERIFICATION

- Ad-hoc investigation scripts that call live FUB (or any path that may log
  status=failure) MUST set COS_DIAGNOSTIC_MODE=1 in the process environment
  before the probe, and unset it after. Example:
  `COS_DIAGNOSTIC_MODE=1 /root/COS_Deploy/venv/bin/python <<'PY' ...`
- When set: log_event still writes to cos_agent.log (with diagnostic=true),
  send_operator_alert skips Telegram, and tools/watchdog.py ignores those
  lines. Production supervisord processes must never set this flag.
- Crash/idempotency simulation of the webhook queue must use a separate SQLite
  file whose path contains "test" (e.g. logs/webhook_queue.test.db) and must
  not write to the production webhook_queue.db or lead_alert_state.json.
- There is no staging bot. All testing runs against the same token and
  process serving Ben. This is a known structural risk — see PROJECT_LOG.md.

---

## SCHEDULER RULES

- All scheduler time math uses zoneinfo America/Los_Angeles. Never a static UTC offset.
  timezone_offset_hours remains in config for backward compatibility but must never be
  used for window math. A static offset breaks at DST changes and makes time
  comparisons impossible to reason about.
- Daily job fire gates are DATE-based, never hour-based. Gate on whether the job has
  already run for today's Pacific date. An hour-based gate that never resets after a
  successful run can permanently disable a job.
- Daily jobs use a catch-up window (scheduled time to scheduled time plus catch_up_hours),
  not a narrow fixed-minute window. A five-minute window on a 60-second tick loop means
  any restart or slow tick across that window silently skips the job for the whole day.
- Scheduled jobs never send late. Past the catch-up cutoff, skip and log.
- State writes must be atomic: write to a temp file in logs/, flush, os.fsync, then
  os.replace. A non-atomic write can corrupt state and disable scheduled jobs entirely.
- No code path may save a stale state object over a newer write. Any job that saves state
  must reload it immediately before saving, or a concurrent job's write can be silently
  overwritten by one loaded earlier in the same tick.

---

## VOICE RULES

- tools/voice.py is the single source of truth.
- build_system_prompt() assembles system prompt for all generative tasks.
- No inline voice rules in handlers, tools, or prompts.
- No em dashes. Not in copy, not in drafts, not in generated text. Never.
- Ben's voice file loads on every generative request via _handle_generative_request.

---

## WHAT MUST NOT CHANGE WITHOUT EXPLICIT INSTRUCTION

- tools/voice.py
- tools/logger.py
- tools/health.py
- tools/telegram.py
- tools/calendar_stub.py (and its name)
- agents/crewai/crew.py
- agents/crewai/config/agents.yaml and tasks.yaml
- clients/ben-olsen/ (any file — changes require explicit scope)
- .env structure (add keys, never remove)
- All FUB write confirmation patterns
- Operator/Ben channel separation
- The Ben-only Telegram callback gate in core/transport.py (see Layer
  Separation Rules — add scoped exceptions alongside it, never widen it)

---

## WHAT IS NOT BUILT YET (DO NOT STUB OR SUGGEST)

Unless explicitly scoped in a prompt, do not build or mention:
- Docker / containerization
- Redis session cache
- ChromaDB or vector knowledge base
- PostHog integration
- CloudCMA integration
- Calendly integration (native FUB sync status unconfirmed)
- Bluedot transcript processing
- EA email identity (Alex / Resend)
- Rental sequence content
- Communication memory write path (stub exists, read path only)
- Multi-agent Supervisor delegation

**This list must be updated in the same commit that ships any of these
features.** It went stale once already — RealEstateAPI.com/BatchData and
Lob.com direct mail were both listed here after they had already shipped as
`relaunch/`, discovered only when someone compared this file against actual
running code. Before trusting this list, check PROJECT_LOG.md's most recent
shipped-feature entries.

---

## AGENT IDENTITY

The agent has no confirmed name. Do not assign one.
Do not reference "Scout" (retired placeholder).
Use "Chief of Staff" in user-facing strings.
Use "cos_agent" in code identifiers.
Ben Olsen decides the name. Current status: see PROJECT_LOG.md.

---
---

## LOGGING RULE — READ BEFORE ENDING ANY SESSION

Use /log-entry (see .claude/skills/log-entry/) to write to PROJECT_LOG.md.
Do this unprompted, as the last step of any session, if what you did
clears any of these:

1. Would a future session waste real investigation time rediscovering
   this, if it happened again?
2. Could a future session make a change that looks locally reasonable but
   is actually wrong, because it doesn't have this context?
3. Does this open or close something already on record as OPEN in
   PROJECT_LOG.md?
4. Does it change what's true anywhere in CLAUDE.md that makes a
   point-in-time claim (the "not built yet" list, a directory structure,
   an "OPEN" or "blocked on" note)?

If none apply — a fix with an obvious cause, a refactor with no behavior
change, a copy edit — don't log it. When genuinely unsure, log it anyway.
A low-value entry costs a few lines to read past. A missing one costs a
future session real time, or a real mistake, rediscovering something you
already knew.

If item 4 applies, update CLAUDE.md itself in the same pass, not just the
log. This is exactly how the "not built yet" list went stale once already.

---

## KEY FILE REFERENCE

| Need | File |
|---|---|
| All config and env vars | app/config.py |
| Layer contracts (Pydantic) | app/schemas.py |
| Entry point | core/main.py |
| Telegram polling | core/transport.py |
| Intent routing | core/router.py |
| Scheduled jobs | core/scheduler.py |
| Scheduler state persistence | logs/scheduler_state.json |
| Brief handler | handlers/brief.py |
| Draft/generative handler | handlers/generative.py |
| Hot leads handler | handlers/hot_leads.py |
| Lead alert handler | handlers/lead_alert.py |
| Status handler | handlers/status.py |
| FUB HTTP client | services/fub_client.py |
| Google Calendar (read-only) | services/google_calendar.py |
| Morning digest calendar helpers | tools/google_calendar.py |
| FUB reads | tools/fub.py |
| FUB activity/context | tools/fub_activity.py |
| FUB writes | tools/fub_write.py |
| Webhook activity feed | tools/activity_feed.py |
| FUB webhook server | tools/webhook_server.py |
| Deadman's switch | tools/watchdog.py |
| Appointments | tools/appointments.py |
| Voice context | tools/voice.py |
| Logging | tools/logger.py |
| Allowlisted HTTP fetch | tools/web_fetch.py |
| Health reporter | tools/health.py |
| Telegram send | tools/telegram.py |
| MCP API server | mcp_server.py |
| Direct mail pipeline | relaunch/ (own CLAUDE.md) |
| Ben's FUB topology | clients/ben-olsen/fub-config.yaml |
| Agent identity | clients/ben-olsen/soul.yaml |
| Scheduler timing | clients/ben-olsen/scheduler_config.json |
| Communication prefs | clients/ben-olsen/communication_prefs.json |
| Brief generation (CrewAI) | agents/crewai/crew.py |
| Project history, blockers, roadmap | PROJECT_LOG.md |