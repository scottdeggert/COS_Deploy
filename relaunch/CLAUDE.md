# relaunch/ — Context for Claude Code and Cursor sessions

This file is auto-loaded by Claude Code on startup and should be treated as
equivalent in authority to CLAUDE.md at the repo root. If something here
conflicts with a general COS_Deploy rule, this file wins for anything under
`relaunch/`.

Read this before touching pull/, scrub/, generate/, or mail/. It exists
because every rule below was learned by something going wrong once, and the
cost of relearning it is a batch that either mails the wrong person or fails
to mail the right one.

---

## What this pipeline does

Pulls expired residential listings (RealEstateAPI) → filters out anything
ineligible (pending, entity-owned, suppressed) → generates a personalized
PDF packet per property (OpenRouter/Sonnet for copy) → a human reviews the
PDFs → on approval, sends via Lob Print & Mail → tags each recipient in FUB
as a dormant contact for future attribution.

One human checkpoint exists, deliberately, after generation and before send.
It is not there because the pipeline is incomplete. Ben is intentionally
kept out of this loop entirely — the whole point of the product is that he
finds out about interest via a phone ringing, not by reviewing address
lists. The reviewer's job is voice/pagination quality and one thing more
important than either: catching properties that shouldn't be in the batch
at all. Do not propose removing or automating past this checkpoint.

---

## Non-negotiable: what counts as "no individual owner"

`is_true_entity()` in `scrub/entity_detection.py` is the single source of
truth for "is there a person to address this letter to," and both
`scrub_batch.py`'s hold-back logic and `generate/batch_generate.py`'s
salutation logic call it. They must never diverge again — they did once,
briefly, before this file existed, and it took a manual PDF review to catch
that a public sanitary district (Central Contra Costa Sanitary District,
name sitting in `owner1LastName` with `companyName` blank) almost went out
in a residential relaunch campaign.

**Trust language is never an entity signal.** `trust`, `living trust`,
`family trust`, `revocable`, `trustee` must never appear in the
institutional exclusion keyword list, under any circumstances, for any
reason that seems locally sensible at the time. A living/family trust is
how an individual holds title, not evidence that no individual exists.
Senior homeowners — this campaign's actual target demographic — hold title
this way constantly. The gate is: if `owner1FirstName` OR `owner2FirstName`
contains a real name, it is not an entity, full stop, regardless of what
else appears in any other field. Only when *no* individual first name
exists anywhere does the function check for institutional keywords (llc,
inc, corp, holdings, district, sanitary, authority, association, hoa,
municipal, bank, foundation, diocese, church — this list may grow, the
trust-family terms must never join it).

This is enforced at import time, not just documented: `entity_detection.py`
asserts none of `PROTECTED_OWNERSHIP_TERMS` overlap with
`institutional_keywords`, and the module fails to import if that assertion
ever fails. `tests/test_entity_detection.py` has permanent regression cases
(Maralyn Cantor, Maria Gerontides — both real trust-held individual
properties that must always resolve to a personal name) and must be run
before shipping any change to `entity_detection.py` or `scrub_batch.py`.

A fourth outcome exists and matters: no individual name AND no keyword
match is `HELD_AMBIGUOUS_OWNER`, not auto-approved and not auto-excluded.
It routes to the same human-review surface as FUB suppression flags. Don't
collapse this into a binary.

---

## Data quirks specific to REAPI's export (learned the hard way)

- Individual owner names live in `public.owner1FirstName` /
  `owner1LastName` and optionally `owner2FirstName` / `owner2LastName`.
  There is **no** `Current Owner` concatenated column in real exports —
  that was an artifact of an old manual scrub tool (Manus AI), now
  replaced. Don't reintroduce logic that expects it.
- `public.companyName` is not reliably where entity ownership shows up.
  It can also land in `owner1LastName` with `companyName` blank (see
  Sunnybrook above). Check all owner-name-shaped fields, not just the one
  that's usually populated.
- City casing is inconsistent between `listing.address.city` and
  `public.address.city` — REAPI has returned `"WALNUT CREEK"` for some
  rows and `"Walnut Creek"` for others in the same export. Benchmark
  lookups by city name in `market_benchmarks.py` are case-sensitive with no
  normalization; they currently work anyway because ZIP is checked first in
  the `or` chain (`BENCHMARKS.get(zip) or BENCHMARKS.get(city)`). This is
  fragile, not fixed — a market with no ZIP-keyed benchmark entries would
  hit the case-sensitivity bug directly. PDF filename matching in
  `pdf_match.py` / `build_pdf_index()` already lowercases both sides before
  comparing and is *not* fragile — that's the right pattern, the benchmark
  lookup should eventually match it.
- `data_state.json`'s per-client checkpoint (`"Ben": "2026-05-01"`) drives
  REAPI's `last_status_change_date_min` on the next pull. **Any real pull —
  sandbox key or not, REAPI has no sandbox mode — advances this checkpoint.**
  If a batch needs to be scrapped and re-pulled for the same window, reset
  this file manually first, or the re-run will ask REAPI for "what changed
  since the last (test) run" instead of the intended window.

---

## Credentials

`LOB_API_KEY` and all `SENDER_*` fields live **only** in `relaunch/.env`.
They must never be added to `/root/COS_Deploy/.env` (the root file
`cos-agent` loads). This was fixed once already — a payment-capable,
physical-mail-triggering credential sitting in a file the lead-response
agent's process also loads is a scope-creep risk nobody would ever decide
on purpose. If you find `LOB_API_KEY` in root `.env`, that's regression,
remove it.

