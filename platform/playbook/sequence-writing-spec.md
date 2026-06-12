# Sequence Writing Spec
# Platform playbook — applies to all BrightWork deployments
# Tenant-specific values live in realtors/{name}/ directories
# Last updated: June 2026

---

## What a Sequence Is (and Is Not)

A sequence is a structured cadence of emails, SMS steps, and call tasks
delivered through Follow Up Boss native sequences. Sequences handle
the automated layer of lead nurture. They run without human intervention
once enrolled, except for:

- SMS steps: Ben pastes manually after CoS drafts and he approves via Telegram
- Day 0 first touch: see Day 0 Handling below

A sequence is **not**:

- A broadcast or newsletter. That is ActivePipe's role. ActivePipe is
  monthly only and is entirely separate from sequence architecture.
- A Gmail or Resend campaign. All sequence email sends go through FUB
  native sequences. No third-party email delivery for sequences.
- A replacement for a live conversation. The moment a real exchange begins,
  the sequence pauses.

---

## The Two Email Types

Every email in every sequence is one of exactly two types. Do not mix them.

### Type 1: Plain Text Email

Used for: Day 0 first touch, early cadence emails (Day 1 through approximately Day 7), 
and all final touch / nurture-transition emails.

Rules:
- No HTML formatting, no images, no dividers, no brand colors
- Looks like a personal email Ben would type himself
- Single-column, no header, no footer logo
- Standard email signature at bottom (see Signature Block below)
- Subject lines are conversational, not promotional
- Body reads as if Ben wrote it to one person, not as a broadcast

Purpose: These emails land in the inbox looking like a real message from a
real person. That is the design intent. Protect it.

### Type 2: Light HTML Program Overview Email

Used for: One per sequence, placed at Day 7-10 for standard-length sequences
(Day 4-5 for shorter sequences like HomeLight, 14 days max).

Rules:
- Use the appropriate pre-built HTML template:
  - Seller sequences: `seller-programs-v2.html`
  - Buyer sequences: `buyer-programs.html` (to be built)
- Single-column layout, BrightWork brand colors
- Shows programs relevant to that contact type only
- Each program card includes: program name, 2-3 sentence description, CTA button with UTM link
- Calendly CTA button at bottom with correct sequence-specific link
- All links must include full UTM parameters (see UTM Requirements below)
- Subject line for the HTML email is standardized: "A few programs worth knowing about"
- The CAMPAIGN_SLUG placeholder in the template Calendly URL must be replaced
  with the correct utm_campaign value for that sequence

This email is where program education lives. Nowhere else in the sequence
explains programs in full. Plain text emails mention programs by name only.

---

## Voice and Tone

All copy is written in Ben Olsen's personal voice. Before writing any
sequence email, read:

  `realtors/ben-olsen/knowledge-base/voice-guide.md`

Do not attempt to summarize or inline the voice guide. It is the source of truth.

Quick orientation (not a substitute for the full guide):
- Semi-formal, conversational, thinking-out-loud quality
- Uses contractions
- Concrete over abstract. Specific over generic.
- Warm and direct, never flowery
- Recommends a course of action with rationale, doesn't just present options
- Candid but never alarmist
- Earns trust by demonstrating he knows this market and is not rushing anyone

---

## Program Mention Rules

Programs are mentioned by name in plain text emails to create curiosity.
They are never explained in plain text emails.

The rule: **name only, no description, no explanation**. The landing page explains.
The plain text email creates a question only a conversation with Ben can answer.

Programs and their landing pages (seller-facing):
- Quiet Listing: https://quiet.brightworkrealty.com
- BrightFlip: https://brightflip.brightworkrealty.com
- Buy Before You Sell: https://buybefore.brightworkrealty.com
- Final Offer: https://finaloffer.brightworkrealty.com
- Relaunch: https://relaunch.brightworkrealty.com
- Senior Planning: https://seniors.brightworkrealty.com

Programs and their landing pages (buyer-facing):
- Off-Market Access: https://offmarket.brightworkrealty.com
- Buy Before You Sell: https://buybefore.brightworkrealty.com

Additional rules:
- Final Offer is a selective tool. Never frame it as a standard service.
  Ben decides whether it fits. The copy reflects that.
- Never say "pocket listing." Use "private buyer network" or "private listing."
- No specific dollar amounts or lender names for capital programs (BrightFlip,
  Buy Before You Sell). Describe the capability, not the terms.

---

## UTM Requirements

Every link in every email must include UTM parameters.
Use the UTM catalog at `realtors/ben-olsen/utm-catalog.md` as the source of truth.

Standard pattern for FUB sequence emails:
```
?utm_source=fub&utm_medium=email&utm_campaign={campaign-slug}&utm_content=day{N}
```

