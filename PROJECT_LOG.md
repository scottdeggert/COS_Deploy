# PROJECT_LOG.md
# COS_Deploy — running history, open items, and roadmap

---

## HOW TO USE THIS FILE

CLAUDE.md is architecture and rules — it should change rarely, only when
someone deliberately changes how the system is built. This file is
everything else: what's currently blocked, what shipped, what broke and
why, what's been discussed but not started. It changes constantly and is
expected to.

When you ship something, fix an incident, or make a decision worth
remembering, add a dated entry under the relevant section. When something
here gets resolved, don't delete the entry — mark it resolved and leave it,
the history of why something was a problem is often as useful as knowing
it isn't anymore.

Tags used below: **SHIPPED**, **OPEN**, **RESOLVED**, **INCIDENT**,
**DECISION**, **PARKED**.

---

## OPEN ITEMS — check before assuming anything below is still accurate

- **OPEN — Realtor suppression tag not enforced.** Identified July 23,
  2026, when a competing realtor tagged `Realtor` generated a lead alert
  draft and a "fallback sequence eligible" note, and appeared in the
  client's morning digest. `Unsubscribed`/`Bounced`/`#NeverMail` are
  enforced correctly at both the sequence-enrollment and digest-surfacing
  paths; `Realtor` is not enforced at either. Status as of last check:
  unresolved.

- **OPEN — Agent has no confirmed name.** Blocked on Ben Olsen's input.
  EA identity work (see below) is blocked on this decision.

- **OPEN — `relaunch/` tenant separation debt.** `SENDER_NAME`/office
  address live in `relaunch/.env`, `ACTIVE_CLIENT = "Ben"` is hardcoded in
  the REAPI pull config. Neither lives under `clients/ben-olsen/` the way
  the rest of the system requires. Fine for single-tenant. Must be resolved
  before a second client's direct mail pipeline can be onboarded without
  forking `relaunch/` wholesale.

- **OPEN — No staging environment.** All testing runs against the same
  Telegram token and process serving Ben live. Flagged as structural risk;
  not yet built. `COS_DIAGNOSTIC_MODE=1` and isolated test SQLite paths
  provide partial mitigation for specific script types, not a general
  staging environment.

- **OPEN — `fub_full_extract.py` baseline assessment.** Was mid-run on the
  Mac Mini with events, notes, calls, and tasks incomplete; pagination cap
  needs patching before re-running.

- **OPEN — `relaunch/` review-index basic auth credential.** The password
  protecting the batch-review URL was printed into a chat transcript when
  first generated (Aug 4-5, 2026 session) and has not been rotated since.
  Low urgency, real exposure. Rotate before the pipeline runs unattended
  on a monthly cron.

- **OPEN — `relaunch/review_map.json` orphan entries.** Manually-removed
  batch rows (e.g. a property pulled from a batch post-scrub) can leave a
  stale token in `review_map.json` pointing at a deleted file. Currently
  harmless — the review index filters by file existence — but should be
  cleaned up as part of batch closeout rather than left to accumulate.

- **UNCONFIRMED — watchdog triple-alert deduplication.** Noted as a bug in
  a prior session (late June). Not clearly the same issue as the
  ProxyError/orphaned-subprocess incident below, which was fixed July 3.
  Whether this is a separate, still-open bug or was resolved alongside that
  fix is not confirmed. Check before assuming either way.

---

## RESOLVED (kept for history)

- **RESOLVED — PDT/PST zoneinfo fix.** Was flagged June 28 as parked work
  (hardcoded UTC-7 offset in scheduler and appointments, needed to move to
  `zoneinfo` before the November DST change). Current CLAUDE.md's Scheduler
  Rules section confirms `zoneinfo America/Los_Angeles` is now the standard
  and static offsets are explicitly prohibited. Appears shipped; if you
  find a hardcoded offset anywhere, that's a regression, not a
  not-yet-started item.

---

## PARKED — discussed, not started, not currently scheduled

Ported from a June 28-29, 2026 session at the close of the layered-
architecture refactor. Confirm current relevance before starting any of
these — six weeks is enough time for priorities to have shifted.

