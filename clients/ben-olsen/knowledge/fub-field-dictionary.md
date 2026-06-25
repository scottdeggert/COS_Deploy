# fub-field-dictionary.md
Purpose: Complete reference for FUB structured fields, pipeline stages,
and lead sources as they exist in Ben Olsen's account. Pulled live from
the FUB API June 2026.
Agent Use: Brief Generator and Lead Router reference this before reading
or writing any contact record. Stage IDs and source strings here are the
canonical values — never infer or guess them.
Maintained by: MKTNG.co
Last updated: June 2026

---

## PRIMARY CONTACT FIELDS

These are structured fields on every FUB contact record. The agent
reads these first, before tags.

| Field | Type | Agent Use | Notes |
|---|---|---|---|
| `id` | integer | Primary key | Never modify |
| `firstName` / `lastName` | string | Display, personalization | |
| `stage` | string | Pipeline position | See stage list below |
| `type` | string | Buyer / Seller / Buyer & Seller / Renter / Other | Primary classification signal |
| `source` | string | Lead origin | See source list below |
| `assignedTo` | string | Owner filter | Must be "Ben Olsen" for all agent ops |
| `assignedUserId` | integer | Owner filter (numeric) | Ben's user ID: 1 |
| `contacted` | boolean | Has Ben made contact | 0 = no, 1 = yes |
| `tags` | array | Supplementary signals | Read after structured fields |
| `customZipCodeOrigin` | string | Geographic market signal | Maps to local-market-context.md |
| `price` | integer | Target price point | Buyer budget or seller expectation |
| `lastActivity` | datetime | Recency | Key signal for nurture vs. active |
| `emails` | array | Email addresses | Check `status` field — use Valid only |
| `phones` | array | Phone numbers | Check `isLandline` — prefer mobile |

---

## PIPELINE STAGES

Verified live from Ben Olsen's FUB account, June 25, 2026.
Use exact string values when reading or writing the `stage` field.

### API-Confirmed Stage IDs

| ID | Stage Name | People Count | Agent Behavior |
|---|---|---|---|
| 2 | Lead | 19,452 | New arrival. Confirm assignedTo before any action. High volume — filter by lastActivity before surfacing. |
| 24 | Attempted contact | 126 | Outreach sent, no response. Monitor for re-engagement. |
| 25 | Spoke with customer | 427 | Two-way contact established. Brief mode eligible. |
| 26 | Appointment set | 151 | Appointment exists. Flag for pre-appointment brief. |
| 27 | Met with customer | 101 | Consultation completed. Monitor next step. |
| 28 | Showing homes | 99 | Active buyer. Do not interrupt with nurture sequences. |
| 29 | Listing agreement | 0 | Listing signed. Transaction mode. |
| 30 | Active listing | 0 | Home on market. Do not sequence. |
| 31 | Submitting offers | 3 | Offer in progress. Transaction mode. |
| 12 | Active Client | 12 | Actively working relationship. |

### Stage IDs Pending (stages exist in account, IDs not yet pulled)

Run `GET /v1/stages?limit=50` to resolve these before building write logic.

| Stage Name | People Count | Agent Behavior |
|---|---|---|
| Nurture | 153 | Active nurture. Sequence appropriate. |
| Nurture 6m+ | 12 | Long-horizon. Low-frequency contact. |
| Warm 3-6m | 11 | Active nurture. Sequence appropriate. |
| Hot Prospect 0-3m | 6 | High priority. Surface in morning digest. |
| Pending | 2 | Transaction pending. Do not sequence. |
| Past Client | 6 | No outreach. Monitor for referral signals. Re-engage via sphere track. |
| Sphere | 5,656 | Largest meaningful segment. Referral sources, past clients, neighbors. No auto-sequence without Ben approval. |
| Unresponsive | 3 | Suppress outreach. Flag for Ben review. |
| Closed | 71 | No outreach. Closed transactions. Monitor for anniversary and referral triggers. |
| Non Client | 47 | No outreach without Ben instruction. |
| Trash | 3,083 | Suppress all operations. |

