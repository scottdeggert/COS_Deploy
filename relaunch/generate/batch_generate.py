"""
batch_generate.py
BrightWork Realty Advocates — Batch Report Generator

Reads properties.csv, calls the Claude API once per property to generate
personalized content, then produces a complete PDF packet for each one.

Final output: one PDF per property in ./output/
Each PDF is 11 pages:
  Pages 1-8:  Generated report (letter, cover, body, disclaimer)
  Page 9:     Ben Olsen bio one-sheet (static)
  Page 10:    Smart Way one-sheet (static)
  Page 11:    Off-Market one-sheet (static)

QR code for Lob is placed on the disclaimer page (page 8). That page number
is written to batches/{batch_id}/manifest.json as qr_page.

Setup (one time):
  pip install reportlab pypdf pillow requests
  OPENROUTER_API_KEY must be set in the COS_Deploy/.env (via app.config)

Run:
  python batch_generate.py

Options:
  python batch_generate.py --test          # Generate only the first property
  python batch_generate.py --address "22 Williams"  # Generate one specific property
  python batch_generate.py --skip-api      # Use cached content (for PDF layout testing)
"""

import argparse
import csv
import json
import logging
import os
import re
import subprocess
import sys
import time
from pathlib import Path

import requests
from pypdf import PdfReader, PdfWriter

from generate_report import generate_report

# ─────────────────────────────────────────────────────────────────────────────
# CONFIGURATION — adjust paths here if your folder layout differs
# ─────────────────────────────────────────────────────────────────────────────
BASE_DIR        = Path(__file__).resolve().parent
RELAUNCH_ROOT   = BASE_DIR.parent
REPO_ROOT       = RELAUNCH_ROOT.parent
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(RELAUNCH_ROOT))
from app.config import OPENROUTER_API_KEY, OPENROUTER_URL, SONNET_MODEL
from config.market_benchmarks import BENCHMARKS, COMMUNITY_FLAGS, PROPERTY_TYPE_FLAGS, BATCH_DATE
from relaunch.scrub.entity_detection import is_true_entity

ENV_PATH        = REPO_ROOT / '.env'
ASSETS_DIR      = RELAUNCH_ROOT / 'assets'
OUTPUT_DIR      = BASE_DIR / 'output'
SYSTEM_PROMPT_PATH = BASE_DIR / 'system_prompt.txt'
CSV_PATH        = BASE_DIR / 'properties.csv'
# Ceiling for the report JSON payload. Cost estimate is ~1,500 output tokens
# typical; the original call site used 4096 so the full schema can finish.
REPORT_MAX_TOKENS = 4096
# Disclaimer is the last page of the generated report block (pages 1-8).
QR_PAGE = 8

def _first_existing_asset(*names):
    """Return the first asset filename that exists on disk."""
    for name in names:
        path = ASSETS_DIR / name
        if path.exists():
            return path
    return ASSETS_DIR / names[0]

SMARTWAY_PDF    = _first_existing_asset('BrightWork_Smartway_Onesheet.pdf', 'smartway_onesheet.pdf')
OFFMARKET_PDF   = _first_existing_asset('offMarket_onesheet.pdf', 'offmarket_onesheet.pdf')
BEN_PROFILE_HTML = ASSETS_DIR / 'ben_profile.html'
BEN_PROFILE_PDF  = ASSETS_DIR / 'ben_profile.pdf'

CHROME_PATHS = [
    Path('/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'),
    Path('/Applications/Chromium.app/Contents/MacOS/Chromium'),
    Path('/Applications/Google Chrome Canary.app/Contents/MacOS/Google Chrome Canary'),
]


def _load_env_file():
    """Load variables from project-root .env (does not override existing env)."""
    if not ENV_PATH.exists():
        return
    for raw_line in ENV_PATH.read_text(encoding='utf-8').splitlines():
        line = raw_line.strip()
        if not line or line.startswith('#'):
            continue
        if line.startswith('export '):
            line = line[7:].strip()
        if '=' not in line:
            continue
        key, _, value = line.partition('=')
        key = key.strip()
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in ('"', "'"):
            value = value[1:-1]
        if key and key not in os.environ:
            os.environ[key] = value

def _is_do_not_print(row):
    """Returns True if the CSV row is flagged Do Not Print."""
    for col in ('Status Flag', 'Status', 'status_flag'):
        flag = (row.get(col) or '').strip()
        if flag and 'do not print' in flag.lower():
            return True
    return False


# ─────────────────────────────────────────────────────────────────────────────
# CSV LOADING AND PROPERTY ENRICHMENT
# ─────────────────────────────────────────────────────────────────────────────

