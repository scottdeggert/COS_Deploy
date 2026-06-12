# Chief of Staff AI Agent

## Complete Product, System, and Engineering Handbook

**Version:** 3.0 — June 2026  
**POC Deployment:** BrightWork Realty, Ben Olsen  
**Source Basis:** Internal Version 2.0 handbook, Version 2.1 memory-architecture revision, Gemini casualty analysis, and latest product prompt updates.

## 1. Project Overview and High-Level Architecture

### 1.1 Executive Summary

**Chief of Staff** is an autonomous AI agent layer that runs on a real estate broker’s existing **Follow Up Boss** CRM. It replaces the combined operational function of an offshore ISA, a manual direct-mail operation, fragmented scheduling support, property report preparation, and a disconnected analytics stack, without requiring the broker to abandon their primary CRM, calendar, or communication workflows. The first deployment target is a solo residential real estate broker generating roughly 50–200 leads per month and managing most CRM operations manually or inconsistently.

The core user experience is intentionally narrow. The realtor’s sole daily interaction surface is **Telegram**, where the agent sends concise operational summaries, approval requests, alerts, and morning digests. Behind Telegram, the system connects to FUB, Calendly, Google Calendar, PostHog, Resend, Bluedot, CloudCMA, RealEstateAPI.com, BatchData, and eventually Lob.com. The agent is designed as an augmentative operations layer rather than a replacement for broker judgment.

### 1.2 System Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              REALTOR INTERFACE                              │
│                        Telegram (sole daily surface)                        │
└──────────────────────────────────────┬──────────────────────────────────────┘
                                       │ webhook (POST /telegram/webhook)
                                       ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                               FASTAPI GATEWAY                               │
│                   Self-hosted VPS, optionally Cloudflare-fronted            │
│ Routes: /telegram/webhook /fub/webhook /calendly/webhook /bluedot/webhook   │
│         /posthog/webhook /cloudcma/webhook /lob/webhook /health             │
└──────────────────────────────────────┬──────────────────────────────────────┘
                                       │
                                       ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                          SUPERVISOR AGENT (CrewAI)                          │
│ Loads: invariant soul.md personality config and compiled preferences         │
│ Maintains: stateful execution tree and short-term contextual memory          │
│ Delegates to specialist agents and framework-agnostic Python tools           │
└──┬─────────┬───────────┬──────────────┬──────────────┬──────────────┬───────┘
   │         │           │              │              │              │
   ▼         ▼           ▼              ▼              ▼              ▼
Lead      Scheduling  Calendar       Brief &        Property &      Draft &
Intake    Coord.      Monitor        Report Gen.    CMA Agent       Comms
Agent     Agent       Agent          Agent                           Agent
   │         │           │              │              │              │
   └─────────┴───────────┴──────────────┴──────┬───────┴──────────────┘
                                               │
                                               ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                 COGNITIVE MEMORY ENGINE & EXECUTION TRACE                   │
├───────────────────────┬──────────────────────────────┬──────────────────────┤
│  Redis Session Cache  │  Dynamic Preference Compiler │  Trajectory Ledger   │
│  Ephemeral Context    │  Categorized SQL Store       │  SQLite FTS5 + Vec   │
└───────────────────────┴──────────────┬───────────────┴──────────────────────┘
                                       │
                                       ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                           DATA LAYER: THE ATLAS                             │
├───────────────────────┬──────────────────────────────┬──────────────────────┤
│  FUB CRM READ/WRITE   │  PostHog Behavior Signals    │  Google Calendar API │
├───────────────────────┼──────────────────────────────┼──────────────────────┤
│  Resend Email Out     │  Bluedot Meeting Transcripts │  Calendly Webhooks   │
├───────────────────────┼──────────────────────────────┼──────────────────────┤
│  CloudCMA Reports     │  RealEstateAPI.com Data      │  BatchData Bulk Data │
├───────────────────────┴──────────────────────────────┴──────────────────────┤
│  Lob.com Direct Mail, Phase 3 only                                           │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 1.3 Tech Stack Manifesto

The following stack is mandatory for the proof of concept. Substitutions require explicit sign-off because the handbook, test plan, deployment model, and configuration schemas assume these components.

| Layer | Technology | Version or Baseline | Notes |
| :---- | :---- | ----: | :---- |
| Agent orchestration | CrewAI | Latest stable, `>=0.80` | Phase 1 only; framework is swappable. |
| LLM reasoning engine | Claude via Anthropic API | `claude-sonnet-4-6` | All reasoning calls pass through service wrappers. |
| API gateway | FastAPI | `>=0.110` | Python 3.11+ environment. |
| Task queue and cron | APScheduler or Celery | Latest stable | Supports proactive monitor and delayed sequence scheduling. |
| Deployment | Self-hosted VPS | Ubuntu 22.04 LTS | One isolated VPS per realtor during POC. |
| Config and secrets | `python-dotenv` + centralized `config.py` | Current | No inline `os.environ` access. |
| Short-term context cache | Redis | `>=7.0` | Ephemeral session memory. |
| Durable preference store | SQLite for POC | Current | Migrate to Postgres at scale. |
| Trajectory ledger | SQLite FTS5 + vector extension | Current | Historical execution and semantic lookup. |
| Personality store | Markdown `soul.md` | Current | Invariant identity and operational constraints. |
| Email delivery | Resend | API v1 | Outbound transactional email pipeline. |
| CRM data engine | Follow Up Boss | REST API v1 | Core system of record. |
| Behavioral analytics | PostHog | Python SDK v3 | Website and funnel behavior traces. |
| Scheduling engine | Calendly | API v2 | Appointment booking events. |
| Calendar engine | Google Calendar | API v3 | Calendar read/write loops. |
| Messaging layer | Telegram Bot API | v7.x | Sole daily realtor interface. |
| Transcription intake | Bluedot | Webhook payload | Meeting summary and action-item ingestion. |
| CMA generation | CloudCMA | API or widget workflow | Generates raw CMA asset; agent wraps output. |
| Property data, enrichment, prospect lists | RealEstateAPI.com | Pay-per-record | Default POC data source for unpredictable volume. |
| Bulk enrichment and mass sweeps | BatchData | Subscription + low per-record | Phase 3 and higher-volume jobs. |
| Direct mail | Lob.com | API v1 | Future gated direct mail foundation. |
| Containerization | Docker + Compose | Latest stable | Standardized multi-container app. |

### 1.4 Architectural Guardrails and Code Style

Business logic must live strictly within application source code. CrewAI is a swappable orchestration layer, not the place where durable business rules belong. Every routing rule, preference compiler, campaign trigger, data transformation, eligibility decision, compliance block, and retry policy must be implemented as framework-agnostic Python code. CrewAI may be used only for agent instantiation, linear task delegation, and memory primitives. If a capability requires CrewAI-specific syntax beyond those boundaries, the capability must be refactored into `tools/` or `services/`.

| Rule Category | Mandatory Standard |
| :---- | :---- |
| Python baseline | Python 3.11+ with explicit type hints on every function signature. |
| Agent implementation | Avoid class-based agent overrides where functional Python suffices. |
| External integrations | All integrations live inside `services/` and use retry wrappers. |
| Agent tools | All tools live inside `tools/` as pure standalone functions importable without CrewAI. |
| Config access | Environment variables are loaded only through `app/config.py`. |
| Logging | Use Python `logging` with structured JSON; one logger per module. |
| Hardcoding | No API keys, user names, bot identities, sequence IDs, stage IDs, or schedule values in source code. |
| Secrets | `.env` is never committed; `.env.example` contains names only. |
| Realtor identity | Read from `soul.md`, preference store, and config JSON. |
| FUB topology | Read from `realtors/{client-name}/fub-config.json`. |
| Cron schedules | Read from `realtors/{client-name}/scheduler-config.json`. |

