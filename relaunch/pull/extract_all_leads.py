"""
Secure multi-client RealEstateAPI master extraction engine.

Schema rules: RE_API_SCHEMA.md
Payload conventions: REAPI_Search_Payload_Reference.md
"""

from __future__ import annotations

import json
import os
import re
import sys
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any, Callable, NotRequired, TypedDict

import pandas as pd
import requests
from dotenv import load_dotenv

_PULL_DIR = os.path.dirname(os.path.abspath(__file__))
_REPO_ROOT = os.path.abspath(os.path.join(_PULL_DIR, "..", ".."))
load_dotenv(os.path.join(_REPO_ROOT, ".env"))
load_dotenv(os.path.join(_PULL_DIR, ".env"))

# ---------------------------------------------------------------------------
# Environment & authentication
# ---------------------------------------------------------------------------

API_KEY = os.getenv("REAPI_API_KEY")

PAGE_SIZE = 50
COST_PER_API_PAGE_USD = 0.01
AUDIT_LOG_FILE = os.path.join(_PULL_DIR, "REAPI_Execution_Audit.txt")
DATA_STATE_FILE = os.path.join(_PULL_DIR, "data_state.json")
BASELINE_INIT_DATE = "2026-01-01"
EXPORT_ROOT = os.path.join(_PULL_DIR, "data_exports")
ISO_DATE_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}$")

MODULE_OUTPUT_FILENAMES: dict[str, str] = {
    "expired": "Expired_Listings.csv",
    "divorce": "Divorces.csv",
    "distressed": "Distressed_Homeowners.csv",
    "pre_foreclosure": "PreForeclosures.csv",
}

# ---------------------------------------------------------------------------
# Client configurations
# ---------------------------------------------------------------------------

ACTIVE_CLIENT = "Ben"


class ClientConfig(TypedDict):
    zips: list[str]
    price_floor: int
    targets: list[str]
    output_files: NotRequired[dict[str, str]]


CLIENT_CONFIGS: dict[str, ClientConfig] = {
    "Ben": {
        "zips": [
            "94595",
            "94596",
            "94597",
            "94598",
            "94507",
            "94549",
            "94556",
            "94563",
        ],
        "price_floor": 950_000,
        "targets": ["expired", "divorce", "distressed", "pre_foreclosure"],
    },
    "Concord_Hungry_Agents": {
        "zips": ["94518", "94519", "94520", "94521"],
        "price_floor": 450_000,
        "targets": ["divorce", "distressed", "pre_foreclosure"],
    },
}

# ---------------------------------------------------------------------------
# Types & trackers
# ---------------------------------------------------------------------------


class UsageTracker(TypedDict):
    raw_records_downloaded: int
    consolidated_unique_records: int
    api_pages_fetched: int
    estimated_cost_usd: float
    module_breakdown: dict[str, dict[str, int | float | str]]


class ModuleResult(TypedDict):
    module: str
    output_file: str
    raw_count: int
    unique_count: int
    column_count: int


@dataclass
class EngineContext:
    paginated_fetch: Callable[..., list[dict[str, Any]]]
    records_to_dataframe: Callable[[list[dict[str, Any]]], pd.DataFrame]
    lossless_deduplicate: Callable[..., pd.DataFrame]
    tracker: UsageTracker
    page_size: int
    date_boundary_min: str
    date_boundary_max: str
    export_dir: str


def new_usage_tracker() -> UsageTracker:
    return {
        "raw_records_downloaded": 0,
        "consolidated_unique_records": 0,
        "api_pages_fetched": 0,
        "estimated_cost_usd": 0.0,
        "module_breakdown": {},
    }


# ---------------------------------------------------------------------------
# Persistent state & export routing
# ---------------------------------------------------------------------------


def _is_valid_iso_date(value: str) -> bool:
    if not ISO_DATE_PATTERN.match(value):
        return False
    try:
        datetime.strptime(value, "%Y-%m-%d")
    except ValueError:
        return False
    return True


def _load_state_payload() -> dict[str, str]:
    """Read per-client checkpoint dates from data_state.json."""
    if not os.path.isfile(DATA_STATE_FILE):
        return {}

    try:
        with open(DATA_STATE_FILE, encoding="utf-8") as state_file:
            payload = json.load(state_file)
        if not isinstance(payload, dict):
            return {}

        if "last_successful_run" in payload:
            legacy = payload.get("last_successful_run", "")
            if isinstance(legacy, str) and _is_valid_iso_date(legacy):
                payload.setdefault("Ben", legacy)

        checkpoints: dict[str, str] = {}
        for client_name, checkpoint in payload.items():
            if client_name == "last_successful_run":
                continue
            if isinstance(checkpoint, str) and _is_valid_iso_date(checkpoint.strip()):
                checkpoints[client_name] = checkpoint.strip()
        return checkpoints
    except (OSError, json.JSONDecodeError, TypeError):
        return {}


