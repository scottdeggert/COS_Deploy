"""Expired / unsold closed MLS listings module (POST /v2/MLSSearch)."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from extract_all_leads import ClientConfig, EngineContext, ModuleResult

MLS_SEARCH_URL = "https://api.realestateapi.com/v2/MLSSearch"
DEFAULT_OUTPUT_FILENAME = "Expired_Listings.csv"
GROUP_KEY = "public.apn"
MODULE_NAME = "expired"


def resolve_output_file(client: ClientConfig, ctx: EngineContext) -> str:
    from extract_all_leads import resolve_module_output_path

    return resolve_module_output_path(ctx.export_dir, MODULE_NAME, client)


def build_payload(
    client: ClientConfig,
    result_index: int,
    page_size: int,
    date_min: str,
    date_max: str,
) -> dict[str, Any]:
    return {
        "count": False,
        "size": page_size,
        "resultIndex": result_index,
        "zip": client["zips"],
        "property_type": "SFR",
        "status": "Closed",
        "sold": False,
        "last_status_change_date_min": date_min,
        "last_status_change_date_max": date_max,
        "listing_price_min": client["price_floor"],
    }


def run(client: ClientConfig, ctx: EngineContext) -> ModuleResult:
    records = ctx.paginated_fetch(
        MLS_SEARCH_URL,
        lambda idx: build_payload(
            client,
            idx,
            ctx.page_size,
            ctx.date_boundary_min,
            ctx.date_boundary_max,
        ),
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
