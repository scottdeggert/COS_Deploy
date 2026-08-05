# BrightWork Property Report Generator
## Setup, Configuration, and Run Instructions

---

### FOLDER STRUCTURE
```
brightwork_reports/
├── config/
│   ├── __init__.py
│   └── market_benchmarks.py   ← EDIT THIS between batch runs
├── assets/
│   ├── logo.jpg
│   ├── signature.png
│   ├── ben-olsen.png
│   ├── ben_profile.html       ← source for Ben bio one-sheet
│   ├── ben_profile.pdf        ← rendered from HTML (auto-refreshed)
│   ├── BrightWork_Smartway_Onesheet.pdf
│   ├── offMarket_onesheet.pdf
│   └── fonts/                 ← optional, see Custom Fonts below
├── output/                    ← PDFs appear here (auto-created)
│   └── staging/               ← intermediate files, ignore
├── .env                       ← ANTHROPIC_API_KEY (preferred)
├── properties.csv             ← swap in new batch before each run
├── system_prompt.txt          ← edit only for messaging strategy changes
├── batch_generate.py          ← do not edit
├── generate_report.py         ← do not edit
└── requirements.txt
```

One-sheet filenames are resolved with fallbacks (`smartway_onesheet.pdf` / `offmarket_onesheet.pdf` still work if present).

---

### BETWEEN-BATCH WORKFLOW

This is the only process you follow for each new mailing batch:

1. Drop the new `properties.csv` into the project root.
2. Open `config/market_benchmarks.py`.
3. Update `BATCH_DATE` to the current month and year (e.g. `'August 2026'`).
4. Review benchmark tiers. If market conditions have shifted materially, update the relevant ZIP or city ranges. Benchmarks should be refreshed quarterly using Redfin zip-level data.
5. Run the generator (see Running the Script below).
6. Review any preflight-flagged properties before confirming the run.
7. Hand the `output/` folder (not `staging/`) to the print vendor.

That is the complete operational process. You should not need to touch `batch_generate.py` or `generate_report.py` between runs.

Rows marked **Do Not Print** in the CSV status columns are excluded automatically.

---

### ONE-TIME SETUP

**1. Check Python version**
```
python3 --version
```
Requires Python 3.9 or later.

**2. Install packages**
```
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

**3. Set your Anthropic API key**

Preferred — create `.env` in the project root:
```
ANTHROPIC_API_KEY=sk-ant-your-key-here
```

Or export in your shell:
```
export ANTHROPIC_API_KEY=sk-ant-your-key-here
```

**4. Chrome (for Ben bio one-sheet)**

If you edit `assets/ben_profile.html`, Google Chrome (or Chromium) must be installed so the script can re-render `ben_profile.pdf`. If Chrome is unavailable, a previously rendered `ben_profile.pdf` is reused when present.

---

### RUNNING THE SCRIPT

**Standard run (all properties):**
```
python3 batch_generate.py
```

**Test with one property (no API cost):**
```
python3 batch_generate.py --skip-api --test
```

**Test a specific property:**
```
python3 batch_generate.py --address "22 Williams"
```

**Limit batch size:**
```
python3 batch_generate.py --limit 5
```

**Layout test without API calls:**
```
python3 batch_generate.py --skip-api
```

---

### PREFLIGHT CHECK

Before any API calls are made, the script runs a preflight check on every property in the CSV. It flags:

- Properties in known gated communities (Rossmoor, Moraga Country Club, Orinda Country Club) that may need benchmark or strategy adjustments.
- Townhouses and condos, where SFR benchmark tiers do not apply.
- Rural or large-acreage parcels that are likely not standard expired listing campaign candidates.

The preflight prints a summary and asks you to confirm before proceeding. You can include flagged properties, skip them, or abort the run entirely. Preflight is skipped when using `--skip-api`.

---

### ADDING A NEW MARKET

When Ben expands to a new city or ZIP:

1. Add the new ZIP or city entry to `BENCHMARKS` in `config/market_benchmarks.py`.
2. If the market includes a notable gated or age-restricted community, add a keyword entry to `COMMUNITY_FLAGS`.
3. No other files need to change.

---

### BENCHMARKS REFERENCE

Benchmarks are keyed by ZIP code (preferred) or city name. ZIP-level keys take priority, which allows markets like Walnut Creek (four distinct ZIPs with different price behaviors) to be calibrated independently.

Current markets covered: Moraga, Orinda, Lafayette, Walnut Creek (94595/96/97/98), Alamo, Pleasant Hill.

Sources: Redfin zip-level data, Lamorinda Weekly quarterly reports, Loqol/Movoto. Refresh quarterly.

---

### OUTPUT

PDFs appear in `output/`, named by city and address:
```
Walnut_Creek_1413_Goleta_Ct.pdf
Moraga_152_Tharp_Dr.pdf
```

Each packet is 11 pages:

- Page 1: Cover letter from Ben (date pulled from `BATCH_DATE`)
- Page 2: Property cover page
- Pages 3–7: Report body (executive summary, friction points, positioning, quiet listing, why BrightWork)
- Page 8: Disclaimer
- Page 9: Ben Olsen bio one-sheet
- Page 10: Smart Way one-sheet
- Page 11: Off-Market one-sheet

`output/staging/` holds intermediate report PDFs and Claude JSON content. Ignore these when handing off to print.

---

### OPTIONAL: CUSTOM FONTS

For Montserrat and Open Sans (BrightWork brand fonts):

1. Download from Google Fonts:
   - [Montserrat](https://fonts.google.com/specimen/Montserrat) (Bold)
   - [Open Sans](https://fonts.google.com/specimen/Open+Sans) (Regular, Bold, Italic)
2. Place these files in `assets/fonts/`:
   - `Montserrat-Bold.ttf`
   - `OpenSans-Regular.ttf`
   - `OpenSans-Bold.ttf`
   - `OpenSans-Italic.ttf`

The script loads them automatically. Without them, it falls back to Helvetica.

---

### COST ESTIMATE

Each property requires one Claude API call (~3,000 input + ~1,500 output tokens).
Estimated cost: ~$0.01–0.02 per property. A 20-property batch runs under $0.40.
Run time: approximately 3–5 minutes for 20 properties.

---

### TROUBLESHOOTING

**"Missing required files" error:** Check that `properties.csv`, `system_prompt.txt`, and `assets/logo.jpg` exist.

**"ANTHROPIC_API_KEY not set" error:** Add the key to `.env` in the project root, or run `export ANTHROPIC_API_KEY=sk-ant-...` and retry.

**A property fails with JSON parse error:** Re-run just that property:
```
python3 batch_generate.py --address "partial address"
```

**Font looks like Helvetica:** Custom fonts not installed. See Optional: Custom Fonts above.

**Ben bio page missing or stale:** Ensure `assets/ben_profile.html` exists and Chrome/Chromium is installed so `ben_profile.pdf` can be regenerated. A cached PDF is used if Chrome is unavailable.