# Column name aliases — handles curated CSVs and REAPI MLSSearch exports
COL_ALIASES = {
    'address':     [
        'Address', 'Full Address', 'address',
        'listing.address.unparsedAddress', 'public.address.address',
    ],
    'city':        ['City', 'city', 'listing.address.city', 'public.address.city'],
    'beds':        [
        'Beds', 'Bedrooms', 'beds',
        'listing.property.bedroomsTotal', 'public.bedrooms',
    ],
    'baths':       [
        'Baths', 'Bathrooms', 'baths',
        'listing.property.bathroomsTotal', 'public.bathrooms',
    ],
    'sqft':        [
        'Sq Ft', 'Square Footage', 'sqft', 'Sq. Ft.',
        'listing.property.livingArea', 'public.squareFeet',
    ],
    'year_built':  [
        'Year Built', 'year_built',
        'listing.property.yearBuilt', 'public.yearBuilt',
    ],
    'lot_size':    [
        'Lot Size', 'lot_size',
        'listing.property.lotSizeSquareFeet', 'public.lotSquareFeet',
    ],
    'taxes':       ['Annual Taxes', 'Property Tax', 'taxes', 'public.taxAmount'],
    'hoa':         ['HOA', 'hoa', 'listing.property.associationFee'],
    'owner':       ['Current Owner', 'Owner Information', 'owner'],
    'list_price':  [
        'Last List Price', 'List Price', 'Original List Price (Dec 2025)', 'list_price',
        'listing.leadTypes.mlsListingPrice', 'listing.listPriceLow',
    ],
    'list_date':   ['Last List Date', 'list_date', 'listing.leadTypes.mlsListingDate'],
    'dom':         [
        'Days on Market', 'DOM', 'dom', 'listing.leadTypes.mlsDaysOnMarket',
    ],
    'description': [
        'Full MLS Listing Description', 'Listing Description', 'description',
        'listing.publicRemarks',
    ],
    'features':    ['Special / Standout Features', 'features'],
    'renovations': ['Renovations & Upgrades', 'renovations'],
    'kitchen':     ['Kitchen Features', 'kitchen'],
    'outdoor':     ['Outdoor & Lot Features', 'outdoor'],
    'notes':       ['Additional Notes', 'notes'],
}


def _get(row, key):
    """Get a value from a CSV row using the column alias map."""
    for col in COL_ALIASES.get(key, [key]):
        if col not in row or row[col] is None:
            continue
        text = str(row[col]).strip()
        if text and text.lower() != 'nan':
            return text
    return ''


def _parse_price(price_str):
    """Convert '$2,500,000' → 2500000 (int). Returns 0 if unparseable."""
    if not price_str:
        return 0
    clean = re.sub(r'[^\d]', '', price_str)
    try:
        return int(clean)
    except ValueError:
        return 0


def _parse_sqft(sqft_str):
    """Convert '3,113' → 3113 (int). Returns 0 if unparseable."""
    if not sqft_str:
        return 0
    clean = re.sub(r'[^\d]', '', sqft_str)
    try:
        return int(clean)
    except ValueError:
        return 0


def _parse_hoa(hoa_str):
    """Convert '$73/mo' → 73 (int). Returns 0 if unparseable or N/A."""
    if not hoa_str or hoa_str.lower() in ('none', 'n/a', '—', '-', ''):
        return 0
    clean = re.sub(r'[^\d]', '', hoa_str.split('/')[0])
    try:
        return int(clean)
    except ValueError:
        return 0


def _extract_zip(address):
    match = re.search(r'\b9\d{4}\b', address)
    return match.group(0) if match else '94556'


def _cell(row, *keys):
    """Return the first non-empty string value for any of the given row keys."""
    for key in keys:
        value = row.get(key)
        if value is None:
            continue
        text = str(value).strip()
        if text:
            return text
    return ''


def _owner_salutation(row):
    """
    Build a letter salutation from REAPI owner fields on the CSV row.

    Uses is_true_entity() for institutional detection. Individual first names
    on owner1 or owner2 produce a personal salutation; true entities fall back
    to 'Dear Homeowner,'.
    """
    entity = is_true_entity(row)
    if entity is True:
        return 'Dear Homeowner,'

    if entity is False:
        first = _cell(row, 'public.owner1FirstName', 'owner1FirstName')
        if first:
            return f'Dear {first.title()},'
        owner2_first = _cell(row, 'public.owner2FirstName')
        if owner2_first:
            return f'Dear {owner2_first.title()},'

    return 'Dear Homeowner,'


def _owner_display(row):
    """Short display name for the cover page 'Prepared For' line."""
    entity = is_true_entity(row)
    if entity is True:
        return 'The Owners'

    first = _cell(row, 'public.owner1FirstName', 'owner1FirstName')
    last = _cell(row, 'public.owner1LastName', 'owner1LastName')
    owner2_first = _cell(row, 'public.owner2FirstName')

    if entity is False:
        if first:
            if last:
                return f'The {last.title()} Family'
            return f'{first.title()} Family'
        if owner2_first:
            owner2_last = _cell(row, 'public.owner2LastName')
            if owner2_last:
                return f'The {owner2_last.title()} Family'
            return f'{owner2_first.title()} Family'

    return 'The Owners'


def _city_benchmark_str(city, zip_code=None):
    """Return benchmark range string for use in system prompt context.
    Looks up by ZIP code first, falls back to city name."""
    tiers = BENCHMARKS.get(zip_code) or BENCHMARKS.get(city) or BENCHMARKS.get('Moraga')
    low  = min(v[0] for v in tiers.values())
    high = max(v[1] for v in tiers.values())
    tier_detail = '  |  '.join(f'{k}: ${v[0]}–${v[1]}/sqft' for k, v in tiers.items())
    return f'${low}–${high}/sqft range  ({tier_detail})'


