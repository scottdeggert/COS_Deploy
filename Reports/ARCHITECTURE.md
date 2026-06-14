# ARCHITECTURE — Chief of Staff / COS_Deploy

Higher-level design document for the BrightWork Chief of Staff AI agent. Explains **design intent** and **what is actually built** in the COS_Deploy repository as of June 2026.

This system is **CrewAI-only**. It does **not** use Hermes. It shares conceptual DNA with the Ziggy agent build (CrewAI orchestration, Telegram as planned interface, similar chat ID) but is a separate product for a real estate broker POC.

---

## What the Chief of Staff Is

The Chief of Staff is Ben Olsen's AI operations layer designed to sit on top of Follow Up Boss (FUB) and augment a solo residential broker's workflow without replacing his CRM, calendar, or judgment. The product vision (documented in `platform/architecture/cos-handbook.md`) positions the Chief of Staff as replacing fragmented manual work: offshore ISA follow-up, direct mail coordination, scheduling support, property report prep, and disconnected analytics. Ben's sole daily touchpoint is intended to be **Telegram**, where the Chief of Staff delivers concise summaries, approval cards, alerts, and morning digests.

The **CrewAI architecture** supports this by keeping business logic framework-agnostic while using CrewAI only for agent instantiation, task delegation, and LLM orchestration. Integrations live in `tools/` as plain Python functions. CrewAI wraps those functions as agent tools. Client identity comes from `soul.yaml`; FUB topology from `fub-config.yaml`; agent personas from YAML config files. This separation means CrewAI can be swapped later without rewriting FUB, Telegram, or calendar logic. Today, only one task is implemented (`generate_pre_appointment_brief`), with two agents defined (supervisor and brief_generator) but only the brief_generator actively executing work.

---

## How the Content Digest Works

**Status: NOT BUILT in COS_Deploy.**

The Content Digest pipeline described in the Ziggy prompt (cron trigger → Google Drive output → Telegram delivery) does not exist in this repository. There is no content digest script, no Google Drive integration, no digest cron job, and no reference to content digestion in the codebase or handbook.

**Planned analog (from handbook):** The closest planned capability is the **morning digest** — a proactive Telegram summary of overnight leads, deferred approvals, calendar items, and pipeline status. The handbook specifies this would be driven by APScheduler/Celery on a VPS, triggered by cron config in a future `scheduler-config.json`, and delivered via the Telegram bot. None of this infrastructure exists yet.

If implemented per handbook, the flow would likely be:

```
[Scheduler cron] → [Python digest script or agent task]
    → Read FUB (new contacts, stage changes, unanswered lead alerts)
    → Read Google Calendar (today's appointments)
    → Read PostHog (overnight form submissions) — requires PostHog client
    → Compile summary via Claude
    → tools/telegram.send_message() → Ben's Telegram chat
```

**Files that would be involved (none exist today):** scheduler config, digest script or CrewAI task, `tools/fub.py`, `tools/calendar.py`, PostHog client, `tools/telegram.py`.

---

## How the Otter Pipeline Works

**Status: NOT BUILT. Otter is not used.**

This project does not reference Otter.ai. The handbook specifies **Bluedot** (not Otter) for meeting transcript ingestion.

**Planned Bluedot flow (from handbook, not implemented):**

```
[Bluedot completes recording]
    → POST /bluedot/webhook (FastAPI gateway — not built)
    → Verify shared secret header
    → Look up FUB contact by meeting participant
    → Check bluedot_consent tag on contact
        → If no consent: log suppression, return 200, stop
        → If consent: extract transcript summary + action items
    → Write notes to FUB contact
    → Optionally notify Ben via Telegram
    → Feed into pre-appointment brief context
```

**Files that would be involved (none exist today):** FastAPI app, Bluedot webhook handler, FUB write functions, consent tag check against `clients/ben-olsen/knowledge/tag-taxonomy.md`.

There is no Bluedot webhook handler, no transcript parser, and no `BLUEDOT_WEBHOOK_SECRET` in `.env`.

---

## How the Sales Pipeline Loop Works

**Status: PARTIALLY SPECIFIED — not implemented as runtime code.**

The sales pipeline exists today as **content assets and design specs**, not as executable automation.

### What exists (content layer)

1. **16 sequence markdown files** in `clients/ben-olsen/sequences/` — full drip campaign copy for programs (Zillow seller/buyer, HomeLight, expired packet, senior workshop, etc.). Each defines Day 0 (Telegram approval), plain-text emails, and HTML template references.

2. **11 HTML program templates** in `clients/ben-olsen/sequences/templates/` — rendered program blocks inserted into HTML emails.

3. **`scripts/push_fub_templates.py`** — one-way push of plain-text email bodies to FUB `/v1/templates`. Does not enroll contacts, trigger sequences, or interact with Telegram.

4. **`clients/ben-olsen/fub-config.yaml`** — stage ID mappings and action plan key placeholders (all `null`).

5. **`platform/architecture/lead-alert-pattern.md`** — detailed spec for the Lead Alert Telegram card (new lead → draft SMS → APPROVE/EDIT/CALL buttons).