### 1.5 Zero-Hardcoding Policy

API credentials are loaded from `.env` through the centralized configuration engine. Realtor, agent, bot, and user identities are parsed from `soul.md`, `RealtorProfile`, and deployment-specific config. FUB account topology, including stages, canonical tags, and sequence UUIDs, is derived from `realtors/{client-name}/fub-config.json`. Scheduler runtimes are loaded from `realtors/{client-name}/scheduler-config.json`. Property-data vendor selection is loaded from `realtors/{client-name}/property-data-config.json`, allowing the system to switch between RealEstateAPI.com, BatchData, and CloudCMA pathways without changing agent code.

---

## 2. Cognitive Memory Architecture and Multi-Tier Governance

### 2.1 Memory Design Objective

The agent must remain teachable without becoming prompt-bloated, contradictory, or unsafe. The system therefore separates short-term conversational context, invariant persona constraints, durable user preferences, knowledge retrieval, historical execution traces, and deterministic programmatic guardrails. These layers prevent dynamic user corrections from corrupting the core personality file while allowing the agent to improve operational behavior over time.

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                       SIX COGNITIVE LAYERS OF MEMORY                        │
├───────────────────────┬─────────────────────────────────────────────────────┤
│ 1. Session Context    │ Ephemeral chat buffers and stateful message chains.  │
├───────────────────────┼─────────────────────────────────────────────────────┤
│ 2. Static Persona     │ Core operational constraints and system behavior.    │
├───────────────────────┼─────────────────────────────────────────────────────┤
│ 3. Knowledge Base     │ Vectorized market guides and compliance data.        │
├───────────────────────┼─────────────────────────────────────────────────────┤
│ 4. Preference Store   │ SQL-managed dynamic constraints and user changes.    │
├───────────────────────┼─────────────────────────────────────────────────────┤
│ 5. Trajectory Ledger  │ FTS5-indexed execution history and feedback loops.   │
├───────────────────────┼─────────────────────────────────────────────────────┤
│ 6. Programmatic Guard │ Pure-Python validators and schema blocks.            │
└───────────────────────┴─────────────────────────────────────────────────────┘
```

### 2.2 Six Operational Memory Layers

| Layer | Technical Implementation | Functional Mechanics |
| :---- | :---- | :---- |
| Ephemeral session context | Redis-backed structured string queues | Captures immediate Telegram loops and Supervisor state. Flushes when intent boundary changes or after 30 minutes of inactivity. |
| Invariant static persona | Read-only `realtors/{client-name}/soul.md` | Holds identity, tone sliders, and non-negotiable operational limits. Dynamic preference writes are barred from directly modifying this file in production. |
| Epistemic knowledge base | ChromaDB or CrewAI-native vector index over `knowledge/` | Grounds the agent in local market guides, Fair Housing references, FUB field dictionaries, and vendor docs. |
| Dynamic preference store | SQLite or Postgres managed by `PreferenceCompiler` | Converts user instructions into structured hard or soft rules without appending prompt bloat. |
| Semantic trajectory ledger | SQLite FTS5 virtual table plus vector embedding column | Allows full-text and semantic lookup across prior agent actions, failures, feedback, and resolutions. |
| Programmatic guardrails | Pydantic models, validators, and Python interceptors | Enforces safety, compliance, consent, approval, and identity boundaries regardless of LLM output. |

### 2.3 Preference Consolidation Compiler

The `PreferenceCompiler` processes dynamic realtor instructions through a strict compilation pipeline. Its purpose is to capture teachability while preventing contradictions, stale directives, and uncontrolled prompt growth.

```
[Conversational Input]
        │
        ▼
[Parse and Classify via Claude]
        │
        ▼
[Query Active DB Constraints]
        │
        ▼
[Run Contradiction Filter]
        ├── Matches Overlap? ──> [Flag Realtor for Resolution]
        └── No Conflict? ──────> [Upsert to Store and Evict Cache]
```

Hard rules override soft rules. Newer soft rules evict conflicting older soft rules. New hard rules that contradict existing hard rules require explicit realtor confirmation before replacement. The compiled dynamic prompt footprint must remain below 1,000 tokens. If compiled preferences exceed this limit, the compiler must deduplicate by category, remove inactive entries, summarize repeated directives, and escalate unresolved conflicts.

### 2.4 Preference Write and Read Flow

Version 2.0 appended dynamic instructions to `soul.md`; Version 2.1 made `soul.md` invariant. Version 3.0 resolves this by treating `soul.md` as a read-only deployment artifact in production. The **database preference store** is the authoritative teachability layer. A human engineer may update `soul.md` during controlled deployment revisions, but the live agent must not append to it during a Telegram conversation.

| Flow | Required Behavior |
| :---- | :---- |
| Write flow | Realtor sends instruction; Supervisor classifies intent as `INSTRUCTION`; Claude parses a structured rule; Supervisor asks for confirmation; confirmed rules are written to `PreferenceEntry`; Redis session context is updated immediately; cached compiled preferences are evicted. |
| Read flow | `soul.md` loads at Supervisor initialization; active preferences are queried from DB; `PreferenceCompiler` returns a deduplicated prompt fragment; specialist agents receive compiled context plus relevant hard guards. |
| Conflict resolution | Hard-rule contradictions require realtor confirmation. Soft-rule contradictions may be overwritten silently but must be logged. |
| Audit trail | Every created, replaced, deactivated, or escalated preference must be logged in `AgentActionLog` and preference DB metadata. |

---

## 3. Data Models and Configuration Schemas

### 3.1 Core Pydantic Entities

```py
from datetime import datetime
from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, EmailStr, Field

class RealtorProfile(BaseModel):
    realtor_id: str
    fub_user_id: int
    agent_name: str
    telegram_chat_id: str
    soul_md_path: str
    fub_api_key_name: str
    posthog_api_key_name: str
    resend_api_key_name: str
    timezone: str
    created_at: datetime
    updated_at: datetime

class PreferenceEntry(BaseModel):
    id: Optional[int] = None
    realtor_id: str
    preference_type: Literal["hard", "soft"]
    category: Literal["communication", "routing", "tone", "scheduling", "formatting", "cma", "direct_mail"]
    instruction: str
    parsed_rule: str
    active: bool = True
    scope_target: Optional[str] = None
    created_at: datetime
    source: Literal["explicit", "inferred"]

class LeadEvent(BaseModel):
    id: Optional[int] = None
    realtor_id: str
    fub_contact_id: int
    event_type: str
    payload: Dict[str, Any]
    processed: bool = False
    processing_agent: Optional[str] = None
    output_summary: Optional[str] = None
    created_at: datetime
    processed_at: Optional[datetime] = None

class AgentActionLog(BaseModel):
    id: Optional[int] = None
    realtor_id: str
    agent_name: str
    action_type: str
    fub_contact_id: Optional[int] = None
    input_summary: str
    output_summary: str
    success: bool
    error_message: Optional[str] = None
    duration_ms: int
    created_at: datetime

class AppointmentLedger(BaseModel):
    appointment_uid: str
    source_origin: Literal["calendly", "google_calendar", "fub_activity"]
    calendly_event_id: Optional[str] = None
    google_event_id: Optional[str] = None
    fub_contact_id: Optional[int] = None
    normalized_attendee_emails: List[EmailStr]
    start_time_utc: datetime
    timezone: str
    appointment_type: Literal[
        "buyer_consult", "seller_consult", "valuation_call", "partner_meeting", "unknown"
    ]
    contact_classification: Literal[
        "lead_related", "client_related", "past_client", "associate_vendor", "internal", "unknown"
    ]
    brief_status: Literal["eligible_pending", "generated", "suppressed_non_lead"]
    cma_status: Literal["not_applicable", "eligible_pending", "generated", "suppressed"]
    last_verified_at: datetime
    event_hash: str

