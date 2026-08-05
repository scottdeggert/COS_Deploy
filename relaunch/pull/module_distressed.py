"""Distressed wealth preservation proxy module using stacked financial filters."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from extract_all_leads import ClientConfig, EngineContext, ModuleResult

PROPERTY_SEARCH_URL = "https://api.realestateapi.com/v2/PropertySearch"
OUTPUT_FILE = "Distressed_Homeowners.csv"
GROUP_KEY = "apn"
MODULE_NAME = "distressed"


def resolve_output_file(client: ClientConfig, ctx: EngineContext) -> str:
    from extract_all_leads import resolve_module_output_path

    return resolve_module_output_path(ctx.export_dir, MODULE_NAME, client)


def build_payload(client: ClientConfig, result_index: int, page_size: int) -> dict[str, Any]:
    # Alex's verified proxy strategy: compound OR for alternative financial distress signals
    return {
        "count": False,
        "size": page_size,
        "resultIndex": result_index,
        "zip": client["zips"],
        "property_type": "SFR",
        "value_min": client["price_floor"],
        "and": [
            {
                "or": [
                    {"pre_foreclosure": True},
                    {"judgment": True},
                    # Deep multi-year tax delinquency
                    {"tax_delinquent_year_min": 2020},
                ]
            }
        ],
    }


def run(client: ClientConfig, ctx: EngineContext) -> ModuleResult:
    records = ctx.paginated_fetch(
        PROPERTY_SEARCH_URL,
        lambda idx: build_payload(client, idx, ctx.page_size),
        ctx.tracker,
    )
    raw_df = ctx.records_to_dataframe(records)
    consolidated_df = ctx.lossless_deduplicate(raw_df, group_key=GROUP_KEY)
    from extract_all_leads import reorder_realtor_columns

    export_df = reorder_realtor_columns(consolidated_df)
    output_file = resolve_output_file(client, ctx)
    export_df.to_csv(output_file, index=False)

    return {
        "module": MODULE_NAME,
        "output_file": output_file,
        "raw_count": len(raw_df),
        "unique_count": len(consolidated_df),
        "column_count": len(consolidated_df.columns),
    }