def enrich_property(row):
    """
    Takes a raw CSV row dict and returns a fully enriched property dict
    ready to be passed to the Claude API and generate_report().
    """
    address   = _get(row, 'address')
    city      = _get(row, 'city')
    # If city column is blank, extract from address string
    if not city and address:
        parts = address.split(',')
        if len(parts) >= 2:
            city = parts[1].strip()
    list_price = _parse_price(_get(row, 'list_price'))
    sqft      = _parse_sqft(_get(row, 'sqft'))
    hoa_mo    = _parse_hoa(_get(row, 'hoa'))
    first = _cell(row, 'public.owner1FirstName', 'owner1FirstName')
    last = _cell(row, 'public.owner1LastName', 'owner1LastName')
    owner_raw = f'{first} {last}'.strip() or _get(row, 'owner')
    desc_raw  = _get(row, 'description')
    dom_raw   = _get(row, 'dom')
    zip_code  = _cell(row, 'listing.address.zipCode', 'public.address.zip') or _extract_zip(address)

    # Compute $/sqft
    price_per_sqft = round(list_price / sqft) if sqft > 0 and list_price > 0 else 0

    # DOM as integer
    dom = 0
    if dom_raw:
        m = re.search(r'\d+', dom_raw)
        dom = int(m.group(0)) if m else 0

    list_price_str = _get(row, 'list_price')
    if list_price and list_price_str and not list_price_str.startswith('$'):
        list_price_str = f'${list_price:,}'

    return {
        # Display fields
        'address':        address,
        'city':           city,
        'zip':            zip_code,
        'beds':           _get(row, 'beds'),
        'baths':          _get(row, 'baths'),
        'sqft':           sqft,
        'year_built':     _get(row, 'year_built'),
        'lot_size':       _get(row, 'lot_size'),
        'owner_raw':      owner_raw,
        'owner_display':  _owner_display(row),
        'salutation':     _owner_salutation(row),

        # Financial
        'list_price':     list_price,
        'list_price_str': list_price_str,
        'price_per_sqft': price_per_sqft,
        'hoa_monthly':    hoa_mo,
        'hoa_str':        _get(row, 'hoa') if hoa_mo > 0 else 'None',
        'taxes':          _get(row, 'taxes'),

        # Listing data
        'list_date':      _get(row, 'list_date'),
        'dom':            dom,
        'description':    desc_raw,
        'kitchen':        _get(row, 'kitchen'),
        'features':       _get(row, 'features'),
        'renovations':    _get(row, 'renovations'),
        'outdoor':        _get(row, 'outdoor'),
        'notes':          _get(row, 'notes'),

        # Analysis helpers
        'city_benchmark': _city_benchmark_str(city, zip_code=zip_code),
        'batch_date': BATCH_DATE,
        'property_type_raw': row.get('listing.property.propertySubType') or row.get('public.propertyType') or '',
        'lot_sqft_raw':      row.get('public.lotSquareFeet') or row.get('lot_size') or 0,
    }


def load_properties(csv_path):
    """
    Load and filter properties from CSV. Returns list of enriched dicts.

    Handles spreadsheets exported with multi-row headers (e.g. a title row
    followed by group headers before the actual column names). Detects the
    real header row by finding the first row that contains 'Address' or
    'address' in any cell.
    """
    with open(csv_path, newline='', encoding='utf-8') as f:
        raw = list(csv.reader(f))

    # Find the real header row
    header_idx = 0
    for i, row in enumerate(raw):
        if any('address' in str(cell).strip().lower() for cell in row):
            header_idx = i
            break

    headers = [h.strip() for h in raw[header_idx]]
    data_rows = []
    for raw_row in raw[header_idx + 1:]:
        if not any(cell.strip() for cell in raw_row):
            continue  # skip blank rows
        row = dict(zip(headers, raw_row))
        data_rows.append(row)

    properties = []
    for row in data_rows:
        address = _get(row, 'address')
        if not address:
            continue
        if _is_do_not_print(row):
            logging.info(f'Do Not Print: {address}')
            continue
        prop = enrich_property(row)
        properties.append(prop)
    return properties


def preflight_check(properties, auto_confirm=False):
    """
    Scans loaded properties for community flags and property type flags.
    Prints a summary and prompts operator to confirm before API calls begin.
    Returns the list of properties to process (operator may abort).
    """
    ready = []
    flagged = []

    for prop in properties:
        remarks = (prop.get('description') or '').lower()
        prop_type = (prop.get('property_type_raw') or '').lower()
        lot_sqft = prop.get('lot_sqft_raw') or 0
        flags = []

        # Community keyword check
        for keyword, note in COMMUNITY_FLAGS.items():
            if keyword.strip() in remarks:
                flags.append(note)
                break

        # Property type checks
        if any(t in prop_type for t in ('townhouse', 'condo', 'townhome')):
            flags.append('Townhouse/Condo — benchmarks and strategy language calibrated for SFR.')

        try:
            lot = int(str(lot_sqft).replace(',', ''))
        except (ValueError, TypeError):
            lot = 0

        is_rural = 'rural' in prop_type
        if is_rural or lot > 200000:
            flags.append('Rural Residence or lot > 4.5 acres — likely not standard SFR campaign.')

        if flags:
            flagged.append((prop['address'], flags))
        else:
            ready.append(prop)

    # Print summary
    total = len(properties)
    print()
    print(f'  {"─" * 52}')
    print(f'  PREFLIGHT CHECK — {total} properties loaded')
    print(f'  {"─" * 52}')
    print(f'  Ready to generate : {len(ready)}')
    if flagged:
        print(f'  Flagged for review: {len(flagged)}')
        for addr, notes in flagged:
            print(f'')
            print(f'    ! {addr}')
            for note in notes:
                print(f'      → {note}')
    print(f'  {"─" * 52}')
    print()

    if flagged:
        if auto_confirm or not sys.stdin.isatty():
            print('  Non-interactive/auto-confirm: including flagged properties.')
            return properties
        answer = input(f'  Generate packets for flagged properties too? [y/n/skip]: ').strip().lower()
        if answer == 'y':
            return properties   # include everything
        elif answer == 'skip':
            return ready        # exclude flagged
        else:
            print('  Aborted. Fix flagged properties and re-run.')
            sys.exit(0)

    return properties


