"""Long-term senior / high-equity module (POST /v2/PropertySearch)."""

from __future__ import annotations

import os
from typing import TYPE_CHECKING, Any

import requests

if TYPE_CHECKING:
    from build_static_farm import StaticFarmConfig, StaticFarmContext, ModuleResult

PROPERTY_SEARCH_URL = "https://api.realestateapi.com/v2/PropertySearch"
DEFAULT_OUTPUT_FILENAME = "Seniors_High_Equity.csv"
GROUP_KEY = "apn"
MODULE_NAME = "seniors"
PAGE_SIZE = 50
COST_PER_API_PAGE_USD = 0.01


def resolve_output_file(ctx: StaticFarmContext) -> str:
    return os.path.join(ctx.export_dir, DEFAULT_OUTPUT_FILENAME)


def build_payload(
    client_config: StaticFarmConfig,
    result_index: int,
    page_size: int = PAGE_SIZE,
) -> dict[str, Any]:
    return {
        "count": False,
        "size": page_size,
        "resultIndex": result_index,
        "zip": client_config["zips"],
        "property_type": "SFR",
        "free_clear": True,
        "years_owned_min": 30,
        "value_min": client_config["price_floor"],
    }


def fetch_all_records(
    client_config: StaticFarmConfig,
    ctx: StaticFarmContext,
) -> list[dict[str, Any]]:
    headers = ctx.build_headers()
    all_records: list[dict[str, Any]] = []
    result_index = 0
    result_count: int | None = None

    while True:
        payload = build_payload(client_config, result_index, ctx.page_size)
        response = requests.post(
            PROPERTY_SEARCH_URL,
            headers=headers,
            json=payload,
            timeout=120,
        )
        response.raise_for_status()
        body = response.json()

        ctx.tracker["api_pages_fetched"] += 1
        ctx.tracker["estimated_cost_usd"] = round(
            ctx.tracker["api_pages_fetched"] * COST_PER_API_PAGE_USD,
            4,
        )

        page = body.get("data", [])
        record_count = int(body.get("recordCount", len(page)))
        if result_count is None:
            result_count = int(body.get("resultCount", 0))

        all_records.extend(page)
        ctx.tracker["raw_records_downloaded"] += record_count

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


def run(client_config: StaticFarmConfig, ctx: StaticFarmContext) -> ModuleResult:
    records = fetch_all_records(client_config, ctx)
    raw_df = ctx.records_to_dataframe(records)
    consolidated_df = ctx.lossless_deduplicate(raw_df, group_key=GROUP_KEY)
    from extract_all_leads import reorder_realtor_columns

    export_df = reorder_realtor_columns(consolidated_df)
    output_file = resolve_output_file(ctx)
    export_df.to_csv(output_file, index=False)

    return {
        "module": MODULE_NAME,
        "output_file": output_file,
        "raw_count": len(raw_df),
        "unique_count": len(consolidated_df),
        "column_count": len(consolidated_df.columns),
    }