### Important Notes

- "Lead" (19,452) contains the Chime import dump. Do not treat as
  uniformly hot. Filter by lastActivity and source before surfacing.
- "Sphere" (5,656) is the largest active segment and the primary
  re-engagement opportunity. No sequence enrollment without explicit
  Ben approval.
- "Past Client" (6) is severely underpopulated relative to closed
  Deals count (85+ transactions). Past clients are likely sitting in
  Sphere or at their last active stage. This is a data hygiene gap.
- Closed transaction trigger must use Deals pipeline stage changes
  (dealsUpdated webhook), NOT peopleStageUpdated. Ben does not
  consistently move contacts to the "Closed" People stage.

---

## LEAD SOURCES

These are the actual source strings appearing in Ben's contact
records. The agent maps these to sequences and trust levels.

### Active / High-Volume Sources

| Source String | Description | Sequence | Trust Level |
|---|---|---|---|
| `Zillow` | Zillow Premier Agent portal | zillow-seller or zillow-buyer by type | Low-moderate |
| `Ben-Olsen-ZillowPremier` | Legacy Zillow Premier label | Treat same as Zillow | Low-moderate |
| `Zillow Rentals` | Zillow rental inquiries | No active sequence — flag for Ben | Low |
| `HomeLight` | HomeLight referral platform | homelight | Medium-high |
| `Referral` | Agent or personal referral | agent-referral | High |
| `CSV Import` | Batch import | No auto-sequence. Ben approval required. | Unscored |
| `<unspecified>` | Source not captured | No auto-sequence. Flag for classification. | Unknown |

### Legacy / Low-Volume Sources

| Source String | Description | Agent Behavior |
|---|---|---|
| `Homesnap` | Defunct portal (merged into Realtor.com) | No active sequence. Treat as portal-buyer/seller by type if re-engaged. |
| `AgentMachine` | Legacy lead service | No active sequence. Flag for Ben. |
| `iHomeFinder` | Legacy IDX portal | No active sequence. |
| `FastExpert` | Agent matching platform | No active sequence. Flag for Ben. |
| `FB_Lafayette` / `FB_Moraga` | Facebook ad campaigns by city | No active sequence. Flag for Ben. |
| `Google` / `googsell` | Google ad campaigns | No active sequence. Flag for Ben. |
| `TP Websites` | Third-party website lead | No active sequence. Flag for Ben. |

### Sources Not Yet Appearing (Expected from New Programs)

| Source String | Expected From | Sequence |
|---|---|---|
| `BrightWork Website` | Landing page forms | Varies by tag |
| `Final Offer` | finaloffer.brightworkrealty.com | final-offer |
| `Open House` | ShowingTime / manual | No sequence — direct Ben action |

---

## CUSTOM FIELDS

| Field Name | API Key | Type | Notes |
|---|---|---|---|
| Zip Code Origin | `customZipCodeOrigin` | string | Migrated from zip code tags June 2026. Maps to local-market-context.md. Agent reads this for geographic routing. |

Note: Additional custom fields likely exist in the account but were
not exposed in the current API pull. This section should be updated
after a full custom fields endpoint query.

---

## AGENT WRITE RULES (SUMMARY)

Permitted writes to FUB contact records:
- Add tags with `mergeTags: true` — never replace tag arrays
- Update `stage` — always log previous stage in activity note
- Log activity notes
- Update `customZipCodeOrigin` if null
- Enroll in sequence after Ben Telegram approval on first touch

Prohibited writes:
- Delete contacts
- Remove tags without explicit Ben instruction
- Write to contacts where `assignedTo` is not "Ben Olsen"
- Overwrite `stage` without logging previous value

See source-of-truth-matrix.md for full write permission rules.
