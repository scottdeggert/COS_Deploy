# SYSTEM-MAP — Chief of Staff / COS_Deploy

Handoff document for AI assistants. Describes the **COS_Deploy** runtime repository as of June 2026. This is **not** the Ziggy/Hermes system; it is a related but separate CrewAI-only deployment for BrightWork Realty / Ben Olsen.

---

## Identity

| Field | Value |
|-------|-------|
| **What this agent is** | **Chief of Staff** — the BrightWork AI agent. CrewAI orchestration layer only. **No Hermes** runtime, no Hermes directory layout, no Hermes cron scheduler. |
| **Product name** | Chief of Staff (CoS) |
| **Agent display name** | Chief of Staff (from `clients/ben-olsen/soul.yaml`) |
| **Personality archetype** | The Penny (James Bond–style sharp equal) |
| **POC client** | Ben Olsen / BrightWork Realty Advocates |
| **Repository** | `/Users/scotteggert/Development/Cursor/COS_Deploy` (local dev); remote origin on GitHub |
| **Hardware / deployment host** | unknown — not yet deployed to production VPS per handbook plan |
| **Access method** | unknown — no Tailscale/SSH deployment config in repo |
| **Primary output channel (planned)** | Telegram (`TELEGRAM_CHAT_ID=8325146634` in `.env`) |
| **Primary output channel (current)** | CLI stdout only; Telegram tool exists but is not wired into the agent loop |
| **Knowledge base** | Markdown files under `clients/ben-olsen/knowledge/` (not Obsidian; content authored in sibling repo `COS_Project_Build`) |
| **LLM** | `anthropic/claude-sonnet-4-5` via CrewAI `LLM()` in `agents/crewai/crew.py` — direct Anthropic API, **not** OpenRouter |
| **Orchestration** | CrewAI (swappable per architectural guardrails) |
| **Active status** | **Not active** — no cron jobs, no FastAPI gateway, no webhooks, no production deployment |
| **Initial commit** | 2026-06-11 — single commit: "Initial commit: COS_Deploy runtime with Telegram messaging tool." |

---

## Directory Structure

Full annotated tree of the **COS_Deploy** project root. Excludes `.venv/`, `.git/`, and `__pycache__/`.

