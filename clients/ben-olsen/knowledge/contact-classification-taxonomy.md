# contact-classification-taxonomy.md
Purpose: Defines contact types, lead sources, funnel stages, and how the agent interprets FUB data to classify any given contact
Agent Use: Lead Router reads this to determine sequence eligibility and next-best action. Brief Generator reads this to frame who a contact is before an appointment. All FUB operations must be consistent with classifications defined here.
Maintained by: MKTNG.co
Last updated: June 2026

---

## Classification Hierarchy

The agent reads FUB structured fields first, tags second. This is a hard rule.

**Primary fields (in order of priority):**

1. `type` — Buyer, Seller, Buyer & Seller, Renter, Other
2. `stage` — the pipeline stage (see stage definitions below)
3. `source` — where the lead originated
4. `assignedTo` — must be Ben Olsen for any agent operation
5. `lastActivity` — recency signal
6. `customZipCodeOrigin` — maps contact to a market area (see `local-market-context.md`)

Tags are supplementary signals. If a tag contradicts a structured field, the structured field wins. Flag the conflict for Ben.

---

## FUB Stage Definitions

FUB may also use intent-specific entry stages (`New Buyer Lead`, `New Seller Lead`). Treat these as subtypes of **Lead** for routing purposes.

Use exact stage string values as they appear in Ben's FUB account (verified June 25, 2026).

| Stage | Meaning | Agent behavior |
|---|---|---|
| **Lead** | Just arrived, no contact yet | Confirm assignedTo before any action. High volume — filter by lastActivity before surfacing. Priority: trigger or confirm Day 0 sequence enrollment |
| **Attempted contact** | Outreach sent, no response | Monitor for re-engagement signals; do not duplicate Day 0 |
| **Spoke with customer** | Two-way communication established | Brief mode eligible; pause or exit active sequences per exit conditions |
| **Appointment set** | Appointment scheduled | Flag for pre-appointment brief |
| **Met with customer** | Consultation completed | Monitor next step |
| **Showing homes** | Active buyer | Do not interrupt with nurture sequences |
| **Listing agreement** | Listing signed | Transaction mode; no sequence contact |
| **Active listing** | Home on market | Do not sequence |
| **Submitting offers** | Offer in progress | Transaction mode; no sequence contact |
| **Active Client** | Actively working relationship | Brief mode; confirm whether an active sequence should continue or exit |
| **Nurture** | Active nurture contact | Sequence enrollment appropriate when source/tags warrant |
| **Nurture 6m+** | Long-horizon contact | Low-frequency contact |
| **Warm 3-6m** | Active nurture segment | Sequence appropriate |
| **Hot Prospect 0-3m** | High priority prospect | Surface in morning digest |
| **Pending** | Transaction pending | Defer to SkySlope/Dotloop; no sequence contact |
| **Past Client** | Prior closed transaction with Ben | No outreach; monitor for referral signals. Re-engage via sphere track |
| **Sphere** | Referral sources, past clients, neighbors | No auto-sequence without Ben approval |
| **Unresponsive** | No response over extended period | Suppress outreach; flag for Ben review |
| **Closed** | Closed transactions | No outreach; monitor for anniversary and referral triggers |
| **Non Client** | Not a client contact | No outreach without Ben instruction |
| **Trash** | Disqualified / junk | Suppress all operations |

**Engagement milestones** (used as sequence exit conditions, not primary pipeline stages): Engaged, Listing Appointment, Active Seller, Showing, Active Buyer. When a contact reaches any of these, active pursuit sequences should pause or hand off to nurture per sequence rules.

**FUB Deals module:** Transaction management, not pipeline. Do not confuse Deal stage with Contact stage.

---

## Lead Source Mapping

For each source: what it means, which sequence it maps to, and trust/intent level.

