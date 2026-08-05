"""
Standalone static farm extraction controller (no incremental state checkpoints).

Schema rules: RE_API_SCHEMA.md
Payload conventions: REAPI_Search_Payload_Reference.md
"""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Callable, TypedDict

import pandas as pd
import requests
from dotenv import load_dotenv

from extract_all_leads import lossless_deduplicate, records_to_dataframe

load_dotenv()

# ---------------------------------------------------------------------------
# Environment & authentication
# ---------------------------------------------------------------------------

API_KEY = os.getenv("REAPI_API_KEY")

PAGE_SIZE = 50
COST_PER_API_PAGE_USD = 0.01
AUDIT_LOG_FILE = "REAPI_Execution_Audit.txt"
EXPORT_ROOT = "./data_exports"

# ---------------------------------------------------------------------------
# Static farm configurations (independent of data_state.json)
# ---------------------------------------------------------------------------

ACTIVE_FARM = "Ben_Senior_Workshop"


class StaticFarmConfig(TypedDict):
    zips: list[str]
    price_floor: int
    module: str


STATIC_FARM_CONFIGS: dict[str, StaticFarmConfig] = {
    "Ben_Senior_Workshop": {
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
        "module": "seniors",
    },
    "Concord_Senior_Workshop": {
        "zips": ["94518", "94519", "94520", "94521"],
        "price_floor": 450_000,
        "module": "seniors",
    },
}

# ---------------------------------------------------------------------------
# Types & context
# ---------------------------------------------------------------------------


class UsageTracker(TypedDict):
    raw_records_downloaded: int
    consolidated_unique_records: int
    api_pages_fetched: int
    estimated_cost_usd: float


class ModuleResult(TypedDict):
    module: str
    output_file: str
    raw_count: int
    unique_count: int
    column_count: int


@dataclass
class StaticFarmContext:
    build_headers: Callable[[], dict[str, str]]
    records_to_dataframe: Callable[[list[dict[str, Any]]], pd.DataFrame]
    lossless_deduplicate: Callable[..., pd.DataFrame]
    tracker: UsageTracker
    page_size: int
    export_dir: str
    farm_name: str


def new_usage_tracker() -> UsageTracker:
    return {
        "raw_records_downloaded": 0,
        "consolidated_unique_records": 0,
        "api_pages_fetched": 0,
        "estimated_cost_usd": 0.0,
    }


def build_headers() -> dict[str, str]:
    if API_KEY is None:
        raise RuntimeError("REAPI_API_KEY is not configured.")
    return {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "x-api-key": API_KEY,
    }


def farm_client_name(farm_name: str) -> str:
    return farm_name.split("_", 1)[0]


def ensure_static_export_dir(farm_name: str) -> str:
    client_name = farm_client_name(farm_name)
    export_dir = os.path.join(EXPORT_ROOT, client_name, "static_farms")
    os.makedirs(export_dir, exist_ok=True)
    return export_dir


def append_execution_audit(
    farm_name: str,
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
        f"[{timestamp}] farm={farm_name} | module={module_name} | "
        f"raw_rows={raw_count} | unique_rows={unique_count} | "
        f"api_pages={api_pages} | est_cost_usd=${module_cost_usd:.4f} | "
        f"export_dir={export_dir} | output_file={output_file}\n"
    )
    with open(AUDIT_LOG_FILE, "a", encoding="utf-8") as audit_log:
        audit_log.write(entry)


def _load_module_runners() -> dict[str, Callable[[StaticFarmConfig, StaticFarmContext], ModuleResult]]:
    from module_seniors import run as run_seniors

    return {
        "seniors": run_seniors,
    }


def run_static_farm(farm_name: str) -> UsageTracker:
    if farm_name not in STATIC_FARM_CONFIGS:
        raise KeyError(
            f"Farm '{farm_name}' not in STATIC_FARM_CONFIGS. "
            f"Available: {list(STATIC_FARM_CONFIGS)}"
        )

    farm_config = STATIC_FARM_CONFIGS[farm_name]
    module_name = farm_config["module"]
    export_dir = ensure_static_export_dir(farm_name)
    tracker = new_usage_tracker()
    ctx = StaticFarmContext(
        build_headers=build_headers,
        records_to_dataframe=records_to_dataframe,
        lossless_deduplicate=lossless_deduplicate,
        tracker=tracker,
        page_size=PAGE_SIZE,
        export_dir=export_dir,
        farm_name=farm_name,
    )
    runners = _load_module_runners()

    if module_name not in runners:
        raise ValueError(
            f"Unknown module '{module_name}' for farm '{farm_name}'. "
            f"Valid modules: {list(runners)}"
        )

    pages_before = tracker["api_pages_fetched"]
    client_name = farm_client_name(farm_name)

    print(f"\n{'=' * 72}")
    print(f"Static farm: {farm_name} | Client: {client_name} | Module: {module_name}")
    print(
        f"Zips: {', '.join(farm_config['zips'])} | "
        f"price_floor: ${farm_config['price_floor']:,}"
    )
    print(f"Export directory verified → {export_dir}")
    print(f"{'=' * 72}")

    result = runners[module_name](farm_config, ctx)

    api_pages = tracker["api_pages_fetched"] - pages_before
    module_cost = round(api_pages * COST_PER_API_PAGE_USD, 4)
    tracker["consolidated_unique_records"] = result["unique_count"]

    raw_count = result["raw_count"]
    unique_count = result["unique_count"]

    print(
        f"Retained {unique_count} unique long-term senior profiles "
        f"out of {raw_count} total entries"
    )
    output_exists = os.path.isfile(result["output_file"])
    print(
        f"Saved {unique_count} rows → {result['output_file']} "
        f"({result['column_count']} columns) | "
        f"folder_verified={'yes' if output_exists else 'MISSING'}"
    )
    print(
        f"Billing — farm={farm_name} | module={module_name} | api_pages={api_pages} | "
        f"est_cost=${module_cost:.4f} | running_pages={tracker['api_pages_fetched']} | "
        f"running_cost=${tracker['estimated_cost_usd']:.4f}"
    )

    append_execution_audit(
        farm_name=farm_name,
        module_name=module_name,
        raw_count=raw_count,
        unique_count=unique_count,
        api_pages=api_pages,
        module_cost_usd=module_cost,
        output_file=result["output_file"],
        export_dir=export_dir,
    )

    print(f"\nStatic farm complete for '{farm_name}'.")
    print(
        f"Totals — ingested: {tracker['raw_records_downloaded']} | "
        f"unique retained: {tracker['consolidated_unique_records']} | "
        f"api pages: {tracker['api_pages_fetched']} | "
        f"est cost: ${tracker['estimated_cost_usd']:.4f}"
    )
    print(f"Execution audit appended → {AUDIT_LOG_FILE}")

    return tracker


def main() -> int:
    if API_KEY is None:
        print(
            "WARNING: REAPI_API_KEY is not set.\n"
            "Populate your .env file with:\n"
            '  REAPI_API_KEY="your-api-key-here"\n'
            "Then re-run build_static_farm.py.",
            file=sys.stderr,
        )
        return 1

    try:
        run_static_farm(ACTIVE_FARM)
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
        print(f"Static farm error: {exc}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