Where:
- `utm_source` is always `fub` for sequence emails
- `utm_medium` is always `email` for sequence emails
- `utm_campaign` is the campaign slug for the destination program (see catalog)
- `utm_content` is `day{N}` where N is the sequence day number

Examples:
- Day 3 email linking to Quiet Listing:
  `https://quiet.brightworkrealty.com?utm_source=fub&utm_medium=email&utm_campaign=quiet-listing&utm_content=day3`
- Day 10 email Calendly link in Zillow Seller sequence:
  `https://calendly.com/ben-brightwork/selling?utm_source=fub&utm_medium=email&utm_campaign=zillow-seller&utm_content=day10`

The `utm_content` parameter is set by the agent or defined when building the
sequence. Theresa and Ben do not set these manually.

---

## Calendly Links

Seller sequences use: `https://calendly.com/ben-brightwork/selling`
Buyer sequences use: `https://calendly.com/ben-brightwork/buying`

These are not interchangeable. Buyer links never appear in seller sequences.

Calendly links appear in every email EXCEPT the Day 0 first touch.
All Calendly links include full UTM parameters.

---

## Day 0 Handling

**OPEN DECISION — must be resolved before sequences go live in FUB.**

Two paths are under consideration:

**Path A (Telegram-first):** The CoS agent drafts the Day 0 email and SMS.
It sends Ben a Telegram alert with APPROVE / EDIT / CALL buttons.
If Ben approves within 30 minutes, the CoS sends via FUB. If Ben does not
respond within 30 minutes, FUB sends the Day 0 email automatically as a fallback.
Day 1 and beyond always run automatically through FUB.

**Path B (FUB-always):** FUB owns Day 0. The CoS agent drafts the text
and injects it into the FUB sequence before enrollment. Ben's Telegram
notification is informational only. FUB fires Day 0 automatically.

**How to write sequences until this is resolved:**
- Mark Day 0 steps clearly as `[TELEGRAM APPROVAL REQUIRED - PATH A]` or
  `[FUB AUTO - PATH B]` with a note
- Write the Day 0 email and SMS content for both paths identically
- The architecture of Day 1+ is unaffected by this decision
- Do not block sequence writing on this decision. Write the content.
  Flag the send mechanism.

---

## Structural Rules

### Cadence Patterns

Standard seller sequence (14-30 day active period):
- Day 0: First touch email + SMS + 2 call tasks
- Day 1: Follow-up email + call task
- Day 2: SMS
- Day 3: Email + call task
- Day 5: Email
- Day 7: SMS + call task
- Day 10: Email (typically the HTML program overview)
- Day 14: Final active pursuit email + final call task
- Day 30: Nurture transition email

Short seller sequence (HomeLight, high-intent warm transfer, 14 days max):
- Day 0: First touch email + call task
- Day 1: Email + call task
- Day 3: Email
- Day 5: HTML program overview email
- Day 7: SMS
- Day 10: Final active pursuit email
- Day 14: Nurture transition email

Event/community sequence (Senior Workshop, Expired Packet, lower urgency):
- Day 0: First touch email (no call tasks unless high intent)
- Day 3: Email
- Day 7: HTML program overview email
- Day 14: Follow-up email
- Day 30: Nurture transition email

### HTML Email Placement

For standard sequences: Day 7-10.
For short sequences: Day 4-5.
Place it after at least two plain text emails have established the
relationship. Do not lead with the HTML email.

### Maximum Sequence Length

Active pursuit phase: 14 days.
With nurture transition step: 30 days.
Do not add active pursuit steps after Day 14. Move to nurture.

### Nurture Transition

The final sequence step (typically Day 30) moves the contact to
long-term nurture. The email acknowledges the transition explicitly
("I'm going to move you to a lighter touch") and leaves a Calendly link
and an open invitation to reach back out.

After sequence end: 90-day seller nurture, quarterly homeowner market
update. No more call tasks.

### Exit Conditions

Exit conditions apply to all sequences. Pause-on-response must be ON for
all email steps.

A contact exits a sequence when any of the following occurs:
- Any email reply
- Any inbound call logged in FUB
- Any call over 2 minutes (per FUB call tracking)
- Stage changes to: Engaged, Listing Appointment, Active Seller, Active Buyer,
  Closed, or any equivalent terminal/hot stage

FUB's pause-on-response setting handles email replies automatically.
Stage-change exits must be configured per sequence in FUB.

---

## FUB Technical Constraints

### Personalization Fields Available in FUB Sequences
- `[first name]` — always use this, never use full name in email body
- `[last name]`
- `[address]` — property address if captured
- `[email]`
- `[phone]`

Do not use fields that may not be populated. If a field might be empty,
write around it in plain text or use `[first name]` only.

### Enrollment Triggers
Each sequence has a trigger condition defined in FUB. This is set in
`fub-config.json` per tenant. The sequence spec defines what the trigger
should be; the config file implements it.

