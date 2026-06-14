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

## Repo structure
COS_Deploy/
├── agents/crewai/          ← CrewAI orchestration (crew.py, bot.py, main.py, config/)
├── tools/                  ← Framework-agnostic API clients (fub.py, telegram.py, logger.py)
├── scripts/                ← One-off utility scripts (push_fub_templates.py)
├── clients/ben-olsen/      ← Tenant config and content for Ben Olsen
│   ├── soul.yaml           ← Agent identity and personality
│   ├── fub-config.yaml     ← FUB stage IDs and action plan IDs (all null currently)
│   ├── knowledge/          ← Domain knowledge markdown files (not yet loaded at runtime)
│   └── sequences/          ← Drip sequence copy and HTML templates
├── platform/               ← Shared specs and architecture docs (human reference only)
├── logs/                   ← Runtime log output (gitignored)
├── .env                    ← Live secrets (gitignored, never commit)
└── .env.example            ← Key names only, no values

---

## Current runtime state (as of June 2026)

What works:
- FUB read operations: get_contact_by_id, get_recent_activity, get_appointments
- Telegram send/receive: bot.py polls for messages, routes to run_brief()
- Pre-appointment brief generation: crew.py run_brief() via CrewAI
- Structured logging: tools/logger.py writes JSON to logs/cos_agent.log
- FUB template push: scripts/push_fub_templates.py (manual, one-way)

What is NOT built yet:
- FastAPI webhook gateway (no /telegram/webhook, /fub/webhook, /health routes)
- FUB write operations (no sequence enrollment, no note writes, no tag writes)
- Knowledge base loader (9 markdown files exist but are not injected into agents)
- Cron scheduler (no APScheduler, no jobs config)
- Morning digest
- Lead alert Telegram card (APPROVE/EDIT/CALL)
- Google Calendar integration (NotImplementedError stub)
- PostHog integration (keys empty, no client code)
- Calendly, Bluedot, CloudCMA, RealEstateAPI, BatchData, Lob.com
- Docker and VPS deployment
- Monitoring health reporter
- Engineer agent for self-repair

What is broken or incomplete:
- FUB action_plans in fub-config.yaml are all null (awaiting Theresa)
- posthog-event-schema.md is empty (0 bytes)
- knowledge/ files not loaded at runtime despite being listed in soul.yaml manifest
- Six platform/playbook files are empty placeholders
- Log file references a placeholder agent name that needs to be replaced

---

## How to run locally

```bash
# Start the Telegram polling loop
python agents/crewai/main.py --mode bot

# Generate a brief directly (no Telegram)
python agents/crewai/main.py --mode brief --contact 12345

# Push FUB email templates (dry run)
python scripts/push_fub_templates.py --dry-run

# Push FUB email templates (live)
python scripts/push_fub_templates.py --live
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
- clients/{name}/fub-config.yaml for FUB topology
- clients/{name}/soul.yaml for agent identity
- scheduler-config.json (not yet created) for cron timing

---

## FUB write rules

The agent is currently READ ONLY. No FUB writes are implemented.

When writes are added:
- Always filter to assignedTo: Ben Olsen (user ID 1)
- mergeTags: true for additive tag operations
- mergeTags: false for tag replacement (pass full corrected array)
- Never write to a contact without resolving identity first
- All client-facing sends require explicit realtor approval. No autonomous outbound.

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
Add OPENROUTER_API_KEY to .env and .env.example.
Do not use ANTHROPIC_API_KEY for inference. Keep it only if 
CrewAI requires a fallback — check requirements first.

---

## Monitoring (not yet built, building next)

Target architecture:
- Health reporter runs after every scheduled job and agent action
- Failures route to a separate operator Telegram channel (not Ben's bot)
- Ben's bot has one graceful degradation message per failure type
- Structured log is the source of truth for the Engineer agent (future)

Do not build monitoring into Ben's Telegram interface. 
Errors go to the operator channel, not to the realtor.

---

## Key files

| Need | Read |
|---|---|
| Agent orchestration | agents/crewai/crew.py |
| Telegram bot loop | agents/crewai/bot.py |
| FUB API client | tools/fub.py |
| Logging | tools/logger.py |
| Agent personas | agents/crewai/config/agents.yaml |
| Task definitions | agents/crewai/config/tasks.yaml |
| Ben's identity config | clients/ben-olsen/soul.yaml |
| FUB topology | clients/ben-olsen/fub-config.yaml |
| Full target architecture | platform/architecture/cos-handbook.md |
| Lead alert spec | platform/architecture/lead-alert-pattern.md |