| Source | Meaning | Sequence | Trust / intent |
|---|---|---|---|
| **Zillow** | Portal lead, unverified intent | `zillow-buyer` if `type` = Buyer; `zillow-seller` if `type` = Seller and seller intent signal present (valuation inquiry, "thinking of selling") | Low–moderate. Portal behavior, not pre-qualified |
| **Realtor.com / Homes.com** | Portal lead, same logic as Zillow | `portal-buyer` or `portal-seller` (apply Zillow Buyer/Seller sequence logic until dedicated portal sequences exist) | Low–moderate |
| **HomeLight** | Referred lead, pre-screened by HomeLight | `homelight` | High. Warm transfer, seller-focused |
| **Final Offer landing page** | Seller lead from finaloffer.brightworkrealty.com | `final-offer` (trigger tag: `final-offer-inquiry`) | Moderate–high. Program-specific intent |
| **Off-Market landing page** | Buyer lead from offmarket.brightworkrealty.com | `off-market-buyer` (trigger tag: `off-market-lead`) | Moderate–high. Opted into private inventory access |
| **Buy Before You Sell landing page** | Buyer/seller hybrid from buybefore.brightworkrealty.com | `buy-before-you-sell` (trigger tag: `buy-before-you-sell-lead`) | Moderate–high. Dual-transaction intent |
| **Quiet Listing landing page** | Seller lead, privacy-first, from quiet.brightworkrealty.com | `quiet-listing` (trigger tag: `quiet-listing-inquiry`) | Moderate–high. Discretion-driven seller |
| **Relaunch landing page** | Expired listing owner, skeptical, from relaunch.brightworkrealty.com | `relaunch` (trigger tag: `relaunch-inquiry`) | Moderate. Frustrated prior listing experience |
| **BrightFlip landing page** | Seller with deferred maintenance, from brightflip.brightworkrealty.com | `brightflip` (trigger tag: `presale-improvement-inquiry`) | Moderate–high. Renovation-capital intent |
| **MCC Estimator** | Moraga Country Club seller via moragacountryclubrealestate.com | `mcc-estimator` (trigger tag: `MCC Estimator`) | Moderate–high. Community-specific, floor-plan driven |
| **Senior Workshop** | Event registration via seniors.brightworkrealty.com | `senior-workshop` (trigger tags: `workshop-registration`, `workshop-interest-list`) | Moderate. Long-horizon transition planning |
| **Agent Referral** | Referred by another agent | Agent Referral sequence (fallback: `general-buyer` or seller equivalent based on `type`) | High. Warm intro, professional referral |
| **Past Client** | Prior closed transaction with Ben/BrightWork | Nurture flow or direct Ben outreach — no automated sequence without Ben instruction | Highest. Existing relationship |
| **Open House** | In-person contact from open house sign-in | `general-buyer` if Buyer; seller outreach based on `type` and conversation notes | Moderate. In-person but intent varies |
| **Manual / Ben** | Ben entered directly in FUB | No sequence without Ben instruction | N/A — Ben-controlled |
| **Expired Packet Recipient** | Received mailed expired listing packet | `expired-packet` (trigger tag: `expired-listing`) | Moderate. Direct mail response, skeptical seller profile |
| **Website / General inquiry** | Contact form or inquiry not covered by a program landing page | `general-buyer` if Buyer; route seller by closest program tag or Ben review | Low–moderate |

---

## Tag Interpretation Rules

Full tag definitions live in `fub/tag-taxonomy.md`. Behavioral rules the agent must apply:

### Program and enrollment tags

Program tags are enrollment triggers for the matching sequence. Before enrolling, verify the corresponding sequence is not already active and the contact is not suppressed.

| Tag | Sequence | Notes |
|---|---|---|
| `off-market-lead` | Off-Market Buyer VIP | Canonical off-market landing page tag |
| `quiet-listing-inquiry` | Quiet Listing | Privacy-first seller |
| `presale-improvement-inquiry` | BrightFlip | Also appears as `Pre-Sale Reno` on MCC form |
| `final-offer-inquiry` | Final Offer | |
| `relaunch-inquiry` | Relaunch | |
| `buy-before-you-sell-lead` | Buy Before You Sell | Also `Buy Before Sell` on MCC form |
| `MCC Estimator` | MCC Value Estimator | Primary MCC trigger |
| `homelight-lead` | HomeLight | |
| `zillow-lead` | Zillow Buyer or Zillow Seller | Requires buyer/seller intent signal |
| `expired-listing` | Expired Packet | Direct mail response |

Do not re-enroll a contact who already carries an active `Program:` sequence tag unless Ben instructs.

### VIP and relationship tags

| Tag | Rule |
|---|---|
| `#HitList` | Ben's VIP relationship list. These contacts do **not** receive automated sequences. Flag for direct Ben action only. |
| `#AlwaysMail` | Direct mail override — include in mail campaigns unless `#NeverMail` or `Unsubscribed` blocks email |
| `#NeverMail` | Hard suppression for direct mail |

### Intent and priority tags

| Tag | Rule |
|---|---|
| `mcc-report-request` | Higher-intent signal than `MCC Estimator` alone. Brief Generator must note in appointment prep. |
| `Call Requested` | Highest-intent MCC signal. Trigger immediate follow-up alert to Ben. |
| `Hot 90 Days` | Active buy/sell within 90 days. Priority for direct outreach. |
| `Warm 6-12 Months` | Mid-priority nurture. |
| `Future seller` | Long-horizon seller intent. Nurture candidate, not active listing. |

