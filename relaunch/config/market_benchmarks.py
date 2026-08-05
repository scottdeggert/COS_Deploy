"""
market_benchmarks.py
BrightWork Realty Advocates — Market Configuration

THIS IS THE ONLY FILE YOU EDIT BETWEEN BATCH RUNS.

Update BATCH_DATE and review BENCHMARKS before each new batch.
BENCHMARKS are keyed by ZIP code where market behavior differs within a city,
and by city name where zip-level distinction is not needed.
"""

# ─────────────────────────────────────────────────────────────────────────────
# BATCH DATE
# Appears on the cover letter. Update before every run.
# ─────────────────────────────────────────────────────────────────────────────
BATCH_DATE = 'August 2026'


# ─────────────────────────────────────────────────────────────────────────────
# BENCHMARKS
# Keyed by ZIP code (preferred) or city name (fallback).
# Each entry has named tiers. The system prompt receives the full tier detail.
# The positioning analysis uses these to calibrate verdict language.
# Sources: Redfin, Lamorinda Weekly Q1 2026, Loqol/Movoto Feb-Apr 2026.
# Update quarterly or when a new market is added.
# ─────────────────────────────────────────────────────────────────────────────
BENCHMARKS = {

    # ── MORAGA ───────────────────────────────────────────────────────────────
    'Moraga': {
        'renovated':  (700, 750),
        'original':   (630, 680),
        'premium':    (750, 820),
    },

    # ── ORINDA ───────────────────────────────────────────────────────────────
    'Orinda': {
        'renovated':      (790, 850),
        'architectural':  (860, 950),
        'premium':        (900, 1000),
    },

    # ── LAFAYETTE ────────────────────────────────────────────────────────────
    'Lafayette': {
        'renovated':  (780, 840),
        'premium':    (850, 920),
        'fixer':      (650, 720),
    },

    # ── WALNUT CREEK — keyed by ZIP ──────────────────────────────────────────
    # 94595: Parkmead + Rossmoor. Rossmoor units are flagged separately via
    #        COMMUNITY_FLAGS and handled before benchmarks are applied.
    #        These tiers apply to standard SFR in Parkmead and hillside streets.
    '94595': {
        'standard':   (580, 650),
        'renovated':  (650, 720),
    },
    # 94596: Downtown WC, Walnut Heights, hillside estates.
    '94596': {
        'standard':   (680, 760),
        'renovated':  (760, 850),
        'premium':    (850, 950),
    },
    # 94597: Core SFR market — Buena Vista, Palos Verde, Summit Ridge area.
    '94597': {
        'standard':   (650, 730),
        'renovated':  (730, 820),
        'premium':    (820, 950),
    },
    # 94598: Northgate, Shell Ridge, north WC hillside homes.
    '94598': {
        'standard':   (720, 800),
        'renovated':  (800, 880),
        'premium':    (880, 1000),
    },

    # ── ALAMO ────────────────────────────────────────────────────────────────
    'Alamo': {
        'entry':      (750, 850),
        'standard':   (850, 950),
        'premium':    (950, 1100),
    },

    # ── PLEASANT HILL ────────────────────────────────────────────────────────
    'Pleasant Hill': {
        'standard':   (500, 560),
        'renovated':  (560, 630),
        'premium':    (630, 700),
    },
}


# ─────────────────────────────────────────────────────────────────────────────
# COMMUNITY FLAGS
# Keywords checked against listing remarks (case-insensitive).
# When matched, the preflight check flags the property for human review
# before generating a packet. Add new communities here as needed.
# ─────────────────────────────────────────────────────────────────────────────
COMMUNITY_FLAGS = {
    'rossmoor':           'Rossmoor (55+ co-op community) — verify transaction structure and benchmark tier before generating packet.',
    'golden rain':        'Rossmoor (55+ co-op community) — Golden Rain Road address confirms Rossmoor location.',
    'moraga country club':'Moraga Country Club — gated golf community with HOA overlay. Verify benchmark tier.',
    ' mcc ':              'Possible Moraga Country Club reference — verify before generating packet.',
    'orinda country club':'Orinda Country Club — gated golf community. Verify benchmark tier and HOA context.',
}


# ─────────────────────────────────────────────────────────────────────────────
# PROPERTY TYPE FLAGS
# Properties matching these conditions are flagged at preflight.
# They are not auto-skipped — operator confirms whether to include.
# ─────────────────────────────────────────────────────────────────────────────
PROPERTY_TYPE_FLAGS = [
    {
        'label':     'Townhouse/Condo',
        'condition': 'townhouse_or_condo',
        'note':      'Benchmark tiers and strategy language are calibrated for SFR. Review before generating.',
    },
    {
        'label':     'Rural/Large Acreage',
        'condition': 'rural_large_lot',
        'note':      'Rural Residence or lot > 5 acres. Likely not a standard expired listing campaign candidate.',
    },
]