class CMAReportJob(BaseModel):
    job_id: str
    realtor_id: str
    fub_contact_id: int
    property_address: str
    trigger_source: Literal["seller_appointment", "telegram_request", "manual_admin", "test"]
    vendor: Literal["cloudcma", "custom_portal"]
    status: Literal["queued", "generating", "generated", "wrapped", "failed", "suppressed"]
    pdf_url: Optional[str] = None
    view_url: Optional[str] = None
    wrapper_url: Optional[str] = None
    executive_summary: Optional[str] = None
    created_at: datetime
    completed_at: Optional[datetime] = None
    error_message: Optional[str] = None

class PendingOperation(BaseModel):
    id: Optional[int] = None
    operation_type: str
    service_name: str
    payload: Dict[str, Any]
    retry_count: int = 0
    next_retry_at: datetime
    status: Literal["queued", "retrying", "failed", "completed"]
    created_at: datetime
    updated_at: datetime
```

### 3.2 `soul.md` Structure

Each realtor deployment has one invariant file at `realtors/{client-name}/soul.md` (e.g. `realtors/ben-olsen/soul.md`). It is loaded into the Supervisor’s system context at initialization and should be changed only through controlled deployment edits.

```
# Agent Identity
name: Sarah
realtor_name: Ben Olsen
brokerage: BrightWork Realty
timezone: America/Los_Angeles

# Communication Style
tone: professional but warm
verbosity: concise — lead with the key point, details follow
formality_level: 4/10  # 1=very casual, 10=very formal
uses_emoji: false

# Hard Operational Boundaries
- Do not surface contacts tagged "Do Not Contact" or "Archived".
- Never execute text or email transmissions between 9:00 PM and 7:00 AM Pacific.
- Always stage drafts in the FUB queue; direct raw API broadcasting is locked.
- When contact resolution confidence is low, escalate to the realtor.
- Never mention AI in client-facing communications.

# Soft In-Session Preferences
- Pre-appointment briefs are generated and delivered at T-24h unless overridden.
- Summary text formats must lead with actionable talking points.
- Telegram updates must contain one clear operational event per message.

