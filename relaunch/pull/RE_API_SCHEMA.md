# RE_API_SCHEMA — Data Transformation & Deduplication Rules

> Grounded in [RealEstateAPI v2 docs](https://developer.realestateapi.com/reference) and local payload reference (`REAPI_Search_Payload_Reference.md`).

## Response Normalization

| Source Endpoint | Flatten Method | Records Array Key | Primary Dedup Key | Fallback Keys |
|---|---|---|---|---|
| `POST /v2/MLSSearch` | `pd.json_normalize(records)` | `data` | `public.apn` | `id`, `listingId`, `public.propertyId` |
| `POST /v2/PropertySearch` | `pd.json_normalize(records)` | `data` | `apn` | `id`, `propertyId`, `address.address` |

## Column Prefix Conventions (MLSSearch flattened)

| Prefix | Source Object | Examples |
|---|---|---|
| `listing.` | MLS listing payload | `listing.standardStatus`, `listing.leadTypes.mlsListingPrice` |
| `public.` | Linked public record | `public.apn`, `public.owner1LastName`, `public.leadTypes.preForeclosure` |
| `listingAgent.` | Listing agent | `listingAgent.email`, `listingAgent.phone` |
| `listingOffice.` | Listing office | `listingOffice.name`, `listingOffice.email` |

## Client Config → API Field Mapping

| Client Config Key | MLSSearch Payload Key | PropertySearch Payload Key |
|---|---|---|
| `price_floor` | `listing_price_min` (`integer`) | `value_min` (`integer`) |
| `zips` | `zip` (`string[]`) | `zip` (`string[]`) |
| `targets` | Module routing array | Module routing array |
| `output_files` | Per-module CSV filename overrides (optional) | Per-module CSV filename overrides (optional) |

## Module → Endpoint & Filter Mapping

| Module | Endpoint | Documented Filters |
|---|---|---|
| `expired` | `/v2/MLSSearch` | `status: "Closed"`, `sold: false`, `last_status_change_date_min/max`, `listing_price_min` |
| `pre_foreclosure` | `/v2/PropertySearch` | `pre_foreclosure: true`, `property_type: "SFR"`, `zip`, `value_min` |
| `divorce` | `/v2/PropertySearch` | `divorce: true`, `value_min` |
| `distressed` | `/v2/PropertySearch` | `property_type: "SFR"`, `value_min`, compound `or`: `pre_foreclosure`, `judgment`, `tax_delinquent_year_min` |

## Deduplication Algorithm (`lossless_deduplicate`)

1. Resolve dedup key column (configured field → fallbacks).
2. Coerce key to stripped `string`; drop blank/`nan` keys.
3. Compute per-row non-null count `_non_null_rank`.
4. Group by dedup key.
5. Within each group, sort by `_non_null_rank` descending (richest row first).
6. Apply `.bfill()` then `.ffill()` across rows to merge sparse fields.
7. Keep index `0` (exhaustive master profile).
8. Drop duplicate rows globally after merge.

## Type Coercion Rules

- All dedup keys → `str`, stripped.
- Currency/numeric API ints preserved; read as nullable numeric where possible post-normalize.
- Date strings kept as `object`/`string` (API returns ISO / `YYYY-MM-DD`).

## Output Artifacts

Default filenames apply when `output_files` is omitted. Clients may override per module in `CLIENT_CONFIGS`.

| Module | Default CSV | Ben override |
|---|---|---|
| `expired` | `REAPI_EastBay_Expired.csv` | `REAPI_Lamorinda_2026_Failed.csv` |
| `divorce` | `REAPI_EastBay_Divorces.csv` | (default) |
| `distressed` | `Distressed_Homeowners.csv` | (default) |
| `pre_foreclosure` | `REAPI_EastBay_PreForeclosures.csv` | (default) |
