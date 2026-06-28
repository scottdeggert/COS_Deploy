# CLAUDE.md
# Context file for AI-assisted development in COS_Deploy.
# Read this entire file before touching anything.

## What this repo is

COS_Deploy is the runtime deployment for the BrightWork Chief of Staff 
AI agent, built by MKTNG.co (Scott Eggert) for real estate professionals.
It runs on top of Follow Up Boss CRM and delivers an AI operations layer 
via Telegram. First deployment: Ben Olsen, BrightWork Realty Advocates,
Moraga CA.

This is the repo that ships. It is NOT the content authoring repo.
Content (sequences, knowledge base, platform specs) is authored in the 
sibling repo COS_Project_Build and synced here manually when finalized.

Do not author or edit sequence copy, HTML templates, or platform 
architecture docs in this repo. Make those changes in COS_Project_Build.

---

## TWO-REPO ARCHITECTURE — READ THIS FIRST

There are three instances of this codebase. Know which one you are in
before making any change.

| Instance | Path | Purpose |
|---|---|---|
| COS_Project_Build (Mini) | `/Users/scotteggert/Development/Cursor/COS_Project_Build/` | Content authoring source of truth. Sequences, knowledge base, FUB config. Never runs in production. |
| COS_Deploy (Mini) | `/Users/scotteggert/Development/Cursor/COS_Deploy/` | Staging and local runtime. This repo. |
| COS_Deploy (Droplet) | `/root/COS_Deploy/` | Live production. |

**Directory structure differs between BUILD and DEPLOY:**
- BUILD sequences path: `cos-agent/realtors/ben-olsen/sequences/`
- DEPLOY sequences path: `clients/ben-olsen/sequences/`

**Sync convention:** Content authored in COS_Project_Build is manually
copied to COS_Deploy when finalized. After editing sequence files or
knowledge base files, changes must be:
1. Committed in COS_Deploy on the Mini
2. Pushed to GitHub (`scottdeggert/COS_Deploy`)
3. Pulled on the Droplet and services restarted

If you are asked to edit a sequence file or knowledge base file and
you are in COS_Deploy, confirm with Scott whether the change should
originate in COS_Project_Build instead.

**Never assume the Droplet is current.** It may be behind the Mini by
one or more sprint's worth of changes.

---

## Repo structure
COS_Deploy/

├── agents/crewai/          ← CrewAI orchestration (crew.py, bot.py, main.py, config/)

├── tools/                  ← Framework-agnostic API clients

│   ├── fub.py              ← FUB REST API client (read + Action Plan enrollment)

│   ├── telegram.py         ← Telegram Bot API (send_message, send_operator_alert)

│   ├── logger.py           ← Structured JSON logging

│   ├── health.py           ← Health reporter, operator channel alerts

│   └── calendar_stub.py    ← Google Calendar stub — NotImplementedError

│                             CRITICAL: Do not rename this file. It was previously

│                             calendar.py, which shadowed Python's stdlib calendar

│                             module and crashed requests on import.

├── scripts/                ← One-off utility scripts (push_fub_templates.py)

├── clients/ben-olsen/      ← Tenant config and content for Ben Olsen

│   ├── soul.yaml           ← Agent identity and personality

│   ├── fub-config.yaml     ← FUB stage IDs (all 21 confirmed) and action plan IDs

│   ├── knowledge/          ← Domain knowledge markdown files (not yet loaded at runtime)

│   └── sequences/          ← Drip sequence copy and HTML templates

├── platform/               ← Shared specs and architecture docs (human reference only)

├── logs/                   ← Runtime log output (gitignored)

├── .env                    ← Live secrets (gitignored, never commit)

└── .env.example            ← Key names only, no values

---

## Current runtime state (as of June 2026)

**What works:**
- FUB read operations: get_contact_by_id, get_recent_activity, get_appointments
- FUB Action Plan enrollment: APPROVE button triggers POST /v1/actionPlansPeople
- Telegram send/receive: bot.py polls for messages, routes intents
- Lead alert cards: new FUB contacts trigger Telegram card with APPROVE/EDIT/CALL buttons
- Operator alert channel: errors and health events route to separate operator chat
- Health reporter: tools/health.py fires after agent actions
- Structured logging: tools/logger.py writes JSON to logs/cos_agent.log
- Pre-appointment brief generation: crew.py run_brief() via CrewAI
- FUB template push: scripts/push_fub_templates.py (manual, one-way, upsert logic)

**What is NOT built yet:**
- FastAPI webhook gateway (no /telegram/webhook, /fub/webhook, /health routes)
- FUB write operations beyond Action Plan enrollment (no note writes, no tag writes)
- Knowledge base loader (9 markdown files exist but are not injected into agents)
- Cron scheduler (no APScheduler, no jobs config)
- Morning digest
- Google Calendar integration (NotImplementedError stub in calendar_stub.py)
- PostHog integration (keys empty, no client code)
- MCC event parsing and flag-to-tag mapping in fub.py (spec complete, prompt pending)
- Calendly, Bluedot, CloudCMA, RealEstateAPI, BatchData, Lob.com
- Docker and VPS deployment
- Engineer agent for self-repair
- Knowledge base runtime loader