# Voice Notes for Client-Facing Drafts
- Sign emails as "Ben" rather than "Ben Olsen".
- Use a direct, neighborly, non-corporate style.
- Avoid generic luxury clichés; sound specific to the neighborhood and property.
```

### 3.3 `fub-config.json`

```json
{
  "realtor_id": "ben_olsen_brightwork",
  "pipeline_stages": {
    "new_lead": 1001,
    "attempting_contact": 1002,
    "active_lead": 1003,
    "under_contract": 1004,
    "closed": 1005,
    "nurture": 1006
  },
  "canonical_tags": {
    "sources": ["zillow", "homes.com", "website", "referral", "open_house", "cold_outreach", "homelight", "calendly"],
    "intent": ["buyer", "seller", "both", "renter", "investor"],
    "lifecycle": ["hot", "warm", "cold", "do_not_contact"],
    "program": ["quiet_listing", "moraga_cc", "presale_construction"],
    "compliance": ["bluedot_consent", "do_not_contact", "archived"],
    "automation": ["auto_brief", "cma_generated", "review_sent"]
  },
  "sequences": {
    "new_buyer_lead": "seq_001",
    "new_seller_lead": "seq_002",
    "appointment_set": "seq_003",
    "post_close_review": "seq_004",
    "referral_request": "seq_005",
    "long_term_nurture": "seq_006"
  },
  "webhook_events_enabled": [
    "peopleCreated",
    "peopleStageUpdated",
    "peopleTagsCreated",
    "appointmentsCreated",
    "appointmentsUpdated"
  ],
  "closed_stage_ids": [1005],
  "review_sequence_id": "seq_004",
  "referral_sequence_id": "seq_005"
}
```

### 3.4 `property-data-config.json`

```json
{
  "realtor_id": "ben_olsen_brightwork",
  "cma_vendor": "cloudcma",
  "default_enrichment_vendor": "realestateapi",
  "bulk_enrichment_vendor": "batchdata",
  "batch_threshold_records": 1000,
  "cloudcma": {
    "suppress_native_email_distribution": true,
    "capture_pdf_url": true,
    "capture_view_url": true,
    "wrapper_strategy_enabled": true
  },
  "realestateapi": {
    "use_cases": ["instant_inbound_enrichment", "boutique_list_pulling", "market_updates", "expired_listings", "divorce_filings", "distressed_properties"],
    "cost_model": "$0.10/record, no monthly base"
  },
  "batchdata": {
    "use_cases": ["phase_3_direct_mail_sweeps", "continuous_database_auditing", "large_geo_exports"],
    "cost_model": "$0.01/record plus platform subscription"
  }
}
```

### 3.5 `scheduler-config.json`

```json
{
  "timezone": "America/Los_Angeles",
  "brief_scan_interval_minutes": 15,
  "calendar_watch_renewal_hours": 24,
  "morning_digest_time": "07:30",
  "quiet_hours": {
    "start": "21:00",
    "end": "07:00"
  },
  "post_close_referral_delay_days": 7,
  "direct_mail_weekly_cap": 20,
  "fub_retry_backoff_seconds": [2, 4, 8],
  "default_pending_approval_timeout_hours": 4,
  "approval_deferred_after_hours": 24
}
```

---

## 4. Endpoints and Integration Blueprint

### 4.1 Internal FastAPI Routes

All webhook routes must return quickly and must hand work to asynchronous processors. Routes that are called by vendors should never execute expensive LLM or property-data work synchronously.

| Route | Purpose | Authentication | Response Rule |
| :---- | :---- | :---- | :---- |
| `POST /telegram/webhook` | Receives realtor Telegram messages and approval replies. | `X-Telegram-Bot-Api-Secret-Token`; chat ID whitelist. | Return `200 OK` within 500 ms; swallow route-level errors to prevent retry loops. |
| `POST /fub/webhook` | Receives CRM contact and stage events. | `FUB-Signature` HMAC-SHA256 (see §4.3). | Return `200 OK` immediately after enqueue; invalid signatures return `401`. |
| `POST /calendly/webhook` | Receives appointment created and canceled events. | `X-Calendly-Webhook-Signature`. | Return `200 OK` after enqueue. |
| `POST /bluedot/webhook` | Receives meeting transcript payloads. | Shared secret header. | Return `200 OK`; suppress processing if consent tag is absent. |
| `POST /cloudcma/webhook` | Receives CMA job completion callback. | Shared secret or vendor signature. | Return `200 OK`; store `pdf_url` and `view_url`; trigger wrapper pipeline. |
| `POST /posthog/webhook` | Optional behavioral event bridge. | PostHog secret. | Return `200 OK`; do not mutate CRM unless identity is high confidence. |
| `POST /lob/webhook` | Future direct mail status callback. | Lob signature. | Phase 3 only; log status events. |
| `GET /health` | Health check. | None. | Return status, realtor ID, and agent version. |

### 4.2 Telegram Webhook

The Telegram webhook is the realtor’s primary operating interface. It must verify the Telegram secret token, reject or ignore unregistered chat IDs, combine rapid message bursts into one execution stream when messages arrive within five seconds, and route classified intents to the Supervisor.

```json
{
  "update_id": 987654321,
  "message": {
    "chat": { "id": 11223344 },
    "text": "Stop sending me briefs for vendor coordination syncs",
    "date": 1780348200
  }
}
```

If the route encounters an internal processing error after authentication, it must log the error and still return `200 OK` to Telegram. This prevents Telegram from repeatedly redelivering the same update. Messages from unregistered chat IDs are ignored silently but logged as security-relevant attempts.

### 4.3 FUB Webhook

The FUB webhook receives contact creation, stage changes, tag events, and appointment-related CRM events. It must validate the `FUB-Signature` header: Base64-encode the raw JSON payload (non-prettified), compute HMAC-SHA256 using the X-System-Key, and compare the result to the header value. Events generated by the system’s own credential footprint must be dropped to prevent recursive loops.

Note: `appointmentsCreated`, `appointmentsUpdated`, and `appointmentsDeleted` fire only for appointments created directly in FUB—not for appointments synced from integrated calendars (Google or Office 365). Calendly and Google Calendar webhooks cover externally booked appointments.

```json
{
  "eventId": "c3b1a2d4-e5f6-7a8b-9c0d-1e2f3a4b5c6d",
  "eventCreated": "2026-06-03T18:22:00+00:00",
  "event": "peopleStageUpdated",
  "resourceIds": [40942],
  "uri": "https://api.followupboss.com/v1/people?id=40942",
  "data": { "stage": "Closed" }
}
```

Invalid signatures return `401`. Valid events are written to `LeadEvent`, deduplicated by event ID or event hash, and enqueued. If FUB itself is unavailable during downstream processing, required write operations are cached in SQLite as `PendingOperation` records and retried within five minutes. After three failed retry loops, the system alerts the realtor by Telegram and records a critical failure.

### 4.4 Calendly Webhook

Calendly webhooks subscribe to `invitee.created` and `invitee.canceled`. On `invitee.created`, the agent looks up the invitee email in FUB. If found, it updates the contact stage to `appointment_set`, logs the activity, enrolls the contact in the appointment sequence, and schedules a brief for T-24h. If not found, it creates a contact, applies the `source:calendly` tag, and follows the same appointment-set path.

```json
{
  "event": "invitee.created",
  "payload": {
    "event_type": { "name": "Seller Consultation" },
    "event": {
      "start_time": "2026-06-10T17:00:00Z",
      "end_time": "2026-06-10T17:30:00Z",
      "location": { "type": "zoom", "location": "https://zoom.example" }
    },
    "invitee": {
      "name": "Alex Seller",
      "email": "alex@example.com",
      "questions_and_answers": [{ "question": "Address", "answer": "123 Moraga Way" }]
    }
  }
}
```

### 4.5 Bluedot Webhook

Bluedot transcripts are only processed when the associated FUB contact has the `bluedot_consent` tag or another explicit consent marker approved during onboarding. If consent is missing, the webhook returns `200 OK`, logs suppression, and takes no content action.

```json
{
  "meeting_id": "bd_123",
  "participants": ["ben@example.com", "client@example.com"],
  "transcript": "Full transcript text...",
  "summary": "Meeting summary...",
  "action_items": ["Send valuation range", "Confirm timeline"],
  "duration_seconds": 2700,
  "recorded_at": "2026-06-10T18:00:00Z"
}
```

### 4.6 CloudCMA Webhook and CMA Job Callback

CloudCMA is used to generate the raw CMA report. The agent must suppress CloudCMA’s native client email distribution by leaving `email_to` empty or using the equivalent vendor setting. The report is returned to the FastAPI loop through a completion callback.

```json
{
  "job_id": "cma_brief_task_40942",
  "status": "success",
  "pdf_url": "https://cloudcma.com/reports/download/a1b2c3d4e5f6.pdf",
  "view_url": "https://cloudcma.com/presentations/a1b2c3d4e5f6",
  "address": "123 Moraga Way, Moraga, CA 94556"
}
```

The callback must create or update a `CMAReportJob`, store the `pdf_url` and `view_url`, generate a polished executive summary using the Draft Agent, and, when wrapper mode is enabled, create a branded digital dashboard URL.

---

## 5. External API Integration Requirements

### 5.1 Follow Up Boss

Follow Up Boss is the system of record. Authentication uses HTTP Basic Auth with the API key as username and an empty password. The system must respect a baseline rate cap of 500 requests per hour. All calls must use exponential backoff on 429s and transient 5xx responses.

| Endpoint | Purpose |
| :---- | :---- |
| `GET /contacts/{id}` | Fetch contact by ID. |
| `POST /contacts` | Create contact. |
| `PUT /contacts/{id}` | Update contact fields. |
| `POST /contacts/{id}/tags` | Apply tags. |
| `POST /contacts/{id}/notes` | Write note. |
| `POST /contacts/{id}/emails` | Create email draft. |
| `GET /contacts?email={email}` | Lookup by email. |
| `POST /events` | Log activity. |
| `GET /pipelines` | Fetch stage definitions. |
| `POST /contacts/{id}/sequences` | Enroll in sequence. |

The retry policy is three attempts with delays of 2, 4, and 8 seconds. If the API remains unavailable, the operation is queued in SQLite and retried within five minutes. Three failed queued retries trigger a Telegram alert.

### 5.2 PostHog

PostHog provides behavioral context but must never block core lead processing. The identity resolution assumption for the POC is that `distinct_id` maps to the contact email address. If no identity is found, the system proceeds without behavioral data and adds an explicit `DATA_GAP: PostHog context unavailable` marker in internal generation context.

Behavioral analytics footprints must be anchored by validated, single-owner properties. IP-address matches and generic unlinked device data are low-confidence supporting indicators only. They must not drive automatic CRM updates, CRM note generation, or contact mutation.

### 5.3 Google Calendar

Google Calendar is used for appointment monitoring and pre-appointment brief triggering. The default implementation is per-user OAuth2 because it works for personal Google accounts and Google Workspace accounts. Service-account delegation may be supported later for managed Workspace deployments.

| Operation | Requirement |
| :---- | :---- |
| List events | Pull events in the next 72 hours. |
| Watch events | Prefer push notifications where possible. |
| Poll fallback | Poll every 15 minutes if push channel expires. |
| Brief trigger | Any qualifying external-attendee event without an existing brief. |
| Suppression | Internal meetings, vendor meetings, personal placeholders, and low-confidence contact matches are suppressed. |

### 5.4 Telegram Bot API

Telegram sends messages using `POST https://api.telegram.org/bot{token}/sendMessage` with `chat_id`, `text`, and `parse_mode`. The message limit is 4,096 characters; longer messages must be split. The allowed chat IDs are configured during onboarding. Approval requests use concise structured prompts.

```
[Contact Name] — [action proposed]
Approve / Edit / Call first
```

The realtor may reply with `approve`, `edit [text]`, or `call`. If no response arrives within four hours, the agent sends a reminder. If no response arrives within 24 hours, the operation is logged as deferred and surfaced in the morning digest.

### 5.5 Resend

All outbound email goes through Resend. The `From` address is configured during onboarding as `{agent_name}@{realtor_domain}` or an approved development fallback. All sends must be logged to `AgentActionLog`. Client-facing sends must never bypass realtor approval. Drafts must be staged in the FUB email queue before any outbound client transmission.

### 5.6 CloudCMA

CloudCMA powers the POC CMA generation path. The Property & CMA Agent does not send raw CloudCMA links directly to clients unless the realtor explicitly requests that fallback. Instead, it captures `pdf_url` and `view_url`, creates an internal record, and optionally wraps the report in a high-end branded dashboard.

### 5.7 RealEstateAPI.com and BatchData