# ─────────────────────────────────────────────────────────────────────────────
# CLAUDE API CONTENT GENERATION
# ─────────────────────────────────────────────────────────────────────────────

def load_system_prompt():
    with open(SYSTEM_PROMPT_PATH, 'r', encoding='utf-8') as f:
        return f.read()


def build_user_message(prop):
    """
    Builds the per-property user message that gets sent to Claude.
    Includes all available property data so Claude can generate
    property-specific content.
    """
    hoa_line = f"${prop['hoa_monthly']}/month" if prop['hoa_monthly'] > 0 else 'None'
    dom_line  = f"{prop['dom']} days" if prop['dom'] > 0 else 'Unknown'
    sqft_line = f"{prop['sqft']:,}" if prop['sqft'] > 0 else 'Unknown'
    price_line = f"${prop['list_price']:,}" if prop['list_price'] > 0 else (prop['list_price_str'] or 'Unknown')
    ppsf_line  = f"${prop['price_per_sqft']}/sqft" if prop['price_per_sqft'] > 0 else 'Unknown'

    return f"""Generate a complete property report for the following property.

PROPERTY DATA:
Address:          {prop['address']}
City:             {prop['city']}
Beds / Baths:     {prop['beds']} bed / {prop['baths']} bath
Square Footage:   {sqft_line}
Year Built:       {prop['year_built']}
Lot Size:         {prop['lot_size']}
List Price:       {price_line}
Price Per Sq Ft:  {ppsf_line}
Days on Market:   {dom_line}
HOA Monthly:      {hoa_line}
Annual Taxes:     {prop['taxes']}
List Date:        {prop['list_date']}
Owner (raw):      {prop['owner_raw']}

LISTING DESCRIPTION (from MLS):
{prop['description'] or 'Not available.'}

STANDOUT FEATURES:
{prop['features'] or 'Not specified.'}

KITCHEN:
{prop['kitchen'] or 'Not specified.'}

OUTDOOR / LOT:
{prop['outdoor'] or 'Not specified.'}

RENOVATIONS / UPGRADES:
{prop['renovations'] or 'Not specified.'}

ADDITIONAL NOTES:
{prop['notes'] or 'None.'}

CITY BENCHMARK ($/sqft):
{prop['city_benchmark']}

SALUTATION TO USE IN LETTER:
{prop['salutation']}

INSTRUCTIONS:
1. Use the salutation above exactly as provided.
2. The letter paragraphs should reference specific features from the listing data above.
3. Select 3 friction points using the detection logic in the system prompt.
4. Customize every template with real numbers and real features — no placeholders.
5. The positioning table should use the city benchmark tier most appropriate for
   this property's condition and features.
6. All BrightWork contrasts must hint at one specific differentiator and stop.
7. Return only valid JSON per the schema. No preamble, no markdown fences.
"""


_MISSING_STATS_STRINGS = {
    '', '—', '-', 'n/a', 'na', 'none', 'unknown', 'not disclosed', 'position dependent',
}


def _is_missing_stat(value):
    if value is None:
        return True
    text = str(value).strip().lower()
    return text in _MISSING_STATS_STRINGS


def _normalize_exec_summary_stats(content, prop):
    """Force key stats to remain anchored to CSV-derived values when model placeholders appear."""
    if not isinstance(content, dict):
        return content

    exec_summary = content.setdefault('exec_summary', {})
    stats = exec_summary.setdefault('stats', {})

    list_price_text = prop.get('list_price_str') or (
        f"${prop['list_price']:,}" if prop.get('list_price') else '-'
    )
    ppsf_text = f"${prop['price_per_sqft']}/sqft" if prop.get('price_per_sqft') else '-'

    if _is_missing_stat(stats.get('list_price')):
        stats['list_price'] = list_price_text
    if _is_missing_stat(stats.get('price_per_sqft')):
        stats['price_per_sqft'] = ppsf_text
    if _is_missing_stat(stats.get('hoa')):
        stats['hoa'] = prop.get('hoa_str', 'None')

    return content


def _extract_first_number(text):
    """Return first numeric value found in text as int, else None."""
    if not isinstance(text, str):
        return None
    matches = re.findall(r'\d[\d,]*', text)
    if not matches:
        return None
    try:
        return int(matches[0].replace(',', ''))
    except ValueError:
        return None


def _extract_first_two_numbers(text):
    """Return first two numeric values in text as (low, high), else (None, None)."""
    if not isinstance(text, str):
        return (None, None)
    matches = re.findall(r'\d[\d,]*', text)
    if len(matches) < 2:
        return (None, None)
    try:
        first = int(matches[0].replace(',', ''))
        second = int(matches[1].replace(',', ''))
    except ValueError:
        return (None, None)
    return (min(first, second), max(first, second))