def load_last_successful_run(client_name: str) -> str:
    """Return the last successful run date for client_name, or baseline if unset."""
    candidate = _load_state_payload().get(client_name, "")
    if isinstance(candidate, str) and candidate.strip() and _is_valid_iso_date(candidate.strip()):
        return candidate.strip()
    return BASELINE_INIT_DATE


def save_last_successful_run(client_name: str, run_date: str | None = None) -> str:
    """Persist run_date (default today) for client_name without overwriting other clients."""
    persisted = run_date or date.today().isoformat()
    checkpoints = _load_state_payload()
    checkpoints[client_name] = persisted
    with open(DATA_STATE_FILE, "w", encoding="utf-8") as state_file:
        json.dump(checkpoints, state_file, indent=2)
        state_file.write("\n")
    return persisted


def ensure_export_dir(client_name: str) -> str:
    """Create ./data_exports/{client_name}/{YYYY-MM}/ and return its path."""
    year_month = datetime.now().strftime("%Y-%m")
    export_dir = os.path.join(EXPORT_ROOT, client_name, year_month)
    os.makedirs(export_dir, exist_ok=True)
    return export_dir


def resolve_module_output_path(
    export_dir: str,
    module_name: str,
    client: ClientConfig,
) -> str:
    """Resolve full CSV path inside the client export directory."""
    filename = client.get("output_files", {}).get(
        module_name,
        MODULE_OUTPUT_FILENAMES[module_name],
    )
    return os.path.join(export_dir, filename)


# ---------------------------------------------------------------------------
# HTTP layer
# ---------------------------------------------------------------------------


def build_headers() -> dict[str, str]:
    if API_KEY is None:
        raise RuntimeError("REAPI_API_KEY is not configured.")
    return {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "x-api-key": API_KEY,
    }


def paginated_fetch(
    url: str,
    payload_builder: Callable[[int], dict[str, Any]],
    tracker: UsageTracker,
) -> list[dict[str, Any]]:
    headers = build_headers()
    all_records: list[dict[str, Any]] = []
    result_index = 0
    result_count: int | None = None

    while True:
        payload = payload_builder(result_index)
        response = requests.post(url, headers=headers, json=payload, timeout=120)
        response.raise_for_status()
        body = response.json()

        tracker["api_pages_fetched"] += 1
        tracker["estimated_cost_usd"] = round(
            tracker["api_pages_fetched"] * COST_PER_API_PAGE_USD, 4
        )

        page = body.get("data", [])
        record_count = int(body.get("recordCount", len(page)))
        if result_count is None:
            result_count = int(body.get("resultCount", 0))

        all_records.extend(page)
        tracker["raw_records_downloaded"] += record_count

        print(
            f"    API page resultIndex={result_index} | "
            f"records={record_count} | running_raw={len(all_records)} | "
            f"resultCount={result_count}"
        )

        if record_count == 0:
            break

        result_index += record_count
        if result_count is not None and result_index >= result_count:
            break

    return all_records


def records_to_dataframe(records: list[dict[str, Any]]) -> pd.DataFrame:
    if not records:
        return pd.DataFrame()
    # PropertySearch returns flat top-level keys; MLSSearch may nest after normalize.
    sample = records[0]
    if any(isinstance(value, dict) for value in sample.values()):
        return pd.json_normalize(records)
    return pd.DataFrame(records)


# Realtor-ready front columns (PropertySearch flat keys + MLSSearch nested fallbacks).
REALTOR_FRONT_COLUMN_GROUPS: list[list[str]] = [
    ["address.address", "public.address.address", "listing.address.unparsedAddress"],
    ["address.city", "public.address.city", "listing.address.city"],
    ["address.zip", "public.address.zip", "listing.address.zipCode"],
    ["owner1FirstName", "public.owner1FirstName"],
    ["owner1LastName", "public.owner1LastName"],
    ["estimatedValue", "public.estimatedValue"],
    ["openMortgageBalance", "public.openMortgageBalance"],
]