```
COS_Deploy/
├── .env                          # 362 B | 2026-06-11 16:19:30 | Runtime secrets (gitignored). Contains API keys — do not commit.
├── .env.example                  # 142 B | 2026-06-11 12:54:07 | Template listing env var names only
├── .gitignore                    # 35 B  | 2026-06-12 09:52:53 | Ignores .env, .venv, __pycache__, .DS_Store
├── README.md                     # 843 B | 2026-06-11 12:54:07 | Repo overview, structure, local run instructions
├── requirements.txt              # 141 B | 2026-06-11 14:31:12 | Python dependencies (crewai, anthropic, fastapi, etc.)
│
├── agents/
│   └── crewai/
│       ├── crew.py               # 4678 B | 2026-06-11 15:47:21 | Core CrewAI orchestration: loads client config, builds agents, runs pre-appointment brief task
│       ├── main.py               # 653 B  | 2026-06-11 12:54:04 | CLI entry point — **BROKEN**: imports nonexistent `BrightWorkCrew` class
│       └── config/
│           ├── agents.yaml       # 1306 B | 2026-06-11 14:14:31 | Agent role/goal/backstory definitions (supervisor, brief_generator)
│           └── tasks.yaml        # 953 B  | 2026-06-11 14:15:54 | Task definitions (generate_pre_appointment_brief)
│
├── tools/
│   ├── fub.py                    # 5931 B | 2026-06-11 14:07:02 | Follow Up Boss REST API client (framework-agnostic)
│   ├── telegram.py               # 2302 B | 2026-06-11 16:20:24 | Telegram Bot API send/receive helpers
│   └── calendar.py               # 664 B  | 2026-06-11 12:54:07 | Google Calendar client stub — NotImplementedError
│
├── scripts/
│   └── push_fub_templates.py     # 9505 B | 2026-06-12 08:26:32 | Parses sequence markdown, pushes plain-text email templates to FUB API
│
├── clients/
│   └── ben-olsen/
│       ├── soul.yaml             # 837 B  | 2026-06-11 14:27:36 | Agent identity, archetype, personality, knowledge manifest
│       ├── fub-config.yaml       # 763 B  | 2026-06-11 12:59:22 | FUB stage IDs and action plan placeholders (all action_plans null)
│       ├── knowledge/            # Client knowledge base (markdown)
│       │   ├── agent-knowledge-index.md          # 5958 B  | 2026-06-11 12:54:02 | Master index routing tasks to knowledge files
│       │   ├── brand-context.md                    # 27199 B | 2026-06-11 12:54:02 | BrightWork brand positioning, programs, personas
│       │   ├── contact-classification-taxonomy.md  # 11098 B | 2026-06-11 12:54:02 | FUB classification, stage defs, routing logic
│       │   ├── fair-housing-language.md            # 8661 B  | 2026-06-11 12:54:02 | Fair Housing / FEHA compliance rules
│       │   ├── fub-field-dictionary.md             # 6273 B  | 2026-06-11 12:54:02 | FUB field reference
│       │   ├── local-market-context.md             # 12906 B | 2026-06-11 12:54:02 | Lamorinda / local market geography
│       │   ├── posthog-event-schema.md             # 0 B     | 2026-06-11 12:54:02 | **EMPTY PLACEHOLDER** — no content
│       │   ├── source-of-truth-matrix.md           # 9211 B  | 2026-06-11 12:54:02 | Data source authority and write permissions
│       │   ├── tag-taxonomy.md                     # 14130 B | 2026-06-11 12:59:21 | FUB tag dictionary and interpretation rules
│       │   └── voice-guide.md                      # 23320 B | 2026-06-11 12:54:02 | Ben Olsen voice, tone, copy rules
│       └── sequences/            # Drip campaign content (markdown + HTML templates)
│           ├── agent-referral.md                   # 11277 B | 2026-06-11 12:54:02
│           ├── brightflip.md                       # 9160 B  | 2026-06-11 12:54:02
│           ├── buy-before-you-sell.md              # 9963 B  | 2026-06-11 12:54:02
│           ├── expired-packet.md                   # 10183 B | 2026-06-11 12:54:02
│           ├── final-offer.md                      # 8605 B  | 2026-06-11 12:54:02
│           ├── general-buyer.md                    # 8565 B  | 2026-06-11 12:54:02
│           ├── homelight.md                        # 6552 B  | 2026-06-11 12:54:02
│           ├── mcc-estimator.md                    # 5060 B  | 2026-06-11 12:54:02
│           ├── off-market-buyer.md                 # 9003 B  | 2026-06-11 12:54:02
│           ├── portal-buyer.md                     # 8736 B  | 2026-06-11 12:54:02
│           ├── portal-seller.md                    # 10745 B | 2026-06-11 12:54:02
│           ├── quiet-listing.md                    # 8975 B  | 2026-06-11 12:54:02
│           ├── relaunch.md                         # 10101 B | 2026-06-11 12:54:02
│           ├── senior-workshop.md                  # 6976 B  | 2026-06-11 12:54:02
│           ├── zillow-buyer.md                     # 8255 B  | 2026-06-11 12:54:02
│           ├── zillow-seller.md                    # 10053 B | 2026-06-11 12:54:02
│           └── templates/        # HTML program blocks for sequence emails
│               ├── brightflip-programs.html        # 14974 B | 2026-06-11 12:54:02
│               ├── buyer-programs-placeholder.md   # 284 B   | 2026-06-11 12:54:02 | Placeholder stub
│               ├── buyer-programs-v2.html          # 12831 B | 2026-06-11 12:54:02
│               ├── expired-packet-programs.html    # 15121 B | 2026-06-11 12:54:02
│               ├── final-offer-programs.html       # 14966 B | 2026-06-11 12:54:02
│               ├── homelight-programs.html         # 15007 B | 2026-06-11 12:54:02
│               ├── mcc-estimator-programs.html   # 14929 B | 2026-06-11 12:54:02
│               ├── quiet-listing-programs.html   # 15069 B | 2026-06-11 12:54:02
│               ├── relaunch-programs.html        # 15095 B | 2026-06-11 12:54:02
│               ├── seller-programs-v2.html       # 14889 B | 2026-06-11 12:54:02
│               └── senior-workshop-programs.html # 13867 B | 2026-06-11 12:54:02
│
└── platform/                     # Shared specs, architecture docs, integration guides
    ├── architecture/
    │   ├── cos-handbook.md           # 68638 B | 2026-06-11 12:54:02 | Full product/engineering handbook (v3.0) — target architecture
    │   ├── key-decisions.md          # 0 B     | 2026-06-11 12:54:02 | **EMPTY PLACEHOLDER**
    │   ├── lead-alert-pattern.md     # 3050 B  | 2026-06-11 12:54:02 | Lead Alert Telegram card spec (not implemented)
    │   └── soul-md-configurations.md # 3708 B  | 2026-06-11 12:54:02 | Personality archetype matrix for soul config
    ├── integrations/
    │   ├── cloudcma.md               # 6883 B  | 2026-06-11 12:54:02 | CloudCMA API integration spec
    │   ├── fub-api.md                # 7322 B  | 2026-06-11 12:54:02 | FUB REST API reference for agent
    │   └── fub-webhooks.md           # 18081 B | 2026-06-11 12:54:02 | FUB webhook event spec
    └── playbook/
        ├── content-generation-spec.md  # 0 B   | 2026-06-11 12:54:02 | **EMPTY PLACEHOLDER**
        ├── engagement-process.md       # 0 B   | 2026-06-11 12:54:02 | **EMPTY PLACEHOLDER**
        ├── fub-audit-checklist.md      # 0 B   | 2026-06-11 12:54:02 | **EMPTY PLACEHOLDER**
        ├── sequence-writing-spec.md    # 14551 B | 2026-06-11 12:54:02 | Rules for writing sequence content
        ├── soul-md-template.md         # 0 B   | 2026-06-11 12:54:02 | **EMPTY PLACEHOLDER**
        └── utm-spec.md                 # 2739 B  | 2026-06-11 12:54:02 | UTM parameter conventions
```

