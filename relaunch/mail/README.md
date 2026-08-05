# COS Local Expired Packets LOB

Python CLI that filters expired-listing property rows, matches each to a local PDF packet, and mails eligible packets as Lob Print & Mail letters for BrightWork Realty’s relaunch campaign.

Given a properties CSV and a folder of packet PDFs, the tool:

1. **Matches** each row to a PDF by filename (`{city}_{street_slug}.pdf`)
2. **Holds back** rows that are Pending, entity-owned (company with no individual owner first name), or missing a matching PDF
3. **Builds** recipient name and mail address (preferring `public.mailAddress.*`, falling back to the property address)
4. **Sends** eligible packets via the Lob Letters API (color, single-sided, with a campaign QR code)

Run modes support dry-run filtering, a single sandbox send, or a full production send. Each run writes a timestamped CSV log under `logs/`.

## File tree

```
.
??? mailer.py                 # CLI entrypoint
??? requirements.txt
??? .env.example              # Environment variable template
??? .gitignore
??? properties0626.csv        # Input property / listing export
??? Packets0626/              # Local PDF packets to mail
?   ??? Lafayette_23_Timber_Ln.pdf
?   ??? Moraga_45_La_Salle_Dr.pdf
?   ??? Orinda_2_Normandy_Lane.pdf
?   ??? ...                   # additional {city}_{street}.pdf files
??? logs/                     # Timestamped run-log_*.csv outputs
??? relaunch_mailer/
    ??? __init__.py
    ??? config.py             # Settings from env; Lob QR config
    ??? filter.py             # Hold-back rules & recipient construction
    ??? pdf_match.py          # Deterministic PDF filename matching
    ??? lob_client.py         # Lob Letters API client
    ??? run_log.py            # Run-log CSV writer
```

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# Edit .env: LOB_API_KEY, CSV_PATH, PDF_DIR, sender address, LOG_DIR
```

## Usage

```bash
python mailer.py --filter-only      # Classify rows; write run log; no Lob calls
python mailer.py --investigate      # PDF inventory + filter summary
python mailer.py --sandbox-test     # Send one SENT row with a test_ Lob key
python mailer.py --send-all         # Send all SENT rows (live_ key required)
```

## Hold-back actions

| Action | Meaning |
|--------|---------|
| `SENT` | Eligible to mail (individual owner + matched PDF + not Pending) |
| `HELD_PENDING` | `listing.customStatus` is Pending |
| `HELD_ENTITY` | No owner first name; company name present |
| `HELD_UNMATCHED` | No PDF matched for the expected filename |