### MCC Estimator — Interpretation Rule

MCC Estimator runs are awareness-stage behavior. A contact running valuations on one or more MCC properties is exploring options, not declaring intent to sell. Treat estimator activity as private context for Ben only — it tells him the contact is engaged and thinking, not that they are ready to transact.

In briefs: surface estimator activity as background signal ("has been exploring MCC values") not as a primary intent indicator. Never frame it as evidence of a selling decision. The opening move should invite the contact to share their thinking, not reference the valuations directly. Ben should let the contact lead with their own situation.

Exception: if the contact also submitted a call request on a specific property, that submission is an explicit intent signal and can be referenced. The call request is the signal. The valuation runs are the context.

### Pre-Appointment Brief vs. Lead Alert — Do Not Confuse These

Pre-appointment briefs are private intelligence for Ben. They summarize 
what Ben needs to know before a conversation. They never include a 
suggested opening line, drafted message, or anything framed as 
something Ben should say. End the brief at Situation.

Lead alerts are a separate feature triggered by new inbound contacts. 
They include drafted first-touch messages and approval buttons. 
Do not apply lead alert patterns to pre-appointment briefs.

### Import and data quality tags

| Tag | Rule |
|---|---|
| `chimeimport` | Historical Chime CRM import with low data quality. Do not initiate outreach without Ben verification. |
| `Import` | Batch-imported contact. No behavioral signal — do not auto-enroll. |
| `Corliss Neighbors` | Neighborhood canvass import (June 2026). No email sequences without explicit Ben approval. |

### Workshop tags

| Tag | Rule |
|---|---|
| `workshop-registration` | Confirmed event registration. Enroll in Senior Workshop sequence. |
| `workshop-interest-list` | Expressed interest only — not confirmed registration. Flag for Ben review before sequence enrollment. |
| `SeniorWorkshop` | Applied by event registration flow. Treat as workshop segment tag. |

### Suppression tags (hard stops)

| Tag | Rule |
|---|---|
| `Unsubscribed` | Hard email suppression. Never enroll in any email sequence. |
| `Bounced` | Do not send email. Flag for data cleanup. |

### Tags to ignore

- **Zillow-injected tags** (`Zillow Connected`, `Zillow High Intent Buyer`, etc.): Read `source` field instead.
- **City/location tags** (`ORINDA`, `MORAGA`, `WALNUT CREEK`, etc.): Zillow search-area noise. Read `customZipCodeOrigin` for geography.
- **Redundant type tags** (`Buyer`, `Seller`): Read structured `type` field instead.

---

## Contact Type Decision Tree

Plain-English logic the agent follows for every contact:

1. **Read `assignedTo`.** If not Ben Olsen, stop. No agent operations on this contact.

2. **Check suppression.** If `Unsubscribed`, `Bounced`, or `#NeverMail` applies to the planned channel, stop that channel. Email suppression is a hard block.

3. **Read `type`.** Is this a Buyer, Seller, Buyer & Seller, Renter, or Other? Buyer & Seller contacts route to the sequence matching their highest-intent signal (program tag or source).

4. **Read `source`.** Which sequence does this map to per the Lead Source Mapping table?

5. **Check active tags.** Do any program tags override source-based routing? Program tags take precedence over generic source when both are present and aligned with `type`.

6. **Check `stage`.** Is this contact in a state where sequence enrollment is appropriate?
   - Enroll: Lead, Attempted contact (if sequence not yet started), Nurture, Warm 3-6m, Nurture 6m+
   - Do not enroll: Pending, Listing agreement, Active listing, Submitting offers, Closed, Unresponsive, Trash, Non Client
   - Sphere: no auto-sequence without Ben approval
   - Brief mode: Spoke with customer, Appointment set, Met with customer, Showing homes, Active Client, Hot Prospect 0-3m

7. **Check `#HitList`.** If present, stop. Flag for direct Ben action only. No automated sequences.

8. **Check import flags.** If `chimeimport`, `Import`, or `Corliss Neighbors` is present without a fresh inbound signal, stop and flag for Ben verification.

9. **Verify sequence not already active.** Check for existing `Program:` tags or active action plan before enrolling.

10. **Map geography.** Read `customZipCodeOrigin` and cross-reference `local-market-context.md` for market framing in briefs.

11. **Route or flag.**
    - All checks pass → enroll in appropriate sequence or generate brief
    - Any conflict between tags and structured fields → structured field wins, flag conflict for Ben
    - Uncertainty → flag for Ben review rather than auto-enroll