def reorder_realtor_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Push human-readable lead fields to the left before CSV export."""
    if df.empty:
        return df.copy()

    front_columns: list[str] = []
    for group in REALTOR_FRONT_COLUMN_GROUPS:
        for column in group:
            if column in df.columns:
                front_columns.append(column)
                break

    remaining = [column for column in df.columns if column not in front_columns]
    return df[front_columns + remaining]


# ---------------------------------------------------------------------------
# Lossless deduplication (RE_API_SCHEMA.md)
# ---------------------------------------------------------------------------

# PropertySearch flat response keys (.cursorrules §3)
FLAT_GROUP_KEY_FALLBACKS: list[str] = ["apn", "id", "propertyId"]

# MLSSearch flattened nested keys (expired module)
NESTED_GROUP_KEY_FALLBACKS: list[str] = ["public.apn", "id", "listingId", "public.propertyId"]


def _is_nested_schema(group_key: str) -> bool:
    return group_key.startswith(("public.", "listing.", "listingAgent.", "listingOffice."))


def _resolve_group_column(df: pd.DataFrame, group_key: str) -> str:
    fallbacks = (
        NESTED_GROUP_KEY_FALLBACKS if _is_nested_schema(group_key) else FLAT_GROUP_KEY_FALLBACKS
    )
    candidates = [group_key, *[k for k in fallbacks if k != group_key]]
    for column in candidates:
        if column in df.columns:
            populated = df[column].astype("string").str.strip()
            if populated.notna().any() and (populated != "").any():
                return column
    raise ValueError(
        f"No usable group key in dataframe. Tried {candidates}. "
        f"Available columns sample: {list(df.columns)[:20]}"
    )


def lossless_deduplicate(df: pd.DataFrame, group_key: str = "apn") -> pd.DataFrame:
    """
    Merge duplicate rows into one exhaustive master profile per parcel key.

    PropertySearch rows use flat top-level columns (apn, id, estimatedValue,
    owner1FirstName, owner1LastName). MLSSearch callers pass nested keys
    such as public.apn explicitly.
    """
    if df.empty:
        return df.copy()

    working = df.copy()
    key_column = _resolve_group_column(working, group_key)

    working[key_column] = working[key_column].astype("string").str.strip()
    working = working[
        working[key_column].notna()
        & (working[key_column] != "")
        & (working[key_column].str.lower() != "nan")
    ]

    if working.empty:
        return working

    working["_completeness_rank"] = working.notna().sum(axis=1).astype("int64")

    master_rows: list[pd.DataFrame] = []
    for _, subset in working.groupby(key_column, sort=False):
        ranked = subset.sort_values("_completeness_rank", ascending=False)
        block = ranked.drop(columns=["_completeness_rank"]).reset_index(drop=True)
        merged = block.bfill().ffill()
        master_rows.append(merged.iloc[[0]].copy())

    consolidated = pd.concat(master_rows, ignore_index=True)
    consolidated = consolidated.drop_duplicates(subset=[key_column], keep="first").reset_index(
        drop=True
    )
    return consolidated


# ---------------------------------------------------------------------------
# Module routing
# ---------------------------------------------------------------------------

def _load_module_runners() -> dict[str, Callable[[ClientConfig, EngineContext], ModuleResult]]:
    from module_distressed import run as run_distressed
    from module_divorce import run as run_divorce
    from module_expired import run as run_expired
    from module_pre_foreclosure import run as run_pre_foreclosure

    return {
        "expired": run_expired,
        "divorce": run_divorce,
        "distressed": run_distressed,
        "pre_foreclosure": run_pre_foreclosure,
    }


def append_execution_audit(
    client_name: str,
    module_name: str,
    raw_count: int,
    unique_count: int,
    api_pages: int,
    module_cost_usd: float,
    output_file: str,
    export_dir: str,
) -> None:
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    entry = (
        f"[{timestamp}] client={client_name} | module={module_name} | "
        f"raw_rows={raw_count} | unique_rows={unique_count} | "
        f"api_pages={api_pages} | est_cost_usd=${module_cost_usd:.4f} | "
        f"export_dir={export_dir} | output_file={output_file}\n"
    )
    with open(AUDIT_LOG_FILE, "a", encoding="utf-8") as audit_log:
        audit_log.write(entry)


def run_module_pathway(
    module_name: str,
    client: ClientConfig,
    client_name: str,
    ctx: EngineContext,
    runners: dict[str, Callable[[ClientConfig, EngineContext], ModuleResult]],
) -> ModuleResult:
    if module_name not in runners:
        raise ValueError(
            f"Unknown target '{module_name}' for client '{client_name}'. "
            f"Valid modules: {list(runners)}"
        )

    pages_before = ctx.tracker["api_pages_fetched"]

    print(f"\n{'=' * 72}")
    print(f"Module: {module_name} | Client: {client_name}")
    print(f"Zips: {', '.join(client['zips'])} | price_floor: ${client['price_floor']:,}")
    print(f"{'=' * 72}")

    result = runners[module_name](client, ctx)

    api_pages = ctx.tracker["api_pages_fetched"] - pages_before
    module_cost = round(api_pages * COST_PER_API_PAGE_USD, 4)

    ctx.tracker["consolidated_unique_records"] += result["unique_count"]
    ctx.tracker["module_breakdown"][module_name] = {
        "raw_records": result["raw_count"],
        "unique_records": result["unique_count"],
        "api_pages": api_pages,
        "module_cost_usd": module_cost,
        "output_file": result["output_file"],
    }

    raw_count = result["raw_count"]
    unique_count = result["unique_count"]
    compression_pct = (1 - unique_count / raw_count) * 100 if raw_count else 0.0

    print(
        f"Compressed {raw_count} syndication rows down to {unique_count} "
        f"exhaustive unique profiles for client {client_name} "
        f"({compression_pct:.1f}% reduction)"
    )
    output_exists = os.path.isfile(result["output_file"])
    print(
        f"Saved {unique_count} rows → {result['output_file']} "
        f"({result['column_count']} columns) | "
        f"folder_verified={'yes' if output_exists else 'MISSING'}"
    )
    print(
        f"Billing — module={module_name} | api_pages={api_pages} | "
        f"est_cost=${module_cost:.4f} | running_pages={ctx.tracker['api_pages_fetched']} | "
        f"running_cost=${ctx.tracker['estimated_cost_usd']:.4f}"
    )

    append_execution_audit(
        client_name=client_name,
        module_name=module_name,
        raw_count=raw_count,
        unique_count=unique_count,
        api_pages=api_pages,
        module_cost_usd=module_cost,
        output_file=result["output_file"],
        export_dir=ctx.export_dir,
    )

    return result


def run_client_pipeline(client_name: str) -> UsageTracker:
    if client_name not in CLIENT_CONFIGS:
        raise KeyError(
            f"Client '{client_name}' not in CLIENT_CONFIGS. "
            f"Available: {list(CLIENT_CONFIGS)}"
        )

    client = CLIENT_CONFIGS[client_name]
    date_boundary_min = load_last_successful_run(client_name)
    date_boundary_max = date.today().isoformat()
    export_dir = ensure_export_dir(client_name)
    tracker = new_usage_tracker()
    ctx = EngineContext(
        paginated_fetch=paginated_fetch,
        records_to_dataframe=records_to_dataframe,
        lossless_deduplicate=lossless_deduplicate,
        tracker=tracker,
        page_size=PAGE_SIZE,
        date_boundary_min=date_boundary_min,
        date_boundary_max=date_boundary_max,
        export_dir=export_dir,
    )
    runners = _load_module_runners()

    # Optional comma-separated override, e.g. RELAUNCH_MODULES=expired
    modules_override = os.getenv("RELAUNCH_MODULES", "").strip()
    targets = (
        [m.strip() for m in modules_override.split(",") if m.strip()]
        if modules_override
        else list(client["targets"])
    )

    print(f"\nStarting master engine for ACTIVE_CLIENT='{client_name}'")
    print(f"Targets scheduled: {', '.join(targets)}")
    print(
        f"State boundary — {client_name} last_successful_run={date_boundary_min} "
        f"→ querying from {date_boundary_min} through {date_boundary_max}"
    )
    print(f"Export directory verified → {export_dir}")

    for module_name in targets:
        run_module_pathway(module_name, client, client_name, ctx, runners)

    print(f"\nPipeline complete for '{client_name}'.")
    print(
        f"Totals — ingested: {tracker['raw_records_downloaded']} | "
        f"unique retained: {tracker['consolidated_unique_records']} | "
        f"api pages: {tracker['api_pages_fetched']} | "
        f"est cost: ${tracker['estimated_cost_usd']:.4f}"
    )
    print(f"Execution audit appended → {AUDIT_LOG_FILE}")

    persisted_date = save_last_successful_run(client_name)
    print(
        f"State checkpoint updated → {DATA_STATE_FILE} "
        f"({client_name}={persisted_date})"
    )

    return tracker


def main() -> int:
    if API_KEY is None:
        print(
            "WARNING: REAPI_API_KEY is not set.\n"
            "Populate your .env file with:\n"
            '  REAPI_API_KEY="your-api-key-here"\n'
            "Then re-run extract_all_leads.py.",
            file=sys.stderr,
        )
        return 1

    try:
        run_client_pipeline(ACTIVE_CLIENT)
    except requests.HTTPError as exc:
        print(
            f"HTTP error: {exc.response.status_code} {exc.response.text}",
            file=sys.stderr,
        )
        return 1
    except requests.RequestException as exc:
        print(f"Request failed: {exc}", file=sys.stderr)
        return 1
    except (KeyError, ValueError, RuntimeError) as exc:
        print(f"Pipeline error: {exc}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
