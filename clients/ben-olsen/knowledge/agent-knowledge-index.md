# agent-knowledge-index.md

Purpose: Master index of all knowledge-base files for the BrightWork CoS agent. Describes each file's contents and the agent use case that triggers loading it.

Agent Use: Loaded at initialization. Agent consults this index to determine which files are relevant for a given task before loading full file contents.

Maintained by: MKTNG.co

Last updated: June 2026

---

## How to Use This Index

1. Identify the task type (copy generation, contact routing, appointment prep, data write, etc.).
2. Load only the files whose trigger tasks match the current operation.
3. For client-facing copy, always load `voice-guide.md`, `brand-context.md`, and `fair-housing-language.md` together.
4. For any FUB read or write, load `source-of-truth-matrix.md` before acting.
5. Sequence content lives in `realtors/ben-olsen/sequences/` — load the specific sequence file when drafting or reviewing sequence emails, not at initialization.

---

## Knowledge-Base Files

### agent-knowledge-index.md

**Path:** `realtors/ben-olsen/knowledge-base/agent-knowledge-index.md`

**Description:** This file — the master routing table that maps agent tasks to the knowledge files that contain the rules and context for those tasks.

**Load when:** Agent initialization; any time the agent needs to determine which other files to load for an unfamiliar task.

---

### voice-guide.md

**Path:** `realtors/ben-olsen/knowledge-base/voice-guide.md`

**Description:** Ben Olsen's personal voice, tone, reasoning patterns, hard copy rules, and program framing constraints for all client-facing communications.

**Load when:** Drafting or reviewing emails, SMS, letters, blog posts, sequence copy, social posts, or any outbound message written in Ben's voice; checking formatting rules (no em dashes, no signature blocks, REALTOR not Broker, etc.).

---

### brand-context.md

**Path:** `realtors/ben-olsen/knowledge-base/brand-context.md`

**Description:** BrightWork Realty Advocates brand positioning, promise, audience personas, program inventory, landing page references, and messaging pillars.

**Load when:** Writing marketing copy, program introductions, listing narratives, or outreach that references BrightWork services; selecting the right message angle for a contact persona; explaining what BrightWork offers vs. a generic agent.

---

### local-market-context.md

**Path:** `realtors/ben-olsen/knowledge-base/local-market-context.md`

**Description:** Geographic and market context for Ben's service territory — Lamorinda cities, Moraga Country Club, Walnut Creek, Pleasant Hill, Rossmoor, price bands, school districts, and seasonal dynamics.

**Load when:** Generating appointment briefs; framing a contact by geography; writing copy with local market references; flagging Rossmoor cooperative workflow or MCC floor-plan context; verifying school district boundaries by address.

---

### fair-housing-language.md

**Path:** `realtors/ben-olsen/knowledge-base/fair-housing-language.md`

**Description:** Fair Housing Act and California FEHA compliance rules — protected classes, prohibited language patterns, school district copy rules, and Rossmoor/MCC/senior content constraints.

**Load when:** Any client-facing copy touches a neighborhood, community, property, or contact; compliance review before delivering drafts; uncertain whether phrasing could imply steering, demographic preference, or age-targeted suitability.

---

### contact-classification-taxonomy.md

**Path:** `realtors/ben-olsen/knowledge-base/contact-classification-taxonomy.md`

**Description:** FUB contact classification hierarchy, pipeline stage definitions, lead source-to-sequence mapping, tag interpretation rules, and contact handling decision logic.

**Load when:** Routing a new or existing contact to a sequence; determining enrollment eligibility; interpreting FUB stage, type, or source fields; deciding whether to initiate outreach, pause a sequence, or flag for Ben review.

---

### source-of-truth-matrix.md

**Path:** `realtors/ben-olsen/knowledge-base/source-of-truth-matrix.md`

**Description:** Authoritative data source for every data type the agent reads or writes, conflict resolution rules, and per-system write permissions.

**Load when:** Any read or write to FUB, PostHog, Google Calendar, BatchData, CloudCMA, or SkySlope/Dotloop; resolving conflicting data between systems; before updating contact fields, stages, or tags; before enrolling a contact in a sequence.

---

### posthog-event-schema.md

**Path:** `realtors/ben-olsen/knowledge-base/posthog-event-schema.md`

**Description:** PostHog event definitions, property schemas, and identity linkage conventions for Ben's landing pages and the MCC site.

**Load when:** Enriching contact briefs with web behavioral context; interpreting form submission or page-view events; matching PostHog `distinct_id` to FUB contacts; building or validating UTM-attributed activity timelines.

---

### tag-taxonomy.md

**Path:** `realtors/ben-olsen/fub/tag-taxonomy.md`

**Description:** Complete FUB tag dictionary with source, meaning, and agent interpretation rules — program enrollment tags, MCC tags, suppression flags, VIP markers, and import flags.

**Load when:** Interpreting tags on a FUB contact record; verifying enrollment trigger tags before sequence assignment; checking suppression or VIP flags (`#HitList`, `Unsubscribed`, `chimeimport`, etc.); resolving tag-vs-field conflicts after reading structured fields.

---

### utm-catalog.md

**Path:** `realtors/ben-olsen/utm-catalog.md`

**Description:** Landing page URL registry and UTM parameter conventions (`utm_source`, `utm_medium`, `utm_campaign`, `utm_content`) for all BrightWork campaigns and channels.

**Load when:** Building tracked links in sequence emails, social posts, or SMS; matching a contact's inbound campaign to a landing page; appending UTM parameters to Calendly or program URLs in any outbound copy.