def _replace_positioning_terms(text, segment):
    """Adjust common range-position phrases to match computed segment."""
    if not isinstance(text, str):
        return text

    if segment == 'lower':
        replacements = [
            (r'\bupper-middle\b', 'lower-middle'),
            (r'\bupper end\b', 'lower end'),
            (r'\btop end\b', 'lower end'),
            (r'\bhigh end\b', 'lower end'),
            (r'\bupper tier\b', 'lower tier'),
            (r'\bupper range\b', 'lower range'),
            (r'\bupper\b(?=[ -](?:middle|tier|end|range))', 'lower'),
            (r'\bat the top of\b', 'at the lower end of'),
            (r'\bnear the top of\b', 'near the lower end of'),
        ]
    elif segment == 'middle':
        replacements = [
            (r'\bupper-middle\b', 'middle'),
            (r'\blower-middle\b', 'middle'),
            (r'\bupper end\b', 'middle'),
            (r'\blower end\b', 'middle'),
            (r'\btop end\b', 'middle'),
            (r'\bbottom end\b', 'middle'),
            (r'\bhigh end\b', 'middle'),
            (r'\blow end\b', 'middle'),
            (r'\bupper tier\b', 'middle tier'),
            (r'\blower tier\b', 'middle tier'),
        ]
    else:
        replacements = [
            (r'\blower-middle\b', 'upper-middle'),
            (r'\blower end\b', 'upper end'),
            (r'\bbottom end\b', 'upper end'),
            (r'\blow end\b', 'upper end'),
            (r'\blower tier\b', 'upper tier'),
            (r'\blower range\b', 'upper range'),
            (r'\blower\b(?=[ -](?:middle|tier|end|range))', 'upper'),
            (r'\bat the bottom of\b', 'at the upper end of'),
            (r'\bnear the bottom of\b', 'near the upper end of'),
        ]

    out = text
    for pattern, replacement in replacements:
        out = re.sub(pattern, replacement, out, flags=re.IGNORECASE)
    return out


def _normalize_positioning_verdict(content):
    """
    Anchor verdict range language to numeric reality using the table's
    'Price per Sq. Ft.' row when possible.
    """
    if not isinstance(content, dict):
        return content

    table = content.get('positioning_table')
    if not isinstance(table, dict):
        return content

    rows = table.get('rows', [])
    if not isinstance(rows, list):
        return content

    price_row = None
    for row in rows:
        metric = str(row.get('metric', '')).lower()
        if 'price per' in metric:
            price_row = row
            break
    if not isinstance(price_row, dict):
        return content

    subject_text = str(price_row.get('subject', '')).strip()
    market_text = str(price_row.get('market', '')).strip()
    subject_value = _extract_first_number(subject_text)
    low, high = _extract_first_two_numbers(market_text)

    if subject_value is None or low is None or high is None or high <= low:
        return content

    pct = (subject_value - low) / float(high - low)
    if pct <= 0.33:
        segment = 'lower'
        position_text = 'near the lower end'
    elif pct <= 0.66:
        segment = 'middle'
        position_text = 'in the middle'
    else:
        segment = 'upper'
        position_text = 'near the upper end'

    verdict = table.get('verdict', '')
    verdict = verdict if isinstance(verdict, str) else str(verdict)
    verdict = verdict.strip()
    verdict = _replace_positioning_terms(verdict, segment)

    lead = (
        f"At {subject_text} versus a benchmark range of ${low:,}-${high:,}/sqft, "
        f"this home sits {position_text} of that range."
    )
    table['verdict'] = f"{lead} {verdict}".strip()

    # Keep related premium-pricing forensic language aligned with the same range position.
    forensics = content.get('forensics', [])
    if isinstance(forensics, list):
        for friction in forensics:
            if not isinstance(friction, dict):
                continue
            title = str(friction.get('title', '')).lower()
            body = friction.get('body')
            if not isinstance(body, str):
                continue
            if 'premium not justified' in title or 'priced at the' in body.lower():
                friction['body'] = _replace_positioning_terms(body, segment)

    return content


def _sanitize_text(text):
    """Normalize typography we do not want in final output."""
    if not isinstance(text, str):
        return text
    # Remove em dashes globally from model output.
    return text.replace('—', ' - ')


def _sanitize_content_text(content):
    """Recursively sanitize all strings in generated content payload."""
    if isinstance(content, dict):
        return {k: _sanitize_content_text(v) for k, v in content.items()}
    if isinstance(content, list):
        return [_sanitize_content_text(v) for v in content]
    if isinstance(content, str):
        return _sanitize_text(content)
    return content


def call_claude_api(prop, system_prompt):
    """
    Generate property report content via OpenRouter (Sonnet).

    Same request shape as core/router.py: POST OPENROUTER_URL, parse with
    json.loads(resp.text.strip()), content from choices[0].message.content.
    No retry — raise_for_status then catch/log/raise for the caller fallback.
    """
    user_message = build_user_message(prop)

    try:
        resp = requests.post(
            OPENROUTER_URL,
            headers={
                "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "model": SONNET_MODEL,
                "max_tokens": REPORT_MAX_TOKENS,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_message},
                ],
            },
            timeout=120,
        )
        resp.raise_for_status()
        data = json.loads(resp.text.strip())
        raw = data["choices"][0]["message"]["content"].strip()

        # Strip markdown fences if the model added them despite instructions
        if raw.startswith('```'):
            raw = re.sub(r'^```[a-z]*\n?', '', raw)
            raw = re.sub(r'\n?```$', '', raw)
        raw = raw.strip('` \n').removeprefix('json').strip()

        content = json.loads(raw)
        return content

    except Exception as e:
        logging.error(f'OpenRouter API error for {prop["address"]}: {e}')
        raise


# ─────────────────────────────────────────────────────────────────────────────
# PACKET ASSEMBLY
# Appends Ben profile + static one-sheets to the generated report PDF
# ─────────────────────────────────────────────────────────────────────────────

def _find_chrome():
    for path in CHROME_PATHS:
        if path.exists():
            return path
    return None