### Planned end-to-end sales loop (from handbook + lead-alert spec)

```
[FUB webhook: new_contact] → FastAPI /fub/webhook (NOT BUILT)
    → Supervisor agent classifies lead (intent signals vs long-nurture)
    → If alert-eligible:
        → Read contact from FUB (tools/fub.py)
        → Load voice-guide.md + brand-context.md (NOT WIRED)
        → Draft first-touch SMS in Ben's voice
        → Send Telegram card with inline keyboard (NOT BUILT)
        → Ben taps APPROVE / EDIT / CALL
        → Write note to FUB, log action
        → If no response in 30 min: log fallback flag, enroll in sequence
    → If sequence-only:
        → Match lead source to sequence via contact-classification-taxonomy.md
        → Enroll in FUB action plan (requires action plan IDs — all null)
        → Day 0: Telegram approval for first email (manual)
        → Day N+: FUB auto-sends from templates pushed by push_fub_templates.py
```

### Current gap

The loop stops after content authoring. There is no webhook intake, no lead classification code, no Telegram approval UI, no sequence enrollment API calls, and no action plan IDs configured. The pipeline is **designed but not wired**.

---

## Context Partitioning

Ziggy uses four separate context files for operating domains. **COS_Deploy does not use that pattern.** Instead, context is partitioned across several layers with different runtime status:

| Partition | Location | Purpose | Runtime status |
|-----------|----------|---------|----------------|
| **Identity / personality** | `clients/ben-olsen/soul.yaml` | Agent name (Chief of Staff), archetype (The Penny), tone rules | **Loaded** — `name` + `personality_summary` injected into CrewAI agent backstories |
| **Agent behavior templates** | `agents/crewai/config/agents.yaml` | Role, goal, backstory for supervisor and brief_generator | **Loaded** at crew assembly |
| **Task specifications** | `agents/crewai/config/tasks.yaml` | What the brief task must produce | **Loaded** at crew assembly |
| **Domain knowledge** | `clients/ben-olsen/knowledge/*.md` (9 files) | Voice, brand, compliance, market, FUB fields, tags, routing, data authority | **Not loaded** — manifest in soul.yaml is declarative only |
| **Campaign content** | `clients/ben-olsen/sequences/*.md` (16 files) | Sequence copy for each program | **Not loaded** by agent — used by push script and future enrollment |
| **FUB topology** | `clients/ben-olsen/fub-config.yaml` | Stage IDs, action plan IDs | **Partially loaded** — merged into client config dict but not consumed by brief task logic |
| **Platform standards** | `platform/playbook/`, `platform/architecture/` | UTM rules, sequence writing spec, lead alert pattern, integration docs | **Human reference only** |

### Why they are kept separate (design intent)