### SMS Steps
SMS steps in FUB sequences cannot be automated. They appear as tasks.

The workflow for every SMS step:
1. CoS agent drafts SMS copy
2. Ben receives draft via Telegram and approves
3. Ben pastes the approved text into FUB manually and sends
4. Ben logs the activity in FUB

SMS copy in sequence docs is marked: `[BEN PASTES — CoS drafts, Ben approves via Telegram]`

### Call Tasks
Call tasks are assigned to Ben. They appear in his FUB task queue.
They are not automated. Include them in sequence docs with the attempt
number (First attempt, Second attempt, etc.) and any timing note
(e.g., "Schedule 2+ hours after first call").

---

## Email Signature Block
Do not include a signature block in sequence email copy.
FUB appends the account-level email signature to every outbound email
automatically. Embedding a signature in sequence copy produces a duplicate.
Sequence emails end with the last line of body copy. No name, no sign-off,
no contact information.

---

## Sequence File Format

Each sequence is a single Markdown file at:
`realtors/ben-olsen/sequences/{slug}.md`

File structure:
```
# Sequence Name
Trigger: [condition that enrolls this contact]
FUB stage: [starting stage]
Action plan: [FUB action plan name]
Exit conditions: [specific exit rules]
Nurture handoff: [what happens after sequence ends]
HTML email: [which template, which day, which campaign slug]

---

[Step table]

---

[Full copy for each step]
```

Step table columns: Step | Day | Channel | Executed by | Purpose

"Executed by" values:
- `CoS drafts, Ben approves via Telegram` (Day 0 email and SMS)
- `FUB auto` (automated email steps)
- `Ben pastes into FUB` (SMS steps)
- `Ben` (call tasks)

---

## Known Gaps (Resolve Before Writing Those Sequences)

1. **Buyer programs HTML template** (`buyer-programs.html`) does not exist yet.
   Off-Market Buyer VIP and Buy Before You Sell sequences cannot use the HTML
   email step until it is built. Write the placeholder in the sequence doc and
   flag it.

2. **No standalone buyer landing page for Buy Before You Sell.** The program
   has a landing page (`buybefore.brightworkrealty.com`) but it is framed for
   sellers. The buyer-facing sequence will need to reference this page or a
   future buyer-specific page. Flag in the campaign brief.

3. **invest.brightworkrealty.com** scope not confirmed with Ben. Do not include
   the Invest program in any sequence until scope is confirmed.

4. **Day 0 sender decision is open.** See Day 0 Handling above.

5. **Phone number in signatures.** See Email Signature Block above.

---

## Sequence Index

| # | Slug | Name | Bucket | Status |
|---|---|---|---|---|
| 1 | `zillow-seller` | Zillow Seller | High-intent seller | Draft exists — reference implementation |
| 2 | `homelight` | HomeLight | High-intent seller | Draft exists |
| 3 | `zillow-buyer` | Zillow Buyer | High-intent buyer | Draft exists |
| 4 | `mcc-estimator` | MCC Value Estimator | High-intent seller | Not started |
| 5 | `quiet-listing` | Quiet Listing Inquiry | High-intent seller | Not started |
| 6 | `brightflip` | BrightFlip Inquiry | High-intent seller | Not started |
| 7 | `final-offer` | Final Offer Inquiry | High-intent seller | Not started |
| 8 | `relaunch` | Relaunch Inquiry | High-intent seller | Not started |
| 9 | `off-market-buyer` | Off-Market Buyer VIP | High-intent buyer | Not started |
| 10 | `buy-before-you-sell` | Buy Before You Sell | High-intent buyer | Not started |
| 11 | `senior-workshop` | Senior Workshop Registrant | Event/community | Not started |
| 12 | `expired-packet` | Expired Packet Recipient | Event/community | Not started |

---

## How to Generate a New Sequence in Cursor

1. Read this spec fully.
2. Read `realtors/ben-olsen/knowledge-base/voice-guide.md`.
3. Read the Zillow Seller sequence at `realtors/ben-olsen/sequences/zillow-seller.md`
   as the reference implementation.
4. Read the campaign brief for the target sequence (see individual campaign
   brief files once generated).
5. Write the new sequence file to `realtors/ben-olsen/sequences/{slug}.md`.
6. Every email link must include UTM parameters from the catalog at
   `realtors/ben-olsen/utm-catalog.md`.
7. Mark Day 0 steps with the open decision flag.
8. Mark SMS steps with the `[BEN PASTES]` flag.
9. Place the HTML program overview email at the correct day for the sequence length.
10. Do not include any signature block or sign-off in email copy.
   FUB appends the account signature. Sequence copy ends at the last
   sentence of body text.

Do not write sequence emails from memory. Read the voice guide first.