**What is broken or incomplete:**
- FUB action_plan IDs in fub-config.yaml are null — Theresa has built all 16 Action
  Plans in FUB UI but IDs have not yet been populated in the yaml
- knowledge/ files not loaded at runtime despite being listed in soul.yaml manifest
- posthog-event-schema.md is empty (0 bytes) — agent cannot enrich briefs with web behavior
- Six platform/playbook files are empty placeholders
- TELEGRAM_CHAT_ID is currently Scott's test account — pending swap to Ben's account

---

## How to run locally

```bash
# Start the Telegram polling loop
python agents/crewai/main.py --mode bot

# Generate a brief directly (no Telegram)
python agents/crewai/main.py --mode brief --contact 12345

# Push FUB email templates (dry run)
python scripts/push_fub_templates.py

# Push FUB email templates (live)
FUB_API_KEY=$(grep FUB_API_KEY .env | cut -d= -f2) python scripts/push_fub_templates.py --live
```

All commands require a populated .env file. Copy .env.example and fill values.

---

## Agent identity

The agent has no confirmed product name yet. Do not introduce or 
proliferate any name. In code, use neutral identifiers: "cos_agent", 
"chief_of_staff", or "agent". In soul.yaml, the name field is a 
placeholder pending Ben Olsen's input. In Telegram messages to Ben, 
the agent refers to itself as "Chief of Staff" until a name is chosen.

If you encounter the name "Scout" anywhere in this codebase, that is 
a stale placeholder. Replace it with "Chief of Staff" in user-facing 
strings and "cos_agent" in code identifiers.

---

## Tenant structure

clients/ben-olsen/ is the only active tenant. When onboarding a new 
realtor, copy this directory, rename it to clients/{realtor-name}/, 
and replace all content. Do not modify platform/ or agents/ to 
accommodate a single tenant.

---

## Zero-hardcoding policy

No API keys, user IDs, stage IDs, sequence IDs, phone numbers, or 
schedule values in source code. They belong in:
- .env for secrets and credentials
- clients/{name}/fub-config.yaml for FUB topology and stage IDs
- clients/{name}/soul.yaml for agent identity
- scheduler-config.json (not yet created) for cron timing

---

## FUB write rules

The agent currently supports ONE write operation: Action Plan enrollment
via POST /v1/actionPlansPeople. All other FUB operations are read-only.

When additional writes are added:
- Always filter to assignedTo: Ben Olsen (user ID 1)
- mergeTags: true for additive tag operations
- mergeTags: false for tag replacement (pass full corrected array)
- Never write to a contact without resolving identity first
- All client-facing sends require explicit realtor approval. No autonomous outbound.
- Always log previous stage value before writing a new stage

**FUB platform constraints (confirmed, permanent):**
- /v1/emails endpoint is unavailable to integrations — all email routes through Action Plans
- isHtml in template payload causes HTTP 400 — omit entirely, FUB auto-detects HTML
- FUB has no Day 0 — sequences start at Day 1
- Merge tag format: %contact_first_name% (not [first name] or {{person.firstName}})
- Action Plan creation is UI-only — no REST endpoint

---

## FUB source field

The FUB contact `source` field is stale creation-time data. Do not use
it directly for routing decisions. Use `_get_source_from_events()` to
parse the most recent event message for "via: [url]" format instead.

---

## Logging

Every agent action must be logged via tools/logger.py log_event().
Fields: timestamp, agent, action, status, detail, contact_id.
Status values: start, success, failure, fallback.
Log file: logs/cos_agent.log

Do not log to stdout in production code. Use logger.py.
Never include PII (contact email, phone, full name) in log detail fields.
Contact ID only.

---

## LLM

All LLM calls route through OpenRouter, not Anthropic direct.
Base URL: https://openrouter.ai/api/v1
Auth: OPENROUTER_API_KEY in .env

Model assignment by task complexity:
- Brief generation, voice drafts, anything Ben reads:
    anthropic/claude-sonnet-4-6
- Routing, classification, intent parsing, health summaries:
    anthropic/claude-haiku-4-5
- Default fallback if unspecified: anthropic/claude-haiku-4-5

Model strings live in agents/crewai/config/agents.yaml per agent role.
Never hardcode a model string in crew.py or bot.py.

---

## Monitoring

- Health reporter (tools/health.py) fires after every agent action
- Failures route to operator Telegram channel (TELEGRAM_MONITOR_CHAT_ID in .env)
- Ben's bot has one graceful degradation message per failure type
- Ben never sees technical errors — operator channel only

TELEGRAM_MONITOR_CHAT_ID is not yet set in .env. Until it is, operator
alerts fall back to the primary chat ID. Set it before go-live.

---

## Key files

| Need | Read |
|---|---|
| Agent orchestration | agents/crewai/crew.py |
| Telegram bot loop | agents/crewai/bot.py |
| FUB API client | tools/fub.py |
| Logging | tools/logger.py |
| Health reporter | tools/health.py |
| Agent personas | agents/crewai/config/agents.yaml |
| Task definitions | agents/crewai/config/tasks.yaml |
| Ben's identity config | clients/ben-olsen/soul.yaml |
| FUB stage IDs and action plans | clients/ben-olsen/fub-config.yaml |
| Lead alert spec | platform/architecture/lead-alert-pattern.md |