- **soul.yaml** holds invariant identity — who the Chief of Staff is and how he talks to Ben internally. It should not change per task.
- **knowledge/** holds domain expertise — loaded on demand per task type (per `agent-knowledge-index.md` routing rules). Keeps prompts lean.
- **sequences/** holds outbound client-facing copy — loaded only when drafting or reviewing sequence emails, never for internal Telegram chat.
- **fub-config.yaml** holds account-specific IDs that change when FUB is reconfigured — separated from personality.
- **platform/** holds cross-client standards — shared across future realtor deployments.

### What scripts load which contexts

| Code path | Contexts loaded |
|-----------|-----------------|
| `crew.py` → `run_brief()` | `soul.yaml`, `fub-config.yaml`, `agents.yaml`, `tasks.yaml` |
| `crew.py` → `build_soul_context()` | `name`, `personality_summary` from soul only |
| `main.py` | Would load via `BrightWorkCrew` — **broken, class missing** |
| `push_fub_templates.py` | Sequence markdown files only — no agent context |
| `tools/fub.py` | None — pure API client |
| `tools/telegram.py` | None — pure API client |

---

## Agent vs Script Jobs

**No cron jobs exist in COS_Deploy.** This section describes the **intended pattern** from the handbook and Ziggy-style systems, mapped to what exists here.

### Intended distinction

| Mode | Description | When to use |
|------|-------------|-------------|
| **Script-based (`no_agent`)** | Deterministic Python script. No LLM. Fixed input → fixed output. | Template pushes, health checks, data syncs, scheduled API polls |
| **Agent-prompt-based** | CrewAI task with LLM reasoning. Dynamic context gathering via tools. | Brief generation, lead alert draft copy, digest summarization, preference parsing |

### What exists today (manual invocation only)

| Job (conceptual) | Mode | Script / entry point | Schedule |
|------------------|------|---------------------|----------|
| Push FUB email templates | Script | `scripts/push_fub_templates.py` | Manual |
| Pre-appointment brief | Agent | `agents/crewai/crew.py` (direct) | Manual via env vars |
| Telegram smoke test | Script | `tools/telegram.py` (`__main__`) | Manual |
| FUB smoke test | Script | `tools/fub.py` (`__main__`) | Manual |
| Run agent (broken) | Agent | `agents/crewai/main.py` | Manual — fails on import |

### Planned jobs (from handbook — none scheduled)

| Job | Mode | Purpose |
|-----|------|---------|
| Morning digest | Agent | Overnight summary to Telegram |
| Lead monitor | Agent | FUB webhook-driven lead alerts |
| Calendar poll | Script | Upcoming appointments → brief triggers |
| Sequence delay checker | Script | Enroll contacts flagged for fallback sequences |
| Bluedot transcript processor | Script + Agent | Ingest meetings, extract action items |

When cron is established, the handbook recommends config in `clients/{name}/scheduler-config.json` (not yet created) rather than a Hermes-style `jobs.json`.

---

## What Is Not Yet Built

Honest gap assessment — features referenced in config, docs, or handbook that do not exist as working code:

### Infrastructure

- FastAPI gateway with webhook routes (`/telegram/webhook`, `/fub/webhook`, `/calendly/webhook`, `/bluedot/webhook`, `/health`)
- Docker Compose deployment
- VPS production hosting
- APScheduler or Celery task queue
- Cron / scheduler config
- Redis session cache
- SQLite preference store and trajectory ledger
- Centralized `app/config.py` for env var access

### Agent capabilities

- Lead Alert Telegram card with inline keyboard (APPROVE/EDIT/CALL)
- Morning digest
- Sequence enrollment automation
- Draft communications agent
- Calendar monitor agent
- Property/CMA agent
- Preference compiler (teachability from Telegram instructions)
- Knowledge base loader (vector index or file injection per task)
- Working `main.py` entry point with `BrightWorkCrew` class
- Supervisor delegation (supervisor agent is instantiated but unused in task assignment)

### Integrations (no client code)

- PostHog (keys empty, schema file empty)
- Google Calendar (`NotImplementedError`)
- Calendly
- Resend (email delivery)
- Bluedot (transcripts)
- CloudCMA (CMA reports)
- RealEstateAPI.com / BatchData (property data)
- Lob.com (direct mail)

### Configuration gaps

- All 16 FUB `action_plans` IDs are `null`
- `posthog-event-schema.md` is empty (0 bytes)
- Six platform playbook files are empty placeholders
- `utm-catalog.md` referenced in soul.yaml does not exist (UTM spec is at `platform/playbook/utm-spec.md`)
- Knowledge manifest paths use legacy `knowledge-base/` naming

### Ziggy-specific features not applicable here

- Hermes runtime and directory layout
- Content Digest → Google Drive pipeline
- Otter meeting ingestion
- Obsidian knowledge base sync
- OpenRouter LLM routing (this project uses Anthropic direct)

---

## Evolution Notes

### Repository history

- **2026-06-11:** Initial commit — "COS_Deploy runtime with Telegram messaging tool." Single commit on `main`.
- Content files (sequences, knowledge, platform docs) appear to have been bulk-imported from the sibling authoring repo `COS_Project_Build` on the same date.

### Architectural pivots and naming drift

| Topic | Handbook / source spec | Current implementation |
|-------|------------------------|------------------------|
| Integration layer directory | `services/` | `tools/` |
| Config loader | `app/config.py` | Direct `os.environ` in each tool |
| Client config path | `realtors/{client-name}/` | `clients/{client-name}/` |
| Soul file format | `soul.md` (markdown) | `soul.yaml` (YAML) |
| FUB config format | `fub-config.json` | `fub-config.yaml` |
| Knowledge directory | `knowledge-base/` | `knowledge/` |
| LLM model | `claude-sonnet-4-6` | `anthropic/claude-sonnet-4-5` in crew.py |
| Agent entry point | Class-based crew | Functional `run_brief()` in crew.py; broken class reference in main.py |

### Deprecated / superseded patterns

- **`main.py` → `BrightWorkCrew`:** Appears to be an earlier class-based design abandoned in favor of functional `run_brief()` in `crew.py`. `main.py` was not updated — creates a broken entry point.
- **Version 2.x soul.md teachability:** Handbook v3.0 moved dynamic preferences to a database store; `soul.yaml` is invariant. No preference store exists yet.
- **Class-based agent overrides:** Handbook guardrail says avoid them; crew.py uses functional agent factory `_make_agent()`.

### Recent additions (post-initial commit, same day)

- `crew.py` expanded with FUB tool wrappers and `run_brief()` (2026-06-11 15:47)
- `push_fub_templates.py` added (2026-06-12 08:26)
- `telegram.py` updated with smoke test message referencing "Chief of Staff" (2026-06-11 16:20)
- `.gitignore` added (2026-06-12 09:52)

### Relationship to Ziggy

Both systems share:

- CrewAI as orchestration
- Telegram as planned primary interface
- Same `TELEGRAM_CHAT_ID` (8325146634) in local `.env`
- Concept of soul/personality config and cron-driven proactive jobs

COS_Deploy differs:

- No Hermes agent host
- Real estate / FUB domain (not personal AI / Obsidian)
- Client-specific content repo structure
- Anthropic direct (not OpenRouter)
- Agent named Chief of Staff, not Ziggy