`test_` vs `live_` key prefix is enforced in code (`send.py` refuses
`--send-all` on a `test_` key, refuses `--sandbox-test` on a `live_` key).
Do not work around this check. Do not check `/proc/<pid>/environ` to verify
a running process's environment — it reflects exec-time environment only,
not anything loaded via `load_dotenv()` after startup, and will give a
false pass. Verify credential isolation from the file contents and load
order, not from `/proc`.

---

## Lob API constraints learned from real 422s

- `to.name` must be ≤ 40 characters. Two-owner full names with middle
  names routinely exceed this. Fallback order in
  `mail/relaunch_mailer/filter.py`'s `build_recipient_name`: try shared
  last name form first ("Owner1First & Owner2First SharedLast"), fall back
  to owner1 only if surnames differ or it's still too long. Never
  mid-word-truncate.
- `qr_code.redirect_url`, `qr_code.width`, and `use_type` are all required;
  omitting any produces a 422, not a default.
- Inline base64 PDF content over ~10,000 characters of HTML representation
  fails; `file` must be a fetchable URL (currently
  `webhook.brightworkrealty.com/relaunch/batches/{id}/f/{token}.pdf`), not
  inline data.
- A 422 means **nothing was created** at Lob — safe to retry the same row
  after a fix, no duplicate risk. Confirm this by checking for an absent
  `letter_id` before assuming a retry is safe for any *other* kind of
  failure.

---

## The QR page number is not independent of packet layout

`generate/batch_generate.py` writes `qr_page` into
`batches/{batch_id}/manifest.json` as part of generation.
`mail/relaunch_mailer/lob_client.py` reads `pages` for the QR overlay from
that manifest, not a hardcoded constant. **Do not hardcode the QR page
number again.** It has drifted silently before — adding the Ben-bio
one-sheet once pushed the QR placeholder back a page with nothing catching
it until a much later audit. If you change page count or order anywhere in
the generated report (new section, reordered content, added static page),
confirm the manifest's `qr_page` still matches reality before the next
send, and prefer adding an assertion that fails loud on mismatch over
trusting it stayed in sync.

---

## Telegram callback routing

The approve-send card goes to `OPERATOR_TELEGRAM_CHAT_ID`, not Ben's chat.
`core/transport.py`'s primary callback gate (`cb_chat_id == configured_chat_id`)
is Ben-only and must stay that way for lead-alert callbacks — do not widen
it. `relaunch_send:{batch_id}` callbacks route through a narrow, explicit
exception scoped to `OPERATOR_TELEGRAM_CHAT_ID` specifically, added
alongside the primary gate, not by modifying it. If you add another
operator-facing callback type in future, follow this same narrow-exception
pattern rather than further widening the shared gate.

The send-approval flow acknowledges immediately (`answerCallbackQuery` +
edit message to "Sending...", button removed) and writes
`send_initiated_at` to `pipeline_state.json` atomically before the send
subprocess launches, so a second tap on the same batch is refused, not
re-executed. If you add a new send-triggering surface, it must check this
same guard.

---

## What "done" looks like for a batch — verification checklist

Before considering a batch closed:

- [ ] `properties.csv` row count == PDF count in `output/` == Telegram
      card's "ready to send" count. All three drift independently; check
      all three, not just one.
- [ ] FUB `mailer:expired-{batch_id}` tag count == actual successful Lob
      sends, not the attempted count. A partial batch (some rows 422) will
      have fewer FUB tags than PDFs — that's correct, not a bug, confirm
      the shortfall matches the failure list exactly.
- [ ] Any row a human manually flags during review (like Sunnybrook) is
      removed from `properties.csv` **and** `output/` **and**
      `review_map.json` **and** the Telegram card is regenerated to reflect
      the new count. Removing from one and not the others has happened
      before and produces a review card the reviewer's approval doesn't
      actually match.
- [ ] `pipeline_state.json`'s `send_initiated_at` is set only after a real
      send attempt, and `last_batch_status` reflects partial vs. complete
      accurately — it currently does not auto-update on partial completion,
      confirm manually if a batch has any failures.

---

## What's intentionally NOT automated, and why

- The Lob key swap from `test_` to `live_` is a manual `.env` edit, done as
  its own deliberate action, never bundled into approving a batch or fixing
  something else. This is the one action in the pipeline that turns
  "nothing can physically mail" into "this will physically mail." Treat it
  accordingly.
- The APPROVE SEND tap itself is not scriptable or simulatable by an agent.
  It is the actual human decision this whole review step exists to capture.
  If you're tempted to build a way to trigger it programmatically for
  testing, use `mail/send.py --addresses` with an explicit row list instead
  — that path exists specifically so testing and one-off resends don't
  require faking the approval gate.
- The monthly cron trigger runs pull → scrub → generate → notify. It stops
  there. It does not run send under any circumstance. If this ever changes,
  that's a product decision with real stakes, not a refactor.

---

## Where to find business/strategy context

Brand voice, pricing, target-audience reasoning, and the FUB tag taxonomy
this pipeline's writeback depends on live in the BrightWork Chief of Staff
Claude.ai project, not in this repo. This file covers engineering
constraints only — how the data behaves, what the code must never do, what
already broke once. If a change here seems to require a business judgment
call (should this campaign expand to a new market, should the copy tone
change, is a given hold-back category worth a new keyword), that's a
conversation to have there, not a default to pick here.