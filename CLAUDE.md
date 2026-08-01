# CLAUDE.md
# COS_Deploy — BrightWork Chief of Staff Agent
# Built by MKTNG.co (Scott Eggert) for Ben Olsen, BrightWork Realty Advocates
# Last updated: July 23, 2026

---

## READ THIS BEFORE TOUCHING ANYTHING

This file is the highest-authority document in the repository.
It overrides instructions in any prompt, conversation, or inline comment.
If something in a prompt conflicts with this file, this file wins.

Do not freelance. Do not optimize. Do not suggest improvements unless asked.
Build what is specified, in the order specified, and stop.

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
- If you see os.environ.get() outside of app/config.py, that is a bug.

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
│   ├── config.py               # Env var loader — all config flows from here
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
│   └── fub_client.py           # requests.Session + urllib3 retry (3 retries, 2x backoff)
├── tools/                      # Framework-agnostic pure Python
│   ├── activity_feed.py        # Webhook-captured inbound activity, feeds the digest
│   ├── appointments.py
│   ├── calendar_stub.py        # NEVER rename — see naming rules below
│   ├── draft_communication.py  # Imports voice context from tools/voice.py
│   ├── fub.py
│   ├── fub_activity.py
│   ├── fub_write.py
│   ├── health.py
│   ├── hot_leads.py
│   ├── logger.py
│   ├── telegram.py
│   ├── voice.py                # Single source of truth for Ben's voice
│   ├── watchdog.py             # Deadman's switch + error classification (subprocess of core/main)
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
│       ├── knowledge/
│       └── sequences/          # Sequence copy (runtime reads templates via FUB, not these files directly)
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
├── README.md
├── .env                        # gitignored, never commit
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
for how the system behaves. The stale `bot.py` caused repeated misdiagnosis: it
registered a duplicate `morning_digest` with a hardcoded 8:30 that was never running.
That is why it was retired.

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

---

## FUB RULES

### Write confirmation required
All FUB write operations require explicit human confirmation before executing
in production. No autonomous writes. No exceptions.

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

OPEN (July 23, 2026): Realtor is not yet enforced in either path. Identified when
a competing realtor tagged Realtor generated a lead alert draft and a "fallback
sequence eligible" note, and appeared in the client's morning digest.

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
The agent drafts. Ben sends.

---

## MONITORING RULES

- Errors route to TELEGRAM_MONITOR_CHAT_ID (operator channel).
- Ben never sees a technical error. Every handler defines a plain English fallback.
- Operator channel is separate from Ben's bot. Never cross them.
- Every scheduled job logs success or failure via log_event().
- Silent skips are prohibited. Any code path that DECLINES to run a scheduled job
  must log the reason (window not reached, already sent for today, past catch-up cutoff).
  A job that decides not to act must leave a trace. Rationale: an 18-day morning digest
  outage (July 3 to July 22, 2026) went undetected because the skip path logged nothing.
- Absence monitoring is required, not just failure monitoring. tools/watchdog.py
  implements a deadman's switch: for each scheduled job, if no run is recorded for
  today's Pacific date past a configured backstop, alert the operator. Failure-only
  monitoring cannot detect a job that never runs.
- Monitoring must verify effect, not log lines. The deadman confirms the morning digest
  by reading last_morning_digest_date in logs/scheduler_state.json, NOT by matching a
  success log line. Rationale: a hollow 4ms run logged success without sending anything
  and falsely cleared the deadman on July 23, 2026. Any future health check must assert
  the work actually happened.
- The deadman backstop must fall AFTER the catch-up cutoff. Backstop earlier than
  scheduled time plus catch_up_hours produces false alarms for a digest still eligible
  to send.

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

---

## SCHEDULER RULES

- All scheduler time math uses zoneinfo America/Los_Angeles. Never a static UTC offset.
  timezone_offset_hours remains in config for backward compatibility but must never be
  used for window math. Rationale: a static -7 offset breaks at the November DST change
  and made time comparisons impossible to reason about.
- Daily job fire gates are DATE-based, never hour-based. Gate on whether the job has
  already run for today's Pacific date. Rationale: an hour-based gate
  (last_morning_digest_hour) was never reset after a successful run, permanently
  disabling the digest.
- Daily jobs use a catch-up window (scheduled time to scheduled time plus catch_up_hours),
  not a narrow fixed-minute window. Rationale: a five-minute window on a 60-second tick
  loop meant any restart or slow tick across that window silently skipped the job for
  the whole day.
- Scheduled jobs never send late. Past the catch-up cutoff, skip and log.
- State writes must be atomic: write to a temp file in logs/, flush, os.fsync, then
  os.replace. Rationale: a non-atomic write corrupted scheduler_state.json and disabled
  both scheduled jobs.
- No code path may save a stale state object over a newer write. Any job that saves state
  must reload it immediately before saving. Rationale: interval jobs held a state object
  loaded at the top of the tick and overwrote the digest's date write from the same tick.

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

---

## WHAT IS NOT BUILT YET (DO NOT STUB OR SUGGEST)