### Flags: Duplicates, Backups, Orphans

| File / Path | Flag | Notes |
|-------------|------|-------|
| `agents/crewai/main.py` vs `agents/crewai/crew.py` | **Orphan / drift** | `main.py` references `BrightWorkCrew` which does not exist in `crew.py`. Two competing entry points. |
| `clients/ben-olsen/soul.yaml` knowledge manifest | **Path mismatch** | References `knowledge-base/` and `fub/tag-taxonomy.md` and `utm-catalog.md` — actual paths are `knowledge/` and `platform/playbook/utm-spec.md`. Manifest not wired to loader anyway. |
| `clients/ben-olsen/knowledge/agent-knowledge-index.md` | **Path mismatch** | Internal paths say `realtors/ben-olsen/knowledge-base/` — legacy naming from source repo. |
| `clients/ben-olsen/sequences/templates/buyer-programs-placeholder.md` | **Placeholder** | Explicit placeholder, not production content. |
| Six zero-byte platform/knowledge files | **Empty placeholders** | Listed above — reserved for future content. |
| `requirements.txt` includes `fastapi`, `uvicorn`, `python-telegram-bot`, Google auth libs | **Unused deps** | No FastAPI app, no webhook server, no Google Calendar implementation in repo yet. |

### Directories That Do Not Exist (Ziggy-equivalent paths)

| Expected path (from Ziggy prompt) | Status in COS_Deploy |
|-----------------------------------|----------------------|
| `cron/` or `cron/jobs.json` | **Does not exist** — no cron infrastructure |
| `contexts/` | **Does not exist** |
| `skills/` | **Does not exist** |
| `config.yaml` | **Does not exist** — replaced by `soul.yaml` + `fub-config.yaml` |
| `SOUL.md` | **Does not exist** — replaced by `clients/ben-olsen/soul.yaml` |
| `services/` | **Does not exist** — handbook specifies this; integrations live in `tools/` instead |
| `app/config.py` | **Does not exist** — env vars read directly via `os.environ` in tools |

---

## Scripts

Only one script exists under `scripts/`. There is no `~/.hermes/scripts/` equivalent.

### `scripts/push_fub_templates.py`