- **Rental sequence content.** Landlord rep → capture non-signing tenants →
  1-month follow-up → 9-month buyer nurture. Author and push to FUB.
- **Post-meeting follow-up ping.** 2 hours after an appointment ends,
  "how did it go?" → Ben replies → agent logs a FUB note.
- **Communication memory write path.** `communication_prefs.json` stub
  exists (read path only, confirmed still true as of current CLAUDE.md's
  not-built list). Needs Haiku to classify a `preference_update` intent
  and a write path to persist it.
- **Contact address/field lookup.** Discrete lookup intent, separate from
  a full brief — if Ben asks for an address, he should get an address, not
  a brief.
- **EA email identity (Alex / Resend).** This is the feature Scott raised
  wanting to build next (Aug 5, 2026 session) — a unique email identity
  for the assistant to perform functions beyond Telegram. Blocked on the
  agent name decision above. When this starts, it should get the same
  treatment `relaunch/` got: a short scoping conversation, then a
  purpose-built `CLAUDE.md` in whatever directory it lives in, not a
  retrofit of this file.

---

## INCIDENT HISTORY

### 2026-08-12 — Bare-address CMA requests misfiled into entity_address

Live demo: five consecutive Telegram CMA attempts with valid street
addresses (e.g. "722 Augusta Drive, Moraga, CA", "Create a cma for 49
corliss drive...") all returned "I need a street address". Logs showed
`entity_len=0 entity_address_len=N` — Haiku put the address in
`entity_address` and left `entity` empty. `handlers/cma.py` address-only
path only reads `entity`, so it failed even though the address was
extracted.

**Root cause:** Pattern-3 router prompt already stated address-only goes
in `entity`, but the JSON schema label was
`"entity_address": "property address or null"`. That label outweighed the
prose rules; Haiku treated any property address as belonging in
`entity_address`. Same prompt had worked on Aug 1 for some phrasings
(non-deterministic), then failed consistently on Aug 12.

**Fix:** (1) Tighten `core/router.py` cma_request rules with an explicit
hard rule, concrete examples for address-only / contact-only / pattern 3,
and JSON schema labels that say `entity_address` is only for a separate
address when `entity` is already a contact. (2) Defensive fallback in
`handlers/cma.py`: if `entity` is empty but `entity_address` looks like a
street address, treat it as Phase 1 address-only rather than returning
MISSING_ADDRESS. Pattern-3 dual-entity path unchanged (requires non-empty
`entity`).

### 2026-07-03 — ProxyError during watchdog restart bursts

If FUB or OpenRouter calls fail with "ProxyError... Tunnel connection
failed: 403" and no proxy is configured anywhere (env vars, supervisor
config, `/etc/environment`, codebase grep all confirmed clean at the time),
check for a watchdog supervisor burst in `cos_agent.log` around the same
timestamp — rapid start/failure/start cycles, less than 1 second apart.

**Root cause:** orphaned `tools.watchdog` subprocesses survived
`core.main` restarts because SIGTERM doesn't propagate to reparented
children. The orphan held `watchdog.lock`, causing new supervisor threads
to spawn/fail/respawn in a tight loop. This loop correlated 100% with the
two observed ProxyError incidents, though the exact mechanism (likely fd/
socket exhaustion from rapid subprocess forking, misreported by urllib3 as
a proxy error) was not directly confirmed.

**Fix:** `_terminate_stale_watchdog_processes()` in `core/main.py` now
SIGTERMs any orphaned `tools.watchdog` process before each spawn attempt,
plus a 2-second respawn delay. If ProxyError recurs, check first whether
this fix regressed or a new orphan-causing path exists before assuming
it's a real proxy/network issue.

### 2026-07-23 — Unexplained morning_digest fire outside its window

At 18:13:33 UTC (11:13 Pacific), `core/scheduler.py::_tick` logged a
`morning_digest` start and success 4ms apart with empty detail. No FUB
sub-logs, no Telegram send, no state write. The committed window gate at
that time required `hour == 8` and could not have matched hour 11. The
running process had been up since the prior day, so a file saved to disk
seconds before the event could not have altered its in-memory code.