RealEstateAPI.com and BatchData replace ATTOM as the property-data and enrichment strategy. RealEstateAPI.com is the default for unpredictable individual calls and niche list pulls during the POC because it has no fixed monthly overhead in the supplied cost model. BatchData becomes the preferred option for heavy bulk processing, geographic sweeps, and continuous database auditing once record volumes justify the platform subscription.

| Agent Task | RealEstateAPI.com | BatchData | Operational Winner and Rationale |
| :---- | ----: | ----: | :---- |
| Instant inbound lead enrichment from a FUB `new_contact` webhook | `$0.10` per call | `$0.01` per call plus subscription fraction | **RealEstateAPI.com** because 50–200 unpredictable lead calls do not justify a large base subscription during launch. |
| Boutique list pulling such as 30 recent divorce, tax lien, expired, or distressed-property records in Moraga | Approximately `$3.00` for 30 records | Approximately `$0.30` plus platform subscription | **RealEstateAPI.com** because small tests can be run cheaply without committing to a platform contract. |
| Phase 3 direct-mail sweeps such as 3,500 quarterly branding records for Lob | Approximately `$350.00` | Approximately `$35.00` plus subscription base | **BatchData** once volume crosses into multi-thousand-record exports. |
| Continuous database auditing over 2,000 older CRM contacts | High variable cost | Low incremental per-record cost | **BatchData** because recurring large scans favor lower per-record pricing. |

### 5.8 Lob.com

Lob.com is future Phase 3 direct mail infrastructure. During the POC, all direct mail logic is isolated behind deep operational gates. The hard cap is 20 physical records per week unless explicitly changed in `scheduler-config.json` and approved by a human operator. Direct mail must never execute from an inferred audience without realtor confirmation.

---

## 6. Agent Suite and Responsibilities

### 6.1 Supervisor Agent

The Supervisor loads `soul.md`, queries compiled preferences, classifies realtor Telegram messages, delegates tasks to specialist agents, enforces routing boundaries, and coordinates approvals. It must not contain low-level vendor logic; those operations belong in services and tools.

### 6.2 Lead Intake Agent

The Lead Intake Agent handles FUB lead events, duplicate detection, PostHog enrichment attempts, routing, tagging, sequence enrollment, and realtor notifications. It must implement the ordered routing rules and edge-case matrix in Section 7.1.

### 6.3 Scheduling Coordinator Agent

The Scheduling Coordinator handles Calendly events, FUB stage updates for appointments, appointment sequence enrollment, and cancellation notifications. It must schedule briefs at T-24h and mark `AppointmentLedger` records idempotently.

### 6.4 Calendar Monitor Agent

The Calendar Monitor scans Google Calendar, renews watch channels when required, detects qualifying external-attendee meetings, suppresses non-lead events, and triggers pre-appointment briefs or CMA jobs when eligibility conditions are met.

### 6.5 Brief and Report Generator Agent

The Brief and Report Generator synthesizes FUB activity, PostHog behavior, calendar context, appointment notes, and Bluedot transcripts into realtor-facing briefs. It must never fabricate behavioral data. Missing data is omitted or marked as a data gap.

### 6.6 Property and CMA Agent

The Property and CMA Agent generates CMAs for seller prospects. It is triggered when the realtor has a scheduled meeting with a new seller, when a qualifying valuation appointment is detected, or when the realtor requests a CMA via Telegram. In the POC, the agent generates a CloudCMA report as-is, captures the output, and stores it. The next iteration wraps the CloudCMA output in a custom branded online portal.

### 6.7 Draft and Communications Agent

The Draft and Communications Agent prepares client-facing emails, SMS drafts where supported, CMA wrapper copy, follow-up notes, and approval prompts. It must always stage client-facing drafts for realtor review and must never mention AI in client-facing text.

### 6.8 Proactive Monitor Agent

The Proactive Monitor runs scheduled scans for stale leads, missing follow-ups, upcoming appointments, data gaps, and deferred approvals. It is phase-gated and should not trigger autonomous client-facing sends.

---

## 7. Feature Specifications and State-Machine Matrices

### 7.1 Lead Intake and Routing

**Trigger:** FUB webhook receives a new contact event.

```
RECEIVED → ENRICHING → ROUTING → ENROLLED → NOTIFIED
                         │
                         ▼
                       ERROR
```

| State | Meaning |
| :---- | :---- |
| `RECEIVED` | Webhook payload received, authenticated, deduplicated, and queued. |
| `ENRICHING` | PostHog and RealEstateAPI.com enrichment are attempted where eligible. |
| `ROUTING` | Tags, lifecycle stage, and sequence are selected. |
| `ENROLLED` | FUB sequence enrollment and CRM updates succeeded. |
| `NOTIFIED` | Realtor received Telegram notification. |
| `ERROR` | Processing failed after retries or required identity was unresolved. |

Routing logic is evaluated in order, and the first match wins.

| Priority | Condition | Action |
| ----: | :---- | :---- |
| 1 | Contact has `Do Not Contact` or equivalent tag | Log receipt and take no further action; do not notify realtor unless configured for compliance visibility. |
| 2 | Source is `zillow`, `homes.com`, or equivalent buyer portal | Apply source tag and enroll in `new_buyer_lead`. |
| 3 | Source is `website` and `has_property_inquiry = true` | Tag `intent:seller` and enroll in `new_seller_lead`. |
| 4 | Source is `referral` | Tag `source:referral`, apply `warm`, and enroll in `new_buyer_lead` or seller path if inquiry indicates seller intent. |
| 5 | Source is `open_house` | Tag `source:open_house` and enroll in `new_buyer_lead`. |
| 6 | Default | Tag `source:unknown`, enroll in `new_buyer_lead`, and flag for realtor review. |

| Edge Case | Required Behavior |
| :---- | :---- |
| Duplicate email exists in FUB | Update existing record, do not create a new contact, and log `duplicate_lead`. |
| Missing email | Skip PostHog lookup, apply available tags, create a high-priority manual review task, and notify the realtor. |
| Missing phone and email | Do not enrich; create contact only if FUB payload has enough source metadata; otherwise escalate. |
| FUB rate limit | Queue operation for retry in 60 seconds or according to retry config. |
| FUB 5xx | Queue operation in SQLite and retry within five minutes. |
| Telegram notification failure | Log failure but do not roll back CRM work. |

### 7.2 Deterministic Contact Identity Resolution

```
[Incoming Identity Payload]
        │
        ▼
[Query FUB by Email]
        ├── Match Found ───────> [High Confidence Resolution]
        └── No Match
                │
                ▼
[Query FUB by Normalized Phone]
        ├── Match Found ───────> [High Confidence Resolution]
        └── No Match
                │
                ▼
[Query FUB by Structural Metadata]
        ├── Fuzzy Name Match ──> [Low Confidence: Escalate to Telegram]
        └── Zero Records ──────> [Create New CRM Contact Entry]
```

Low-confidence matches must not modify existing CRM records automatically. The agent may present a suggested match to the realtor through Telegram and wait for confirmation.

### 7.3 Pre-Appointment Brief

**Trigger:** Calendar Monitor detects a qualifying appointment at T-24h, unless a different timing preference is configured.

```
TRIGGERED → GATHERING → GENERATING → DELIVERING → COMPLETE
                 │             │             │
                 └─────────────┴─────────────▼
                                            ERROR
```

Required brief content includes contact name, appointment time, appointment type, location, lead source, original inquiry context, PostHog behavioral summary when available, last five FUB interactions, recommended talking points with a maximum of three, suggested questions with a maximum of two, and timeline indicators from notes or prior conversations.

If PostHog data is unavailable, the behavioral section is omitted or marked as a data gap. If the FUB contact is not found for a calendar event, the agent asks the realtor to confirm the contact and does not generate a brief. If the appointment is canceled by Calendly, the agent sends a Telegram notification and suppresses brief generation. If a brief already exists for the appointment, the system skips generation.