def ensure_ben_profile_pdf():
    """
    Render ben_profile.html to a one-page PDF when missing or stale.
    Returns the PDF path, or None if rendering is unavailable.
    """
    if not BEN_PROFILE_HTML.exists():
        logging.warning(f'Ben profile HTML not found at {BEN_PROFILE_HTML}')
        return None

    if (
        BEN_PROFILE_PDF.exists()
        and BEN_PROFILE_PDF.stat().st_mtime >= BEN_PROFILE_HTML.stat().st_mtime
    ):
        return BEN_PROFILE_PDF

    chrome = _find_chrome()
    if not chrome:
        if BEN_PROFILE_PDF.exists():
            logging.warning('Chrome not found; using cached ben_profile.pdf')
            return BEN_PROFILE_PDF
        logging.warning('Chrome not found; cannot render ben_profile.html to PDF')
        return None

    url = BEN_PROFILE_HTML.resolve().as_uri()
    cmd = [
        str(chrome),
        '--headless=new',
        '--disable-gpu',
        '--no-pdf-header-footer',
        '--print-background',
        '--window-size=816,1056',
        f'--print-to-pdf={BEN_PROFILE_PDF.resolve()}',
        url,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    if result.returncode != 0 or not BEN_PROFILE_PDF.exists():
        stderr = (result.stderr or result.stdout or '').strip()
        logging.warning(f'Failed to render ben_profile.pdf: {stderr}')
        return None

    logging.info(f'Rendered Ben profile one-sheet: {BEN_PROFILE_PDF.name}')
    return BEN_PROFILE_PDF


def append_static_pages(report_pdf_path, output_path):
    """
    Merges: generated report PDF + Ben profile + Smart Way one-sheet + Off-Market one-sheet
    Writes the final 11-page packet to output_path.
    """
    writer = PdfWriter()

    # Add the generated report (8 pages)
    reader = PdfReader(report_pdf_path)
    for page in reader.pages:
        writer.add_page(page)

    # Add Ben profile one-sheet (page 9)
    ben_pdf = ensure_ben_profile_pdf()
    if ben_pdf and ben_pdf.exists():
        bp = PdfReader(str(ben_pdf))
        for page in bp.pages:
            writer.add_page(page)
    else:
        logging.warning('Ben profile one-sheet not included in packet')

    # Add Smart Way one-sheet (page 10)
    if SMARTWAY_PDF.exists():
        sw = PdfReader(str(SMARTWAY_PDF))
        writer.add_page(sw.pages[0])  # first page only
    else:
        logging.warning(f'Smart Way one-sheet not found at {SMARTWAY_PDF}')

    # Add Off-Market one-sheet (page 11)
    if OFFMARKET_PDF.exists():
        om = PdfReader(str(OFFMARKET_PDF))
        writer.add_page(om.pages[0])  # first page only
    else:
        logging.warning(f'Off-Market one-sheet not found at {OFFMARKET_PDF}')

    with open(output_path, 'wb') as fh:
        writer.write(fh)


def slugify_address(address):
    """Convert address to a safe filename: '22 Williams Dr, Moraga' → '22_Williams_Dr_Moraga'"""
    # Take everything before the state/zip
    clean = address.split(',')[0].strip()
    clean = re.sub(r'[^\w\s]', '', clean)
    clean = re.sub(r'\s+', '_', clean)
    return clean[:60]


# ─────────────────────────────────────────────────────────────────────────────
# MAIN LOOP
# ─────────────────────────────────────────────────────────────────────────────

def main(argv=None):
    global OUTPUT_DIR, CSV_PATH

    parser = argparse.ArgumentParser(description='BrightWork batch report generator')
    parser.add_argument('--test', action='store_true',
                        help='Generate only the first property (no API calls needed if --skip-api)')
    parser.add_argument('--limit', type=int, default=None,
                        help='Generate at most N properties (after other filters)')
    parser.add_argument('--address', type=str, default=None,
                        help='Generate only the property whose address contains this string')
    parser.add_argument('--skip-api', action='store_true',
                        help='Skip Claude API calls, use dummy content (for PDF layout testing)')
    parser.add_argument('--regenerate-from-staging', action='store_true',
                        help='Reuse staging/*_content.json; re-run PDF assembly only (no OpenRouter)')
    parser.add_argument('--csv', type=str, default=None,
                        help='Path to input properties CSV (default: generate/properties.csv)')
    parser.add_argument('--output-dir', type=str, default=None,
                        help='Directory for final packet PDFs (default: generate/output)')
    parser.add_argument('--auto-confirm', action='store_true',
                        help='Skip interactive preflight prompt (include flagged properties)')
    args = parser.parse_args(argv)

    _load_env_file()

    if args.csv:
        CSV_PATH = Path(args.csv)
    if args.output_dir:
        OUTPUT_DIR = Path(args.output_dir)

    # Logging setup
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s  %(levelname)s  %(message)s',
        datefmt='%H:%M:%S'
    )

    # Verify assets
    missing = []
    for path, label in [
        (CSV_PATH,           str(CSV_PATH)),
        (ASSETS_DIR / 'logo.jpg', 'assets/logo.jpg'),
    ]:
        if not Path(path).exists():
            missing.append(label)
    if not args.regenerate_from_staging:
        if not SYSTEM_PROMPT_PATH.exists():
            missing.append('system_prompt.txt')
    if missing:
        logging.error(f'Missing required files: {", ".join(missing)}')
        sys.exit(1)

    if not (ASSETS_DIR / 'signature.png').exists():
        logging.warning(
            'assets/signature.png not found. Reports will print with a blank '
            'signature space. Add the file and re-run to include Ben\'s signature.'
        )

    # Confirm Chrome fallback path will be used on this host (no Chrome installed).
    if BEN_PROFILE_PDF.exists() and _find_chrome() is None:
        logging.info(
            'Chrome not available; ensure_ben_profile_pdf will use cached %s',
            BEN_PROFILE_PDF,
        )

    # Load system prompt
    system_prompt = load_system_prompt() if not args.regenerate_from_staging else ''

    # Load and filter properties
    properties = load_properties(str(CSV_PATH))
    logging.info(f'Loaded {len(properties)} properties (Do Not Print rows excluded).')

    if not args.skip_api and not args.regenerate_from_staging:
        properties = preflight_check(properties, auto_confirm=args.auto_confirm)

    # Apply CLI filters
    if args.address:
        properties = [p for p in properties
                      if args.address.lower() in p['address'].lower()]
        if not properties:
            logging.error(f'No properties matched address filter: {args.address}')
            sys.exit(1)

    if args.test:
        properties = properties[:1]
        logging.info(f'TEST MODE: generating 1 property only.')

    if args.limit:
        properties = properties[:args.limit]
        logging.info(f'LIMIT: generating {len(properties)} propert{"y" if len(properties) == 1 else "ies"}.')

    # Set up output directory
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    staging_dir = OUTPUT_DIR / 'staging'
    staging_dir.mkdir(exist_ok=True)

    if not args.skip_api and not args.regenerate_from_staging and not OPENROUTER_API_KEY:
        logging.error(
            'OPENROUTER_API_KEY not set.\n'
            'Add it to COS_Deploy/.env, or use --skip-api for layout testing.'
        )
        sys.exit(1)

    if args.regenerate_from_staging:
        logging.info('Regenerate mode: loading cached staging JSON, skipping OpenRouter.')

    # ── Process each property ────────────────────────────────────────────────
    success_count = 0
    error_count   = 0

    for i, prop in enumerate(properties, 1):
        addr = prop['address']
        slug = slugify_address(addr)
        city = prop['city']
        city_slug = re.sub(r'\s+', '_', (city or '').strip())
        final_path = OUTPUT_DIR / f'{city_slug}_{slug}.pdf'

        logging.info(f'[{i}/{len(properties)}] {addr}')

        try:
            json_path = staging_dir / f'{slug}_content.json'

            if args.regenerate_from_staging:
                if not json_path.is_file():
                    raise FileNotFoundError(f'Cached content not found: {json_path}')
                with json_path.open(encoding='utf-8') as jf:
                    content = json.load(jf)
                logging.info(f'  Loaded cached content: {json_path.name}')
            elif args.skip_api:
                # Use minimal stub content for PDF layout testing
                content = _stub_content(prop)
            else:
                logging.info(
                    '  Calling OpenRouter (%s, max_tokens=%s)...',
                    SONNET_MODEL,
                    REPORT_MAX_TOKENS,
                )
                content = call_claude_api(prop, system_prompt)
                content = _normalize_exec_summary_stats(content, prop)
                content = _sanitize_content_text(content)
                logging.info(f'  Content generated.')

            if not args.regenerate_from_staging:
                # Keep style constraints enforced for both API and stub paths.
                content = _normalize_positioning_verdict(content)
                content = _sanitize_content_text(content)

                # Save finalized JSON so staging content mirrors the PDF payload exactly.
                with json_path.open('w', encoding='utf-8') as jf:
                    json.dump(content, jf, indent=2, ensure_ascii=False)

            # ── STEP 2: Generate report PDF ───────────────────────────────────
            report_path = str(staging_dir / f'{slug}_report.pdf')
            generate_report(content, prop, assets_dir=str(ASSETS_DIR),
                            output_path=report_path)
            logging.info(f'  PDF generated: {report_path}')

            # ── STEP 3: Append static one-sheets ──────────────────────────────
            append_static_pages(report_path, str(final_path))
            logging.info(f'  Packet complete: {final_path.name}')

            success_count += 1

            # Brief pause between API calls to avoid rate limits
            if not args.skip_api and not args.regenerate_from_staging and i < len(properties):
                time.sleep(1.5)

        except Exception as e:
            logging.error(f'  ERROR on {addr}: {e}')
            error_count += 1
            continue

    # ── Summary ──────────────────────────────────────────────────────────────
    logging.info('')
    logging.info(f'Done. {success_count} packets generated, {error_count} errors.')
    logging.info(f'Output folder: {OUTPUT_DIR.resolve()}')
    if error_count > 0:
        logging.info('Check the log above for failed properties. '
                     'Re-run with --address "partial address" to retry individual ones.')

    # Persist qr_page for Lob send (batches/{batch_id}/manifest.json).
    # OUTPUT_DIR is batches/{batch_id}/output when invoked by relaunch.trigger.
    batch_dir = OUTPUT_DIR.parent if OUTPUT_DIR.name == 'output' else OUTPUT_DIR
    manifest_path = batch_dir / 'manifest.json'
    manifest = {
        'qr_page': QR_PAGE,
        'pdf_count': success_count,
        'output_dir': str(OUTPUT_DIR.resolve()),
    }
    try:
        with open(manifest_path, 'w', encoding='utf-8') as mf:
            json.dump(manifest, mf, indent=2)
            mf.write('\n')
        logging.info('Wrote manifest %s (qr_page=%s)', manifest_path, QR_PAGE)
    except OSError as exc:
        logging.error('Failed to write manifest.json: %s', exc)
        sys.exit(1)