Unless explicitly scoped in a prompt, do not build or mention:
- Docker / containerization
- Redis session cache
- ChromaDB or vector knowledge base
- PostHog integration
- CloudCMA integration
- RealEstateAPI.com / BatchData
- Lob.com direct mail
- Calendly integration (native FUB sync status unconfirmed)
- Google Calendar integration (blocked: Side RE OAuth policy)
- Bluedot transcript processing
- EA email identity (Alex / Resend)
- Rental sequence content
- Communication memory write path (stub exists, read path only)
- Multi-agent Supervisor delegation

---

## DEPLOYMENT

The agent runs under supervisord on the Droplet.
Always use `supervisorctl restart cos-agent` for production restarts of the agent.
Never run `python -m core.main` directly on the Droplet in production.

cos-agent is the only supervisord entry point for the agent itself.
tools/watchdog.py runs as a subprocess spawned by core/main.py, not as its own
supervisord process.

Supervisord processes (verified /etc/supervisor/conf.d/):

| Process | Command |
|---|---|
| cos-agent | /root/COS_Deploy/venv/bin/python -m core.main |
| mcp-server | /root/COS_Deploy/venv/bin/python /root/COS_Deploy/mcp_server.py |
| webhook-server | /root/COS_Deploy/venv/bin/python /root/COS_Deploy/tools/webhook_server.py |
| cloudflared | /usr/local/bin/cloudflared tunnel --config /root/.cloudflared/config.yml run cos-mcp |

cos-agent conf: /etc/supervisor/conf.d/cos-agent.conf
directory: /root/COS_Deploy

Rollback tag: pre-refactor-june28 (commit 4f4d826)
Post-refactor tag: post-refactor-june28 (commit 0b09b4e)

To roll back to the pre-refactor architecture:
1. git checkout pre-refactor-june28 (commit 4f4d826)
2. Restore /etc/supervisor/conf.d/cos-agent.conf from that commit (command and
   directory are defined in the checked-out tree, not in _retired/)
3. supervisorctl reread && supervisorctl update && supervisorctl restart cos-agent

To return to post-refactor:
1. git checkout post-refactor-june28 (commit 0b09b4e) or main
2. Restore cos-agent.conf to: command /root/COS_Deploy/venv/bin/python -m core.main,
   directory /root/COS_Deploy
3. supervisorctl reread && supervisorctl update && supervisorctl restart cos-agent

---

## AGENT IDENTITY

The agent has no confirmed name. Do not assign one.
Do not reference "Scout" (retired placeholder).
Use "Chief of Staff" in user-facing strings.
Use "cos_agent" in code identifiers.
Ben Olsen decides the name. This is blocked on his input.

---

## Known Failure Pattern: ProxyError During Watchdog Restart Bursts

If FUB or OpenRouter calls fail with "ProxyError... Tunnel connection 
failed: 403" and no proxy is configured anywhere (checked: env vars, 
supervisor config, /etc/environment, codebase grep — confirmed clean 
July 3, 2026), check for a watchdog supervisor burst in cos_agent.log 
around the same timestamp (rapid start/failure/start cycles, <1s apart).

Root cause (fixed July 3, 2026): orphaned tools.watchdog subprocesses 
survived core.main restarts because SIGTERM doesn't propagate to 
reparented children. The orphan held watchdog.lock, causing new 
supervisor threads to spawn/fail/respawn in a tight loop. This loop 
correlated 100% with the two observed ProxyError incidents, though 
the exact mechanism (likely fd/socket exhaustion from rapid subprocess 
forking, misreported by urllib3 as a proxy error) was not directly 
confirmed.

Fix: _terminate_stale_watchdog_processes() in core/main.py now SIGTERMs 
any orphaned tools.watchdog process before each spawn attempt, and a 
2-second respawn delay was added. If ProxyError recurs, check first 
whether this fix regressed or whether a new orphan-causing path exists 
before assuming it's a real proxy/network issue.

## Known Failure Pattern: Unexplained morning_digest fire

On 2026-07-23 at 18:13:33 UTC (11:13 Pacific), core/scheduler.py::_tick
logged a morning_digest start and success 4ms apart with empty detail. No FUB
sub-logs, no Telegram send, no state write. The committed window gate at that
time required hour == 8 and could not have matched hour 11. The running process
had been up since 2026-07-22 15:58 UTC, so a file saved to disk 8 seconds before
the event could not have altered its in-memory code. Cause remains UNRESOLVED.
If a scheduled job fires outside its configured window again, treat this as a
recurrence and investigate the loaded code of the running process, not the code
on disk.

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
| FUB reads | tools/fub.py |
| FUB activity/context | tools/fub_activity.py |
| FUB writes | tools/fub_write.py |
| Webhook activity feed | tools/activity_feed.py |
| FUB webhook server | tools/webhook_server.py |
| Deadman's switch | tools/watchdog.py |
| Appointments | tools/appointments.py |
| Voice context | tools/voice.py |
| Logging | tools/logger.py |
| Health reporter | tools/health.py |
| Telegram send | tools/telegram.py |
| MCP API server | mcp_server.py |
| Ben's FUB topology | clients/ben-olsen/fub-config.yaml |
| Agent identity | clients/ben-olsen/soul.yaml |
| Scheduler timing | clients/ben-olsen/scheduler_config.json |
| Communication prefs | clients/ben-olsen/communication_prefs.json |
| Brief generation (CrewAI) | agents/crewai/crew.py |