Claude generation calls have a 30-second timeout. If the first call times out, the system retries once. If the second attempt fails, the agent sends a fallback Telegram alert with raw FUB metadata only: `Sarah could not generate the brief for [Contact]. Here is what I have: [raw FUB data summary].`

### 7.4 Supervisor and Telegram Conversation

**Trigger:** Registered realtor sends Telegram message.

| Intent | Behavior |
| :---- | :---- |
| `QUERY` | Extract contact or topic, fetch relevant data, respond within 30 seconds where possible, and log. |
| `INSTRUCTION` | Parse as a persistent preference, confirm understanding, write confirmed rule to preference DB, and update current session context. |
| `APPROVAL` | Match to an open approval request; approve, edit, or close according to realtor reply. |
| `ESCALATION` | Prioritize and notify with urgency marker; do not bypass compliance or approval gates. |
| `UNKNOWN` | Ask for clarification and take no action. |

Rapid messages arriving within less than five seconds are combined into one execution stream. Messages outside business hours may be processed and answered, but any outbound client-facing action must respect quiet-hour rules.

### 7.5 Closed Transaction Trigger

**Trigger:** FUB stage-change event where the new stage is included in `closed_stage_ids`.

| Step | Required Action |
| ----: | :---- |
| 1 | Verify the contact is not already enrolled in the post-close sequence by checking `AgentActionLog` and the trajectory ledger. |
| 2 | Enroll the contact in `review_sequence_id` unless `review_sent` or equivalent exists. |
| 3 | Schedule referral sequence enrollment after seven days or configured delay. |
| 4 | Log both enrollment steps. |
| 5 | Notify the realtor through Telegram. |

Repeated identical closing-stage payloads must be idempotent. A non-close stage change takes no action. A sequence enrollment failure is retried three times and then escalated.

### 7.6 Property and CMA Agent Workflow

The CMA Agent has two release modes. The POC mode generates a standard CloudCMA report and stores the result. The enhanced mode wraps that report inside a custom digital dashboard that feels premium rather than generic.

```
[Seller Appointment or Realtor CMA Request]
        │
        ▼
[Resolve Contact and Property Address]
        │
        ▼
[Create CloudCMA Job with Native Email Suppressed]
        │
        ▼
[Receive pdf_url and view_url]
        │
        ├── POC Mode ─────────────> [Store Report and Notify Realtor]
        │
        └── Wrapper Mode ─────────> [Generate Branded Portal]
                                      │
                                      ▼
                             [Stage Client-Facing Draft]
                                      │
                                      ▼
                               [Realtor Approval]
```

| Trigger | Eligibility Rule | Output |
| :---- | :---- | :---- |
| Seller consultation booked | Appointment type is seller consult or valuation call and property address exists. | CloudCMA report job and realtor notification. |
| Realtor asks “generate CMA for [address/contact]” | Contact or address resolves with sufficient confidence. | CloudCMA report job. |
| Lead intake suggests seller intent | CMA is not auto-generated unless appointment exists or realtor requests it. | Optional prompt asking whether to generate. |
| Missing property address | Ask realtor for address; do not guess. | Pending CMA request. |

#### 7.6.1 CloudCMA Wrapper Strategy

The recommended enhanced presentation strategy is to host a bespoke single-property digital dashboard. CloudCMA generates the raw report; the Property and CMA Agent captures the report URLs; the agent populates a minimalist HTML/Tailwind template; the client receives a branded page rather than a raw CloudCMA link.

```
[CloudCMA API] ──> [Raw PDF and Live View Link]
        │
        ▼
[Property & CMA Agent] ──> [Styled Cloudflare Template]
        │
        ▼
[Beautiful Digital Experience] ──> [Sent via approved Resend email or SMS path]
```

The wrapper page should include a polished conversational executive summary written in Ben’s neighborhood voice, brokerage fonts and colors, property address, high-level valuation framing, clear next-step CTA, and a button reading **View Complete Valuation Details** that opens the underlying CloudCMA report. Client delivery remains approval-gated.

### 7.7 Direct Mail and Prospecting Programs

Prospecting programs such as expired listings, divorces, distressed properties, tax liens, market updates, and geographic branding sweeps use RealEstateAPI.com or BatchData based on volume. During the POC, list pulls can be performed for strategy testing, but direct mail execution remains out of scope except for gated Phase 3 experiments capped at 20 physical records per week.

---

## 8. Testing, Quality Assurance, and Evaluation Framework

### 8.1 Pre-Deployment Checklist

```shell
ruff check .
mypy . --strict
pytest tests/unit/ -v --cov=app --cov-report=term-missing
pytest tests/integration/ -v
pytest --cov=app --cov-fail-under=80
```

All checks must pass with zero failures before deployment. Integration tests require sandbox or test credentials for FUB, PostHog, Telegram, Calendly, Resend, and any enabled property-data vendors.

### 8.2 Required Unit Test Registry

Every function in `services/` and `tools/` requires a unit test. Minimum coverage is 80%, with priority on integration boundaries and deterministic routing tools.

| Module | Required Test Functions |
| :---- | :---- |
| `services/fub.py` | `test_create_contact_success`, `test_create_contact_duplicate_returns_existing`, `test_apply_tags_success`, `test_apply_tags_rate_limit_retries`, `test_enroll_sequence_success`, `test_enroll_sequence_api_failure_queues_retry` |
| `services/posthog.py` | `test_get_person_by_email_found`, `test_get_person_by_email_not_found_returns_none` |
| `services/cloudcma.py` | `test_create_cma_job_success`, `test_create_cma_job_suppresses_native_email`, `test_cloudcma_callback_updates_job`, `test_cloudcma_failure_alerts_realtor` |
| `services/realestateapi.py` | `test_enrich_single_contact_success`, `test_enrich_missing_address_returns_data_gap`, `test_rate_limit_queues_retry` |
| `services/batchdata.py` | `test_bulk_export_success`, `test_bulk_job_cost_guardrail_blocks_unapproved_large_run` |
| `tools/lead_routing.py` | `test_route_zillow_lead`, `test_route_website_seller_lead`, `test_route_referral_lead`, `test_route_unknown_source_defaults_correctly`, `test_route_do_not_contact_takes_no_action` |
| `tools/preference_manager.py` | `test_write_preference_to_db`, `test_hard_preference_conflict_detected`, `test_soft_preference_overwrite_deactivates_old_rule`, `test_read_preferences_on_init`, `test_preference_compilation_conflict_resolution` |
| `tools/brief_generator.py` | `test_brief_generated_with_full_data`, `test_brief_generated_without_posthog_data`, `test_brief_not_duplicated_if_already_generated`, `test_claude_timeout_fallback_uses_raw_fub_summary` |
| `tools/cma_builder.py` | `test_cma_trigger_for_seller_appointment`, `test_cma_not_triggered_without_address`, `test_wrapper_page_contains_cloudcma_link`, `test_cma_client_delivery_requires_approval` |
| `webhooks/fub_webhook.py` | `test_new_contact_event_processed`, `test_stage_change_to_closed_triggers_sequence`, `test_unknown_event_type_logged_not_raised`, `test_invalid_signature_rejected_401` |
| `webhooks/telegram_webhook.py` | `test_unregistered_chat_ignored`, `test_valid_message_enqueued`, `test_rapid_messages_batched`, `test_route_errors_return_200_after_auth` |

Example memory compiler test:

```py
import pytest
from datetime import datetime
from app.models.preference import PreferenceEntry
from app.tools.preference_manager import PreferenceCompiler

def test_preference_compilation_conflict_resolution():
    compiler = PreferenceCompiler(realtor_id="ben_olsen_brightwork")

    rule_old = PreferenceEntry(
        realtor_id="ben_olsen_brightwork",
        preference_type="soft",
        category="formatting",
        instruction="Send long detailed narrative summaries",
        parsed_rule="format_style=narrative",
        created_at=datetime(2026, 6, 1, 9, 0, 0),
        source="explicit",
    )

    rule_new = PreferenceEntry(
        realtor_id="ben_olsen_brightwork",
        preference_type="soft",
        category="formatting",
        instruction="Keep summaries to short bullet points only",
        parsed_rule="format_style=bullets",
        created_at=datetime(2026, 6, 3, 12, 0, 0),
        source="explicit",
    )

    compiled_prompt = compiler.compile_dynamic_context([rule_old, rule_new])

    assert "format_style=bullets" in compiled_prompt
    assert "format_style=narrative" not in compiled_prompt
```

### 8.3 Required Integration Test Flows

| Flow | Scenario | Assertions |
| :---- | :---- | :---- |
| Flow 1: New lead end-to-end | POST a simulated Zillow lead to `/fub/webhook`. | Contact is tagged in FUB; sequence is enrolled; Telegram notification is sent; `AgentActionLog` contains `tag_applied`, `sequence_enrolled`, and `telegram_sent`. |
| Flow 2: Appointment brief end-to-end | Insert a test Google Calendar event at T-23h and run Calendar Monitor manually. | Brief is generated in FUB note; Resend call is made; Telegram summary is sent; `AgentActionLog` contains `brief_generated`. |
| Flow 3: Teachability round-trip | Send Telegram message: “Don’t send briefs for investor leads,” then confirm with “yes.” | Supervisor returns confirmation; `PreferenceEntry` is written with `category="routing"`; compiled preferences reflect the rule without modifying `soul.md`. |
| Flow 4: Closed transaction idempotency | POST stage-change webhook with closed stage ID twice. | First event enrolls review sequence and schedules referral; second event does not duplicate enrollment. |
| Flow 5: CMA generation | Create seller appointment with address and run Calendar Monitor. | `CMAReportJob` is created; CloudCMA job uses native email suppression; callback stores `pdf_url` and `view_url`; realtor receives approval-gated notification. |
| Flow 6: CMA wrapper | Simulate CloudCMA success callback with wrapper mode enabled. | Wrapper page is created; page includes executive summary and CloudCMA CTA; client-facing delivery is staged but not sent without approval. |

### 8.4 LLM Evaluation Criteria

| Evaluation Target | Input | Required Criteria |
| :---- | :---- | :---- |
| Brief Generator | 10 contacts with varied PostHog data and FUB histories. | All available required fields included; talking points derive from data; tone matches `soul.md`; no hallucinated details; full brief is 300–500 words; Telegram summary is five lines max. |
| Intent Classification | 20 Telegram messages covering all intent types. | Classification accuracy is at least 90%; unknown intent does not trigger action; instruction intent extracts a parseable rule. |
| Preference Parsing | 10 natural-language instructions. | All outputs are unambiguous structured rules that a developer can verify. |
| Memory Regression | Conflicting style instructions and old/new preference combinations. | Preference overwrite precision is at least 98%; no context bleed into unrelated specialist agents. |
| Hallucination Boundary | Contacts with missing behavioral or property data. | Output contains explicit data-gap markers and does not fabricate timelines, page views, property details, or valuation claims. |
| CMA Executive Summary | Five seller contacts with CloudCMA outputs. | Summary is conversational, compliant, locally specific, and does not overstate valuation certainty. |

---

## 9. Definition of Done

An engineering iteration is complete only when the system passes every applicable validation gate below.

| Category | Criterion | Assessment Command or Review |
| :---- | :---- | :---- |
| Static code integrity | Zero lint and type errors. | `ruff check . && mypy . --strict` |
| Unit and integration tests | All test suites pass. | `pytest tests/ -v` |
| Coverage | At least 80% coverage on `services/` and `tools/`. | `pytest --cov=app --cov-fail-under=80` |
| Secrets | No API keys or secrets in source. | `grep -r "sk-|Bearer|api_key\s*=" app/` returns zero secret hits. |
| Config | All realtor-specific values live in `.env` or config JSON. | Manual review. |
| Logging | Every agent action is logged. | Spot check three core flows. |
| `soul.md` loading | Supervisor prompt populates correctly. | `python -c "from app.config import load_soul"` |
| Webhooks | Routes respond within 500 ms after validation. | `pytest tests/integration/test_webhooks.py` |
| Retry logic | FUB, Resend, CloudCMA, and property-data calls use retry wrappers. | Code review confirms external calls use shared retry decorator. |
| Identity guardrails | Automated runs perform zero invalid CRM modifications. | `pytest tests/integration/test_identity_locks.py` |
| Loop control | Webhooks do not trigger recursive self-generated events. | `pytest tests/integration/test_idempotency.py` |
| Dynamic memory | Preferences compile and inject without prompt-length drift. | `python -m app.evals.run_memory_regression` |
| CMA safety | Client-facing CMA delivery requires approval. | `pytest tests/integration/test_cma_approval.py` |

---

## 10. Deployment and Repository Layout

### 10.1 Production Directory Architecture

```
cos_agent/
├── app/
│   ├── main.py
│   ├── config.py
│   ├── agents/
│   │   ├── supervisor.py
│   │   ├── lead_intake.py
│   │   ├── scheduling.py
│   │   ├── calendar_monitor.py
│   │   ├── brief_generator.py
│   │   ├── property_cma.py
│   │   ├── proactive_monitor.py
│   │   └── draft_comms.py
│   ├── tools/
│   │   ├── lead_routing.py
│   │   ├── brief_builder.py
│   │   ├── cma_builder.py
│   │   ├── identity_resolution.py
│   │   ├── trajectory_index.py
│   │   ├── preference_manager.py
│   │   └── approval_flow.py
│   ├── services/
│   │   ├── fub.py
│   │   ├── posthog.py
│   │   ├── google_calendar.py
│   │   ├── calendly.py
│   │   ├── telegram.py
│   │   ├── resend.py
│   │   ├── bluedot.py
│   │   ├── cloudcma.py
│   │   ├── realestateapi.py
│   │   ├── batchdata.py
│   │   └── lob.py
│   ├── webhooks/
│   │   ├── fub_webhook.py
│   │   ├── telegram_webhook.py
│   │   ├── calendly_webhook.py
│   │   ├── bluedot_webhook.py
│   │   ├── cloudcma_webhook.py
│   │   └── lob_webhook.py
│   ├── models/
│   │   ├── realtor.py
│   │   ├── preference.py
│   │   ├── lead_event.py
│   │   ├── action_log.py
│   │   ├── appointment.py
│   │   └── cma.py
│   └── scheduler/
│       └── jobs.py
├── realtors/
│   └── {client-name}/              # e.g. ben-olsen
│       ├── soul.md
│       ├── fub-config.json
│       ├── property-data-config.json
│       ├── scheduler-config.json
│       ├── knowledge-base/
│       ├── fub/
│       └── sequences/
├── knowledge/
│   ├── local_market_guide.md
│   ├── fair_housing_compliance.pdf
│   └── fub_field_dictionary.md
├── prompts/
│   ├── brief_generator.md
│   ├── intent_classifier.md
│   ├── preference_parser.md
│   ├── cma_executive_summary.md
│   └── client_email_draft.md
├── tests/
│   ├── unit/
│   └── integration/
├── .env
├── .env.example
├── docker-compose.yml
└── requirements.txt
```