| Field | Value |
|-------|-------|
| **Filename** | `push_fub_templates.py` |
| **What it does** | Reads 16 Ben Olsen sequence markdown files from `clients/ben-olsen/sequences/`, parses EMAIL step headings (Day N Email), extracts Subject and body text, skips Day 0 (Telegram approval steps) and HTML template steps, and either dry-prints or POSTs plain-text templates to FUB `/v1/templates`. Supports dual-path sequences (Seller path / Buyer path). |
| **Cron job** | not called by cron |
| **Schedule** | none — manual invocation only |
| **Dependencies** | `FUB_API_KEY` env var (required for `--live`); sequence markdown files in `clients/ben-olsen/sequences/`; stdlib only (no CrewAI) |
| **Known issues** | HTML email steps are skipped entirely — only plain-text bodies pushed. Action plan IDs in `fub-config.yaml` are all `null`, so templates cannot be linked to action plans yet. |
| **Last successful run** | unknown — not logged in repo |

---

## Tools

All tools live in `tools/`. No subdirectories.

### `tools/fub.py`

| Field | Value |
|-------|-------|
| **Path** | `tools/fub.py` |
| **What it does** | Framework-agnostic Follow Up Boss REST API client. Functions: `get_contact_by_id`, `get_recent_activity`, `search_contacts`, `get_contact_by_email`, `get_appointments`. Enforces contacts assigned to "Ben Olsen". Uses HTTP Basic auth with `FUB_API_KEY`. 10-second timeout on all requests. |
| **Status** | **active** (code complete for read operations) |
| **Depends on it** | `agents/crewai/crew.py` (wrapped as CrewAI tools); `scripts/push_fub_templates.py` (separate urllib implementation, does not import this module); smoke test via `__main__` block |

### `tools/telegram.py`

| Field | Value |
|-------|-------|
| **Path** | `tools/telegram.py` |
| **What it does** | Telegram Bot API client. Functions: `send_message`, `get_updates`, `extract_message`. Reads `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID` from environment. Markdown parse mode on send. |
| **Status** | **active** (send/receive code complete; not integrated into agent loop) |
| **Depends on it** | Nothing in the agent pipeline yet. Standalone smoke test sends "Chief of Staff is online. Pre-appointment brief system ready." |

### `tools/calendar.py`

| Field | Value |
|-------|-------|
| **Path** | `tools/calendar.py` |
| **What it does** | Stub `CalendarClient` class with `get_upcoming_appointments(days_ahead)` method. |
| **Status** | **pending** — raises `NotImplementedError` |
| **Depends on it** | Nothing yet. Handbook plans calendar-aware briefs. |

---

## Cron Jobs

**No cron infrastructure exists in this repository.**

| Item | Status |
|------|--------|
| `cron/jobs.json` | Does not exist |
| `scheduler-config.json` | Does not exist (referenced in handbook as future config) |
| APScheduler / Celery | Listed in `requirements.txt` indirectly (not present); no scheduler code |
| System crontab | unknown — not documented in repo |

The handbook (`platform/architecture/cos-handbook.md`) describes planned proactive monitors (morning digest, lead alerts, calendar polling) but none are implemented.

---

## Context Files

**No `contexts/` directory exists.**

Ziggy-style partitioned context files are not used. Context is instead distributed across:

| Location | Role | Loaded by | Last updated |
|----------|------|-----------|--------------|
| `clients/ben-olsen/soul.yaml` | Agent identity and personality injection | `crew.py` → `build_soul_context()` — injects name + personality_summary into agent backstories only | 2026-06-11 |
| `clients/ben-olsen/knowledge/*.md` | Domain knowledge (voice, compliance, routing, market) | **Not loaded at runtime** — documented in manifest but no loader implemented | 2026-06-11 |
| `agents/crewai/config/agents.yaml` | Agent role/goal/backstory templates | `crew.py` → `load_yaml_config()` | 2026-06-11 |
| `agents/crewai/config/tasks.yaml` | Task descriptions and expected outputs | `crew.py` → `load_yaml_config()` | 2026-06-11 |
| `platform/architecture/*.md` | Design specs (Lead Alert, soul archetypes) | Human/engineering reference only | 2026-06-11 |
| `platform/playbook/*.md` | Content and UTM standards | Human/content authoring reference only | 2026-06-11 |

