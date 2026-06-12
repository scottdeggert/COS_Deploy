# source-of-truth-matrix.md
Purpose: Defines the authoritative data source for every data type the agent touches, conflict resolution rules, and write permissions per system
Agent Use: Consulted before any read or write operation. If two systems have conflicting data, this file determines which one the agent trusts. Write permissions here are hard limits — the agent does not write to a system unless explicitly permitted.
Maintained by: MKTNG.co
Last updated: June 2026

---

## The Rule

One system owns each data type. When systems conflict, the owner wins. The agent does not reconcile conflicts silently — it flags them for Ben.

---

## System Inventory

### Follow Up Boss (FUB)

CRM. Primary source of truth for all contact data, pipeline stage, sequence state, and activity history. All agent contact operations scope to contacts assigned to Ben Olsen unless explicitly instructed otherwise.

### PostHog

Behavioral analytics. Source of truth for web activity, form submission events, and cross-session identity signals from Ben's landing pages and the MCC site. Enrichment only — never overrides CRM state.

### Google Calendar

Appointment truth. Source of truth for Ben's scheduled appointments, times, and attendees. Calendar Monitor and Brief Generator read from here.

### Calendly

Scheduling layer. Feeds appointments into Google Calendar via integration. Calendly is the intake mechanism; Google Calendar is authoritative for what is actually on Ben's schedule.

### BatchData

Property data. Source of truth for ownership records, equity estimates, and property characteristics used in seller lead enrichment and prospecting sweeps.

### CloudCMA

Comparative market analysis. Draft-only outputs. Never authoritative. Always requires Ben approval before use or client delivery.

### SkySlope / Dotloop

Transaction management. Source of truth for contract state, contingency dates, and closing timelines on active transactions. Agent reads for context; does not modify.

### Cloudflare Workers

Form submission routing layer. Not a data store. Events pass through to FUB and PostHog. Agent does not read from or write to Workers directly.

---

## Data Type Ownership Matrix

| Data Type | Authoritative System | Secondary Reference | Agent Write Permission | Conflict Rule |
|---|---|---|---|---|
| Contact name, email, phone | FUB | Calendly booking form, PostHog identify events | FUB: update only when correcting blank or verified data; log change in activity note | FUB wins. Flag if Calendly or PostHog show different contact details. |
| Contact pipeline stage | FUB | — | FUB: permitted with previous state logged in activity note | FUB wins. Never infer stage from PostHog or Calendar. |
| Contact type (buyer/seller) | FUB (`type` field) | Tags (`Buyer`, `Seller`), form submission context | FUB: read preferred; update only with Ben instruction | Structured `type` field wins over tags. Flag tag conflicts. |
| Contact lead source | FUB (`source` field) | PostHog UTM parameters, landing page events | FUB: read only unless blank and high-confidence source from intake event | FUB `source` wins. Use PostHog UTMs to enrich briefs, not to overwrite source. |
| Active sequence enrollment | FUB (action plans, `Program:` tags) | — | FUB: enroll with Ben approval on first contact | FUB wins. Do not infer enrollment from tags alone — verify action plan state. |
| Last activity date | FUB (`lastActivity`) | PostHog last seen, Google Calendar last appointment | FUB: read only | FUB wins for CRM recency. PostHog supplements behavioral context only. |
| Appointment datetime and attendees | Google Calendar | Calendly booking record, FUB activity log | Read only (both systems) | Google Calendar wins. Flag if FUB has no matching activity log. |
| Property address associated with a contact | FUB (contact record, notes) | BatchData ownership lookup, Calendly form fields | FUB: update only when blank and verified from appointment or intake | FUB wins for contact association. BatchData wins for ownership verification at address level. |
| Property equity estimate | BatchData | FUB notes, CloudCMA draft | Read only (BatchData) | BatchData wins for automated estimates. Ben's manual notes win over BatchData when Ben explicitly stated a figure. Flag the conflict. |
| Property ownership record | BatchData | FUB contact record | Read only (BatchData) | BatchData wins. Flag if FUB contact name does not match BatchData owner of record. |
| Web behavioral events (page views, form submits) | PostHog | Cloudflare Workers event payload (transient) | Read only (PostHog) | PostHog wins. Workers events are not retained — do not treat Workers as reference. |
| PostHog identity (`distinct_id`) | PostHog | FUB email address (identity link assumption) | Read only (PostHog) | PostHog wins for behavioral identity. Match to FUB contact by email; flag if no match. |
| CMA draft | CloudCMA (draft output) | — | Initiate draft generation only; mark all outputs DRAFT | CloudCMA draft is never authoritative. Ben approval required before any client delivery. |
| Transaction contingency dates | SkySlope / Dotloop | FUB notes, Google Calendar | Read only (SkySlope / Dotloop) | SkySlope / Dotloop wins. FUB stage may lag — defer to transaction system for active deals. |
| Closing date | SkySlope / Dotloop | FUB notes, Google Calendar | Read only (SkySlope / Dotloop) | SkySlope / Dotloop wins. Flag if FUB stage does not reflect Under Contract or Closed. |