**Cause: UNRESOLVED.** If a scheduled job fires outside its configured
window again, treat this as a recurrence and investigate the loaded code
of the *running* process, not the code on disk — they were confirmed to
have diverged at the time of this incident.

### 2026-07-03 to 2026-07-22 — 18-day morning digest outage, undetected

A skip path in the scheduler declined to run the digest and logged
nothing, for 18 days, with no alert. This is the direct cause of the
"silent skips are prohibited" and "absence monitoring is required" rules
now in CLAUDE.md's Monitoring Rules section. Do not weaken either rule to
reduce log verbosity — this is what verbose logging on skip paths is for.

### 2026-07-23 — Hollow digest run falsely cleared the deadman's switch

A 4ms digest run logged `success` without actually sending anything, and
the deadman's switch accepted the log line as proof of work and cleared
itself. This is the direct cause of the "monitoring must verify effect,
not log lines" rule — the deadman now reads
`last_morning_digest_date` from `logs/scheduler_state.json`, a value only
the real send path writes, rather than trusting a success log line.

### 2026-08-04/05 — Relaunch pipeline: entity detection near-miss

During the first live catch-up batch, a property later identified as
Central Contra Costa Sanitary District (a public wastewater utility, not a
residential owner) passed the scrub step's entity check and was one
Telegram tap away from being mailed a "why didn't your home sold" relaunch
letter. It was caught by a human reviewer noticing an odd salutation, not
by the system. Root cause: the entity name landed in
`public.owner1LastName` with `companyName` blank, a data shape the
scrub check (blank `owner1FirstName` AND non-blank `companyName`) didn't
cover. Fixed same day: `scrub/entity_detection.py` now checks all owner-
name-shaped fields for institutional keywords, gated behind "does any
individual first name exist anywhere" so the fix could not accidentally
exclude real trust-held individual properties (a serious near-miss on its
own — the first draft of the fix would have excluded any property with
"trust" in an owner field, which would have wrongly caught the exact senior
homeowner demographic this campaign targets). See `relaunch/CLAUDE.md` for
the permanent rule this produced.

---

## SHIPPED

### 2026-06-28 — Layered architecture refactor

Decomposed the monolithic `bot.py` (which mixed transport, routing,
scheduling, and business logic in one file) into `app/`, `core/`,
`handlers/`, `services/`, `tools/` with Pydantic contracts between layers
and a centralized FUB client with retry logic. Ran autonomously via Claude
Code in ~10 minutes for phases 1-3; live deployment ran manually in ~45
minutes with zero rollbacks. Tagged `post-refactor-june28`
(commit `0b09b4e`); rollback tag `pre-refactor-june28` (commit `4f4d826`)
still exists. Old files moved to `_retired/` on July 23 after 48 hours of
confirmed clean runtime, not deleted.

### 2026-08-05 — Relaunch (expired listings direct mail) pipeline live

Consolidated three previously-standalone Mac Mini repos (RealEstateAPI
pull, PDF packet generation, Lob mailer) into `relaunch/` on the droplet,
with a single human checkpoint after generation and before send. First
live batch: 21 properties pulled (2026-05-01 through 2026-08-04 window),
5 held back at scrub (3 pending, 2 entity — see incident above), 16
generated and reviewed, all 16 sent live via Lob across two passes (13 on
first approval, 3 more after fixing a `to.name` 40-character Lob
validation limit that had rejected them), plus one physical sample mailed
to Ben's office so he can see the actual printed artifact before the next
batch. All 16 real recipients tagged in FUB
(`mailer:expired-2026-08`, `source:direct-mail`, `expired-listing`) as
dormant contacts for future attribution.

Cron trigger (monthly, 5th of the month) is built but **not yet enabled**
— held back deliberately until one full cycle ran clean end to end, which
it now has. Enabling it is a decision to make on purpose, not a leftover
task to just check off.

This entry is also the first real use of this log file, replacing
narrative content that used to live directly inside `CLAUDE.md`
("Known Failure Pattern" sections, an inline "OPEN" note on the suppression
tag rule) — moved here on the same day for the reasons above.