### 10.2 Environment Variables

```shell
# Anthropic
ANTHROPIC_API_KEY=

# Follow Up Boss
FUB_API_KEY=
FUB_WEBHOOK_SECRET=

# PostHog
POSTHOG_API_KEY=
POSTHOG_PROJECT_ID=

# Google Calendar
GOOGLE_CALENDAR_CREDENTIALS_PATH=
GOOGLE_OAUTH_CLIENT_ID=
GOOGLE_OAUTH_CLIENT_SECRET=

# Calendly
CALENDLY_API_KEY=
CALENDLY_WEBHOOK_SECRET=

# Telegram
TELEGRAM_BOT_TOKEN=
TELEGRAM_ALLOWED_CHAT_IDS=
TELEGRAM_WEBHOOK_SECRET=

# Resend
RESEND_API_KEY=
RESEND_FROM_ADDRESS=

# Bluedot
BLUEDOT_WEBHOOK_SECRET=

# CloudCMA
CLOUDCMA_API_KEY=
CLOUDCMA_WEBHOOK_SECRET=

# RealEstateAPI.com
REALESTATEAPI_KEY=

# BatchData
BATCHDATA_API_KEY=

# Lob, Phase 3
LOB_API_KEY=
LOB_WEBHOOK_SECRET=

# Internal
REALTOR_ID=
DATABASE_URL=sqlite:///./cos_agent.db
REDIS_URL=redis://redis:6379/0
LOG_LEVEL=INFO
AGENT_VERSION=3.0.0
```

---

## 11. Implementation Timeline and Rollout Plan

The target POC rollout spans approximately 20 weeks from environment setup through multi-tenant readiness. Dates should be anchored after Ben Olsen’s onboarding decisions are finalized.

| Phase | Weeks | Objective | Deliverables |
| :---- | ----: | :---- | :---- |
| Phase 0: Setup and onboarding audit | 1–2 | Confirm accounts, credentials, FUB topology, bot setup, calendar access, Resend domain, and CloudCMA path. | `.env`, config JSON, `soul.md`, FUB stage/tag audit, test credentials, deployment VPS. |
| Phase 1: Core lead and Telegram loop | 3–6 | Build FastAPI gateway, Telegram Supervisor, FUB webhook intake, lead routing, retries, action logs, and preference store. | Working new-lead E2E flow and teachability round-trip. |
| Phase 2: Calendar, briefs, and communications | 7–10 | Add Google Calendar, Calendly, pre-appointment briefs, Resend delivery, approval workflow, and Bluedot ingestion. | Appointment brief E2E flow and approval-gated draft flow. |
| Phase 3: CMA and property intelligence | 11–14 | Add Property & CMA Agent, CloudCMA job creation, callback processing, RealEstateAPI.com enrichment, and wrapper prototype. | CMA generation flow, branded portal proof, and data-source selection guardrails. |
| Phase 4: Scaled operations and direct mail foundations | 15–18 | Add BatchData bulk workflows, database audit jobs, Lob dry-run path, and direct-mail gating. | BatchData bulk test, Lob sandbox status tracking, capped mailer experiment design. |
| Phase 5: Hardening and multi-tenant readiness | 19–20 | Harden observability, idempotency, regression evals, migration plan, and instance isolation. | Production runbook, regression suite, backup procedure, and scale-readiness review. |

---

## 12. Onboarding and Strategy Meeting Checklist

The Wednesday strategy meeting must resolve the following nine items before full build execution. If an answer is unavailable, the team must choose the interim approach listed here and mark the decision as provisional.

| Decision | Required Answer | Interim Approach |
| :---- | :---- | :---- |
| 1. CloudCMA access and workflow | Confirm whether Ben uses CloudCMA and whether API/widget callbacks are available. | Build `cloudcma.py` behind an interface and stub callback payloads. |
| 2. Property-data accounts | Confirm RealEstateAPI.com and BatchData account status. | Use RealEstateAPI.com as default and leave BatchData disabled. |
| 3. Calendly ownership | Confirm existing Calendly account, event types, and event IDs. | Stub event type IDs and replace during onboarding. |
| 4. Google Calendar auth | Confirm personal Google account or Workspace account. | Implement per-user OAuth2. |
| 5. Telegram bot | Confirm BotFather bot username and production token. | Use development bot until production token is created. |
| 6. Resend domain | Confirm sender domain and DNS access. | Use Resend development fallback until custom domain verification. |
| 7. FUB topology | Confirm stages, tags, sequence IDs, and closed-stage ID. | Populate `realtors/{client-name}/fub-config.json` from audit; block sequence calls until IDs are confirmed. |
| 8. Business hours and approval boundaries | Confirm quiet hours, approval timeouts, and which actions may be autonomous. | Default to 9 PM–7 AM quiet hours and approval required for all client-facing sends. |
| 9. Bluedot consent and transcript policy | Confirm consent capture method and FUB tag. | Suppress transcript processing unless `bluedot_consent` is present. |

---

## 13. Out of Scope and System Boundaries

The following capabilities are out of scope for the POC and must not be implemented unless a later signed scope revision explicitly adds them.

| Capability | Status |
| :---- | :---- |
| Multi-tenant broker hierarchy, cross-broker seat management, or licensing administration | Out of scope. |
| Autonomous client-facing broadcasts that bypass human verification approvals | Out of scope and prohibited. |
| Direct social media posting, ad spend automation, or social media execution scripts | Out of scope. |
| Full direct-mail automation at scale | Phase 3 gated foundation only; not a POC core feature. |
| Sequence content authoring for all future campaigns | Parallel workstream; not required for core system build. |
| Platform migration from CrewAI to LangGraph or managed cloud orchestration | Future architecture consideration only. |
| ATTOM integration | Removed from current architecture. |

---

## 14. Open Architectural Dependencies

| Dependency | Current Decision | Build Impact |
| :---- | :---- | :---- |
| CloudCMA implementation details | CloudCMA is the POC CMA vendor; wrapper strategy is the preferred next layer. | Requires API/widget confirmation and callback setup. |
| RealEstateAPI.com versus BatchData routing | REAPI is default for POC; BatchData is used for bulk jobs. | Requires cost guardrails and vendor abstraction. |
| Google auth scope | Per-user OAuth2 is default. | Works across personal and Workspace accounts. |
| Resend domain | Unknown until onboarding. | Development can proceed with fallback but production send requires verification. |
| FUB sequence content | IDs may exist before content is complete. | Enrollment code can be tested; production sequence effectiveness depends on content. |
| PostHog identity gaps | Proceed without PostHog data. | No blocking behavior; data gaps must be explicit. |

---

## 15. Build Acceptance Checklist

This checklist confirms that the Version 3.0 handbook has restored the material lost during the Version 2.1 compression and integrated the new prompt requirements.

| Restored or Added Asset | Included |
| :---- | ----: |
| Full unit test inventory with explicit function names | Yes |
| Four original integration flows | Yes |
| Additional CMA integration flows | Yes |
| Lead intake ordered edge-case matrix | Yes |
| Claude timeout fallback logic | Yes |
| Telegram rapid-message batching | Yes |
| Webhook error-handling and `200 OK` behavior | Yes |
| FUB retry and SQLite fallback mechanics | Yes |
| Phased rollout schedule through 20-week target | Yes |
| Wednesday strategy meeting checklist | Yes |
| Six-layer cognitive memory architecture | Yes |
| Preference Compiler and conflict rules | Yes |
| CMA Agent with CloudCMA POC and wrapper path | Yes |
| RealEstateAPI.com and BatchData replacement for ATTOM | Yes |
| Direct-mail and bulk data phase gates | Yes |

---

## References