---

## Write Permission Rules

### FUB — permitted agent writes

- Add or update tags (additive only with `mergeTags: true` — never destructive)
- Update contact stage (log previous stage in activity note before overwriting)
- Log activity notes
- Enroll in sequence (with Ben approval on first contact)
- Update `customZipCodeOrigin` field if blank

### FUB — prohibited agent writes

- Delete contacts
- Remove tags without explicit Ben instruction
- Modify another agent's contacts (Kyle Lerch, Erin Kelly, Claudia Lee are off-limits)
- Change sequence content
- Overwrite existing stage without logging the previous state
- Create contacts without intake workflow authorization
- Send email or SMS directly from FUB without Ben approval

### PostHog — agent reads only. No writes.

### Google Calendar — agent reads only. No writes.

### Calendly — agent reads only. No writes.

### BatchData — agent reads only. No writes.

### CloudCMA — agent initiates draft generation only. All outputs marked DRAFT. Ben approves before any client delivery.

### SkySlope / Dotloop — agent reads only. No writes.

### Cloudflare Workers — not a data store. No reads or writes by the agent.

---

## Conflict Scenarios

### 1. FUB stage says Active, but PostHog shows no web activity in 90 days

**Resolution:** Trust FUB stage as pipeline truth. PostHog absence is not a stage conflict — it means the contact has not visited Ben's web properties recently. Note the behavioral gap in briefs (`DATA_GAP: no recent web activity`). Do not downgrade stage. Flag for Ben only if the contact is in an active sequence that depends on web re-engagement.

### 2. Google Calendar shows an appointment, but FUB has no matching activity log

**Resolution:** Trust Google Calendar for appointment datetime and attendees. Log a FUB activity note documenting the calendar event and the missing CRM record. Attempt to match the calendar attendee to an existing FUB contact by email. If no match, flag for Ben to confirm or create the contact. Do not suppress brief generation if the contact resolves — generate brief with a `DATA_GAP: FUB activity log missing for this appointment` marker.

### 3. BatchData equity estimate conflicts with a figure Ben mentioned in a note

**Resolution:** Ben's manually stated figure takes precedence for client-facing context and brief framing. BatchData figure remains the reference for automated enrichment fields. Flag the conflict to Ben with both values. Do not silently replace either figure. Do not include conflicting numbers in outbound copy without Ben resolution.

### 4. Two FUB tags suggest different sequence enrollment (e.g., `quiet-listing-inquiry` and `zillow-lead`)

**Resolution:** Structured fields win over tags per `contact-classification-taxonomy.md`. Check active action plan state in FUB — the enrolled sequence is authoritative. Do not enroll a second sequence. Flag the conflicting tags for Ben to clean up. If no action plan is active, route by structured `source` and `type`, then by most recent program tag timestamp.

### 5. A contact appears in both Ben's pipeline and another agent's contacts

**Resolution:** Stop all agent operations immediately. Do not read, write, tag, enroll, or draft copy for the contact. Flag for Ben with both agent assignments visible. Kyle Lerch, Erin Kelly, and Claudia Lee contacts are permanently off-limits unless Ben explicitly reassigns the contact.

---

## The Non-Negotiable

No autonomous client contact. All outbound communications — email, SMS, calls initiated by the agent — require Ben to review and approve before sending. This applies regardless of which system the contact data came from.