---

## Skills

**No `skills/` directory exists.**

CrewAI agent capabilities are defined inline in:
- `agents/crewai/config/agents.yaml` (agent personas)
- `agents/crewai/config/tasks.yaml` (task specs)
- `agents/crewai/crew.py` (FUB tool wrappers)

There are no separate SKILL.md files or skill-loading infrastructure.

---

## Key Config Files

### `clients/ben-olsen/soul.yaml`

Agent identity configuration (YAML, not markdown SOUL.md):

```yaml
name: Chief of Staff
archetype: The Penny
proactivity: default
personality_summary: >
  Clever, poised, and equal — a sharp partner, not a subordinate.
  Lead with the decision or action item. Brief and direct by default.
  Flag urgent items clearly at the top. Wit is welcome; filler is not.
  Expand only for appointment prep, compliance flags, or first-time
  contact reviews where missing context would cause a bad decision.
knowledge_base_manifest:
  - knowledge-base/agent-knowledge-index.md
  - knowledge-base/voice-guide.md
  - ... (9 entries total)
  - utm-catalog.md
```

**Runtime usage:** Only `name` and `personality_summary` are consumed by `build_soul_context()`. The `knowledge_base_manifest` is **not loaded** by any code path.

### `clients/ben-olsen/fub-config.yaml`

FUB runtime topology:

- `fub_user_id: 1` (Ben Olsen)
- Stage name → numeric ID mappings (lead=2 through active_client=12)
- `action_plans:` — 16 sequence keys, **all values are `null`** (awaiting Theresa to create action plans in FUB UI)

### `.env` — keys present (values omitted)

| Key | In `.env.example` | Status / Notes |
|-----|-------------------|----------------|
| `FUB_API_KEY` | yes | Present, populated — required for FUB tools |
| `ANTHROPIC_API_KEY` | **no** | Present in `.env` but **missing from `.env.example`** — required for CrewAI LLM calls |
| `TELEGRAM_BOT_TOKEN` | yes | Present, populated |
| `TELEGRAM_CHAT_ID` | yes | Present, populated (`8325146634`) |
| `POSTHOG_API_KEY` | yes | Empty |
| `POSTHOG_PROJECT_ID` | yes | Empty |
| `GOOGLE_CALENDAR_CREDENTIALS_PATH` | yes | Empty |
| `CLIENT_ID` | yes | Set to `ben-olsen` |

**Suspicious entries:**
- `ANTHROPIC_API_KEY` is in `.env` but not documented in `.env.example` — documentation drift.
- No line 473 — file is only 8 lines. N/A for Ziggy's line-473 concern.
- `.env` contains live secrets in the working tree (gitignored but present locally).

### `config.yaml`

Does not exist.

### `SOUL.md`

Does not exist. Equivalent: `clients/ben-olsen/soul.yaml` (see above).

### `cron/jobs.json`

Does not exist. See Cron Jobs section.

---

## External Integrations

| Service | Purpose | Auth method | Key stored where | Status |
|---------|---------|-------------|------------------|--------|
| **Follow Up Boss** | CRM read (contacts, events, appointments); template push script | HTTP Basic (API key as username) | `FUB_API_KEY` in `.env` | **working** (read ops implemented; write limited to template push script) |
| **Anthropic (Claude)** | LLM reasoning via CrewAI | API key | `ANTHROPIC_API_KEY` in `.env` | **untested end-to-end** — key present; agent entry point broken |
| **Telegram Bot API** | Planned daily interface for Ben | Bot token | `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID` in `.env` | **partially working** — send_message smoke test exists; no webhook/polling loop |
| **PostHog** | Behavioral analytics for brief enrichment | API key + project ID | `POSTHOG_API_KEY`, `POSTHOG_PROJECT_ID` in `.env` | **broken/unconfigured** — keys empty; no client code; schema file empty |
| **Google Calendar** | Appointment awareness | OAuth credentials file | `GOOGLE_CALENDAR_CREDENTIALS_PATH` in `.env` | **not built** — stub only |
| **Calendly** | Scheduling webhooks | unknown | not in `.env` | **not built** — spec in handbook only |
| **Resend** | Outbound email delivery | unknown | not in `.env` | **not built** |
| **Bluedot** | Meeting transcript ingestion | Webhook secret | not in `.env` | **not built** — handbook spec only |
| **CloudCMA** | CMA report generation | unknown | not in `.env` | **not built** — integration doc only |
| **RealEstateAPI.com** | Property data | unknown | not in `.env` | **not built** |
| **BatchData** | Bulk enrichment | unknown | not in `.env` | **not built** |
| **Lob.com** | Direct mail | unknown | not in `.env` | **not built** (Phase 3) |

