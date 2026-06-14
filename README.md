# COS_Deploy

Runtime deployment for the BrightWork Chief of Staff AI agent.
Built by MKTNG.co (Scott Eggert) for real estate professionals.
First deployment: Ben Olsen, BrightWork Realty Advocates, Moraga CA.

This repo runs the agent. Content is authored in the sibling repo
COS_Project_Build and synced here manually when finalized.

---

## What exists today

| Component | Status |
|---|---|
| FUB read operations | Working |
| Telegram polling loop | Built, untested end-to-end |
| Pre-appointment brief via CrewAI | Built, untested end-to-end |
| Structured JSON logging | Built |
| Operator alert channel | Built |
| Startup health check | Built |
| OpenRouter model routing | Built |
| FUB write operations | Not built |
| Webhook gateway (FastAPI) | Not built |
| Knowledge base loader | Not built |
| Cron scheduler | Not built |
| Morning digest | Not built |
| Lead alert Telegram card | Not built |
| Google Calendar | Stub only |
| PostHog | Not built |
| Docker / VPS deployment | Not built |

---

## How to run locally

Requires a populated .env file. Copy .env.example and fill all values.

```bash
# Start Telegram polling loop
python agents/crewai/main.py --mode bot

# Generate a brief directly (no Telegram)
python agents/crewai/main.py --mode brief --contact [FUB_CONTACT_ID]

# Push email templates to FUB (dry run)
python scripts/push_fub_templates.py --dry-run

# Push email templates to FUB (live)
python scripts/push_fub_templates.py --live
```

---

## Environment variables

See .env.example for the full list. Required to start:

- OPENROUTER_API_KEY
- FUB_API_KEY
- TELEGRAM_BOT_TOKEN
- TELEGRAM_CHAT_ID
- OPERATOR_TELEGRAM_CHAT_ID

Optional:
- HEALTH_CHECK_CONTACT_ID (a real FUB contact ID for startup verification)

---

## Architecture

See CLAUDE.md for current runtime state and development rules.
See platform/architecture/cos-handbook.md for the full target architecture.

---

## Tenant structure

clients/ben-olsen/ is the only active tenant. To onboard a new realtor,
copy this directory, rename it, and replace the contents.
Do not modify platform/ or agents/ for a single tenant.

---

## Monitoring

Agent errors route to a separate operator Telegram channel.
Ben Olsen's bot interface never surfaces technical errors.
All agent actions write to logs/cos_agent.log in structured JSON.
The operator channel is configured via OPERATOR_TELEGRAM_CHAT_ID in .env.

---

## Agent name

No product name is confirmed. Do not introduce one.
User-facing strings use "Chief of Staff."
Code identifiers use "cos_agent."
If you encounter "Scout" in this codebase, replace it.

---

## Last updated

June 2026 — foundational ops layer complete.
Next: FastAPI webhook gateway, FUB webhook intake, lead alert Telegram card.