# ─────────────────────────────────────────────────────────────────────────────
# STUB CONTENT (used with --skip-api for PDF layout testing)
# ─────────────────────────────────────────────────────────────────────────────

def _stub_content(prop):
    """Returns minimal placeholder content for testing PDF layout without API calls."""
    addr = prop['address'].split(',')[0]
    city = prop['city']
    return {
        'letter': {
            'salutation': prop['salutation'],
            'paragraphs': [
                f"I've been watching {addr} carefully since it came off the market. "
                f"A home with its fundamentals in {city} should have found a buyer. "
                f"I think I understand why it didn't.",
                "The marketing approach left the home's best features unexplained. "
                "In a price range where buyers compare options carefully, that's a "
                "correctable problem — not a reflection of the property.",
                "I've put together a short analysis of what the listing history "
                "suggests went wrong and how I'd approach it differently.",
                "Take a look, and I'd welcome the chance to talk it through with you.",
            ],
            'closing': 'With respect,',
        },
        'cover': {
            'report_title': 'The Path to Sold:',
            'tagline': 'The Blueprint for a Successful Sale',
        },
        'exec_summary': {
            'headline': f'A Home With Real Assets and a Listing That Didn\'t Show Them',
            'p1': f'{addr} has genuine assets that {city} buyers are specifically looking for. '
                  f'At {prop["list_price_str"]}, those assets can support that price, '
                  f'but only if buyers understand what they\'re looking at.',
            'p2': 'The listing was withdrawn without a sale. The marketing described the '
                  'property without giving buyers a reason to feel anything about it. '
                  'The home deserved better than it got.',
            'stats': {
                'list_price':    prop['list_price_str'] or '-',
                'price_per_sqft': f"${prop['price_per_sqft']}/sqft" if prop['price_per_sqft'] else '-',
                'hoa':            prop['hoa_str'],
            },
            'p3': 'The goal is a relaunch that leads with the right story and reaches '
                  'the specific buyer who is looking for exactly this kind of property.',
        },
        'forensics': [
            {
                'title': 'Friction #1: The Listing Description Left the Story Untold',
                'body': 'The published remarks gave buyers a list of facts with no narrative '
                        'attached. In a price range where buyers compare options carefully, '
                        'a listing that reads like a form submission gets scrolled past.',
                'brightwork_contrast_label': 'THE BRIGHTWORK DIFFERENCE',
                'brightwork_contrast': 'Our listing remarks are written the way a great '
                                       'buyer\'s agent describes a home — specific, vivid, '
                                       'and focused on what makes it irreplaceable.',
            },
            {
                'title': 'Friction #2: The Visual Story Was Never Fully Told',
                'body': 'Standard MLS photography captures rooms. It rarely captures character. '
                        'Without cinematic photography and aerial context, the features that '
                        f'make {addr} worth {prop["list_price_str"]} were invisible to buyers '
                        'browsing online.',
                'brightwork_contrast_label': 'THE BRIGHTWORK DIFFERENCE',
                'brightwork_contrast': 'Cinematic photography, a Matterport 3D tour, and a '
                                       'Sky Tour that shows the lot and neighborhood context. '
                                       'These are the minimum required to compete at this price.',
            },
            {
                'title': 'Friction #3: The Right Buyers Needed to Be Found, Not Waited For',
                'body': f'At {prop["list_price_str"]} in {city}, the buyer pool is real but '
                        'selective. A passive MLS listing doesn\'t reach them early enough in '
                        'their process. By the time they find the listing on Zillow, they may '
                        'already have a shortlist of other homes.',
                'brightwork_contrast_label': 'THE BRIGHTWORK DIFFERENCE',
                'brightwork_contrast': 'Geo-targeted digital campaigns reach SF and East Bay '
                                       'buyers who are researching this market before they\'ve '
                                       'found what they\'re looking for.',
            },
        ],
        'positioning_table': {
            'subject_label': addr,
            'market_label':  f'{city} Market Context',
            'rows': [
                {'metric': 'Price per Sq. Ft.',
                 'subject': f"${prop['price_per_sqft']}/sqft" if prop['price_per_sqft'] else '-',
                 'market':  prop['city_benchmark']},
                {'metric': 'Lot / Setting',
                 'subject': prop['lot_size'] or 'See listing',
                 'market':  'Typical for city'},
                {'metric': 'Year Built',
                 'subject': prop['year_built'] or '-',
                 'market':  f'{city} median vintage'},
                {'metric': 'Premium Features',
                 'subject': prop['features'][:60] + '...' if len(prop['features']) > 60
                            else (prop['features'] or 'See listing'),
                 'market':  'Standard floor plan'},
                {'metric': 'HOA',
                 'subject': prop['hoa_str'],
                 'market':  'Varies ($0–$500/mo)'},
            ],
            'verdict': f'The fundamentals justify the price point. The challenge was '
                       f'communicating why the price makes sense - not the price itself.',
        },
        'pillars': [
            {
                'title': 'Pillar I \u2014 Present the Home the Way Buyers Actually Shop',
                'body': 'Cinematic photography and a full 3D tour that gives buyers the '
                        'visual depth to understand what makes this property worth their '
                        'attention before they ever schedule a showing.',
            },
            {
                'title': 'Pillar II \u2014 Write the Listing It Deserves',
                'body': 'From scratch. Specific, vivid, and focused on what kind of life '
                        'this home enables. Zillow Showcase puts that narrative in premium '
                        'placement in front of buyers who are actively searching.',
            },
            {
                'title': 'Pillar III \u2014 Reach the Right Buyer Directly',
                'body': 'Targeted digital campaigns that find the specific buyer profile '
                        'for this property — by geography, life stage, and intent — '
                        'rather than waiting for them to find the listing.',
            },
        ],
    }


if __name__ == '__main__':
    main()