---

## Known Issues

| Issue | Status | Fix Applied | Notes |
|-------|--------|-------------|-------|
| `main.py` imports nonexistent `BrightWorkCrew` | **broken** | No | `ImportError` on `python agents/crewai/main.py`. Use `crew.py` directly or fix import. |
| Knowledge base manifest not loaded at runtime | **open** | No | `soul.yaml` lists 10 knowledge files; `crew.py` only injects name + personality. |
| Knowledge path naming mismatch | **open** | No | Manifest says `knowledge-base/`; repo uses `knowledge/`. Index file references `realtors/ben-olsen/`. |
| `posthog-event-schema.md` is empty | **open** | No | 0 bytes — agent cannot enrich briefs with web behavior. |
| All FUB action plan IDs are null | **open** | No | Sequence enrollment cannot be automated until Theresa creates action plans in FUB. |
| Google Calendar stub | **open** | No | `NotImplementedError` in `calendar.py`. |
| No FastAPI gateway / webhooks | **open** | No | Handbook architecture not implemented. `fastapi` in requirements but no app code. |
| No cron / scheduler | **open** | No | Proactive jobs (morning digest, lead monitor) not established. |
| Telegram not wired to agent | **open** | No | Tool exists; no webhook handler, no polling loop, no message routing. |
| Supervisor agent created but not used in task flow | **open** | No | `crew.py` creates supervisor + brief_generator but only assigns task to brief_generator; supervisor sits idle. |
| LLM model string vs handbook | **open** | No | Code uses `anthropic/claude-sonnet-4-5`; handbook specifies `claude-sonnet-4-6`. |
| Handbook says integrations in `services/` | **open** | No | Actual code uses `tools/` — architectural drift from handbook. |
| Handbook says env via `app/config.py` | **open** | No | Tools read `os.environ` directly. |
| Six empty platform playbook/architecture files | **open** | No | Placeholders with 0 bytes. |
| `.env` contains secrets locally | **risk** | N/A | Gitignored but present; ensure never committed. |
| `ANTHROPIC_API_KEY` missing from `.env.example` | **open** | No | Documentation incomplete. |
| Content Digest pipeline | **not built** | N/A | Ziggy feature — not present in COS_Deploy. |
| Otter / meeting ingestion pipeline | **not built** | N/A | Handbook specifies Bluedot instead; no code. |

---

## System Health Summary

COS_Deploy is an **early-stage POC skeleton**, not an active agent. What works today: the FUB read client (`tools/fub.py`), a standalone Telegram send helper (`tools/telegram.py`), a sequence-to-FUB-template push script (`scripts/push_fub_templates.py`), and a CrewAI brief-generation path in `crew.py` that can be invoked directly with `TEST_FUB_CONTACT_ID` set. What is fragile: the documented entry point (`main.py`) is broken due to a missing `BrightWorkCrew` class; the knowledge base (9 substantive markdown files, 16 sequences, 11 HTML templates) exists as content but is **not loaded into the agent at runtime**; FUB action plan IDs are all unset; and PostHog/Calendar integrations are stubs or empty. What is broken: end-to-end agent execution via `main.py`, any proactive scheduling, webhook-driven lead alerts, and Telegram as a daily interface. What has never been tested end-to-end: pre-appointment brief generation → Telegram delivery, lead alert flow, sequence enrollment, morning digest, Bluedot transcript ingestion, or any production VPS deployment. The comprehensive handbook in `platform/architecture/cos-handbook.md` describes the **target** architecture; the **implemented** codebase covers roughly Phase 0 — tools, one CrewAI task, and content assets.
