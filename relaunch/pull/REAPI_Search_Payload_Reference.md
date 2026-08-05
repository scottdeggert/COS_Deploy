# RealEstateAPI Search Payload Reference

> **Source of truth:** [RealEstateAPI Developer Reference](https://developer.realestateapi.com/reference)  
> **Endpoints covered:** `POST /v2/MLSSearch` · `POST /v2/PropertySearch`  
> **Last grounded against:** MLS Search API OpenAPI, Property Search API OpenAPI, Current Status Searches, Listing Status Change Date Searches, Listing Price Searches, Set Your Location(s), Property Search Field Guide, Foreclosure Searches, Property Search Paging Example

Both endpoints accept JSON request bodies and require the `x-api-key` header.

```http
POST https://api.realestateapi.com/v2/MLSSearch
POST https://api.realestateapi.com/v2/PropertySearch
Content-Type: application/json
x-api-key: <your-api-key>
```

---

## 1. Geographic Parameters

### `zip`

| Endpoint | Field | Type | Format / Rules |
|---|---|---|---|
| **MLSSearch** | `zip` | `string` **or** `string[]` | Single ZIP string **or** array of ZIP strings. Example: `"94595"` or `["94595","94596","94597"]`. |
| **PropertySearch** | `zip` | `string` **or** `string[]` | Single US ZIP **or** array of ZIP strings. **No `state` required** when using `zip`. Field guide requires exactly **5 digits** per ZIP in responses. |

**MLSSearch example (multi-ZIP Lamorinda):**
```json
{
  "zip": ["94595", "94596", "94597", "94598", "94507", "94549", "94556", "94563"]
}
```

**PropertySearch example (single or array):**
```json
{ "zip": "22205", "size": 50 }
```
```json
{ "zip": ["22205", "23857", "95687", "20008"], "size": 50 }
```

---

### `city`

| Endpoint | Field | Type | Dependencies |
|---|---|---|---|
| **MLSSearch** | `city` | `string` | **Requires `state`.** Best combined with `zip`, `county`, or `street`. |
| **PropertySearch** | `city` | `string` | **Must be accompanied by `state` or `zip`** to limit results. |

**Example (both endpoints):**
```json
{
  "city": "Richmond",
  "state": "VA",
  "size": 50
}
```

---

### `state`

| Endpoint | Field | Type | Format / Rules |
|---|---|---|---|
| **MLSSearch** | `state` | `string` | **2-character state code, ALL CAPS** (e.g. `"CA"`, `"VA"`). Combine with `county`, `city`, or `street`. |
| **PropertySearch** | `state` | `string` | **2-digit state code, all caps.** Must be accompanied by `city`, `house`, or `street` to limit results (exceptions exist for some distress filters like foreclosures/judgments at state scale). |

**Example:**
```json
{
  "state": "CA",
  "size": 50
}
```

---

### Additional geo fields (both endpoints)

| Field | Type | Notes |
|---|---|---|
| `county` | `string` | MLSSearch: combine with `state`. PropertySearch: requires `state` or `zip`. |
| `street` | `string` | Must be scoped with other geo fields. |
| `house` | `string` | PropertySearch: must include `state` or `zip`. |
| `address` | `string` | Full or partial address; usable with `radius`. |
| `latitude` / `longitude` / `radius` | `number` | Radius search. MLSSearch: 1–100 miles. PropertySearch: 0.1–100 miles. |
| `polygon` | `array` of `{ lat, lon }` | Closed polygon boundary. |
| `multi_polygon` | `array` | PropertySearch: minimum 1 polygon object with `boundaries`. |

---

## 2. Structural & Property Filters

### `property_type`

| Endpoint | Field | Type | Accepted Values |
|---|---|---|---|
| **MLSSearch** | `property_type` | `string` | Public-record types: **`SFR`**, **`MFR`**, **`LAND`**, **`CONDO`**, **`MOBILE`**, **`OTHER`** |
| **PropertySearch** | `property_type` | `string` (enum) | **`SFR`**, **`MFR`**, **`LAND`**, **`CONDO`**, **`MOBILE`**, **`OTHER`** |

**Example:**
```json
{ "property_type": "SFR" }
```

> **MLSSearch also exposes** `listing_property_type` (`RESIDENTIAL`, `LAND`, `COMMERCIAL`, etc.) and `property_sub_type` for MLS-board-level classification. See [Listing Property Type](https://developer.realestateapi.com/reference/listing-property-type).

---

### Property use (public record)

There is **no request field named `property_use`**. Use the code-based fields below.

| Endpoint | Request Field | Type | Notes |
|---|---|---|---|
| **PropertySearch** | `property_use_code` | `integer` **or** `integer[]` | County Assessor use codes. See [Property Use Codes Reference](https://developer.realestateapi.com/reference/property-use-codes-reference). |
| **MLSSearch** | `public_property_use_code` | `integer` **or** `integer[]` | Same code set, applied against linked public-record data. |
| **MLSSearch** | `public_property_use` | `string` | String form of public-record property use. |

**PropertySearch example:**
```json
{ "property_use_code": 385 }
```
```json
{ "property_use_code": [385, 366] }
```

---

### Listing price minimum

> **`list_price_min` is not a documented request field on either endpoint.** Use the endpoint-specific keys below.

| Endpoint | Correct Field | Type | Pair With |
|---|---|---|---|
| **MLSSearch** | `listing_price_min` | `integer` | `listing_price_max` |
| **PropertySearch** | `mls_listing_price_min` | `integer` | `mls_listing_price_max` |

**MLSSearch example ($950,000 floor):**
```json
{
  "listing_price_min": 950000
}
```

**PropertySearch example:**
```json
{
  "mls_listing_price_min": 950000,
  "mls_listing_price_max": 1500000
}
```

PropertySearch also supports operator-based single-threshold search via `mls_listing_price` + `mls_listing_price_operator` (`lt`, `lte`, `gt`, `gte`).

---

## 3. Historical Time Bounds (MLS Status Changes)

These fields apply to **`/v2/MLSSearch` only** in the official schema.

| Field | Type | Format | Description |
|---|---|---|---|
| `last_status_change_date_min` | `string` | `YYYY-MM-DD` | Lower bound on last MLS status-change date. |
| `last_status_change_date_max` | `string` | `YYYY-MM-DD` | Upper bound on last MLS status-change date. |

**Documented example:**
```json
{
  "count": true,
  "last_status_change_date_min": "2025-04-01",
  "last_status_change_date_max": "2025-04-01"
}
```

**Lamorinda unsold-closed example:**
```json
{
  "status": "Closed",
  "sold": false,
  "last_status_change_date_min": "2026-01-01",
  "last_status_change_date_max": "2026-06-01",
  "listing_price_min": 950000,
  "property_type": "SFR",
  "zip": ["94595", "94596", "94597", "94598", "94507", "94549", "94556", "94563"]
}
```

> **`status_date_min` / `status_date_max` are not valid MLSSearch request keys** and will return a 400 validation error.

### Related MLS date fields (MLSSearch)

| Field | Format |
|---|---|
| `listing_date_min` / `listing_date_max` | `YYYY-MM-DD` |
| `listing_contract_date_min` / `listing_contract_date_max` | `YYYY-MM-DD` |
| `sold_date_min` / `sold_date_max` | `YYYY-MM-DD` |
| `modification_timestamp_min` / `modification_timestamp_max` | `YYYY-MM-DD` |
| `price_change_timestamp_min` / `price_change_timestamp_max` | `YYYY-MM-DD` |

PropertySearch uses different sale/distress date keys (`last_sale_date_min`, `foreclosure_date_min`, `pre_foreclosure_date_min`, etc.) — not `last_status_change_date_*`.

---

## 4. Public Record Distress Parameters

### Keys that do **not** exist in the request schema

The following are **not** documented request payload fields on `/v2/PropertySearch` or `/v2/MLSSearch`:

- `bankruptcy`
- `divorce`
- `foreclosure_status`

Do not send these keys; they are not in the official OpenAPI request models.

---

### `/v2/PropertySearch` — documented distress keys

| Request Field | Type | Description |
|---|---|---|
| `pre_foreclosure` | `boolean` | Properties with any pre-foreclosure notice. Default lookback **1 year** unless bounded. |
| `foreclosure` | `boolean` | Properties in foreclosure. Default lookback **1 year** unless bounded. |
| `reo` | `boolean` | Bank/trust/service/tax-entity owned (REO). Default lookback **1 year** unless bounded. |
| `auction` | `boolean` | Properties with an auction date. Default lookback **1 year** unless bounded. |
| `notice_type` | `string` | Filters by foreclosure notice type on `.foreclosureInfo` recording date. Values: **`NOD`**, **`NOL`**, **`NTS`**, **`FOR`**, **`REO`**. |
| `search_range` | `string` | Relative window from now backward. Values: **`1_MONTH`**, **`2_MONTH`**, **`3_MONTH`**, **`6_MONTH`**, **`1_YEAR`**. Used with `reo`, `auction`, `foreclosure`, `pre_foreclosure`. |
| `foreclosure_date_min` / `foreclosure_date_max` | `string` (`YYYY-MM-DD`) | Use with `"foreclosure": true` and optionally `"notice_type"`. |
| `pre_foreclosure_date_min` / `pre_foreclosure_date_max` | `string` (`YYYY-MM-DD`) | Use with `"pre_foreclosure": true`. |
| `auction_date_min` / `auction_date_max` | `string` (`YYYY-MM-DD`) | Use with `"auction": true`. |
| `tax_lien` | `boolean` | Properties with a tax lien. |
| `judgment` | `boolean` | Properties with a recorded judgment. |
| `death` | `boolean` | Recently deceased owner on deed (probate-oriented). |

**Pre-foreclosure with notice type and date range:**
```json
{
  "size": 200,
  "pre_foreclosure": true,
  "notice_type": "NOD",
  "pre_foreclosure_date_min": "2023-11-01",
  "pre_foreclosure_date_max": "2023-11-30",
  "city": "San Francisco",
  "state": "CA"
}
```

**Foreclosure with explicit dates:**
```json
{
  "size": 10,
  "ids_only": true,
  "foreclosure": true,
  "foreclosure_date_min": "2025-09-01",
  "foreclosure_date_max": "2026-01-01",
  "state": "CA"
}
```

**REO with relative window:**
```json
{
  "size": 50,
  "reo": true,
  "search_range": "6_MONTH",
  "city": "Boise",
  "state": "ID"
}
```

---

### `/v2/MLSSearch` — public-record distress filters

MLSSearch exposes **`public_*` prefixed boolean filters** against linked county/public-record data (examples from schema):

| Request Field | Type |
|---|---|
| `public_absentee_type` | `boolean` |
| `public_corporate_owned` | `boolean` |
| `public_vacant` | `boolean` |

Foreclosure-related fields appear in **response objects** (`foreclosure`, pre-foreclosure indicators inside listing/public-record payloads), but MLSSearch request distress filtering is primarily via MLS status booleans (`active`, `cancelled`, `failed`, `pending`, `sold`) and the `status` / `custom_status` string fields — not via `foreclosure` / `pre_foreclosure` request keys on the PropertySearch side.

---

## 5. Compound `OR` Query Syntax

Both endpoints support nested **`and`** / **`or`** objects for disjunctive (OR) logic inside a conjunctive (AND) wrapper.

### Structural pattern

```json
{
  "<shared filters applied to all branches>": "...",
  "and": [
    {
      "or": [
        { "<condition A>": "<value>" },
        { "<condition B>": "<value>" },
        { "<condition C>": "<value>" }
      ]
    }
  ]
}
```

- Top-level scalar fields outside `and` are **AND**-ed with the compound block.
- Objects inside `"or"` are **OR**-ed with each other.
- Multiple `"and"` array entries are themselves **AND**-ed.

---

### PropertySearch — multi-geo OR (official example)

From [Set Your Location(s)](https://developer.realestateapi.com/reference/set-your-locations):

```json
{
  "absentee_owner": true,
  "and": [
    {
      "or": [
        { "city": "Richmond", "state": "VA" },
        { "zip": "22205" },
        { "county": "Brunswick", "state": "VA" }
      ]
    }
  ]
}
```

---

### PropertySearch / MLSSearch — multi-status OR

From [Current Status Searches](https://developer.realestateapi.com/reference/current-status-searches):

**Boolean status flags OR:**
```json
{
  "city": "Richmond",
  "state": "VA",
  "and": [
    {
      "or": [
        { "active": true },
        { "pending": true }
      ]
    }
  ]
}
```

**String `status` values OR:**
```json
{
  "city": "Richmond",
  "state": "VA",
  "and": [
    {
      "or": [
        { "status": "Active" },
        { "status": "Pending" }
      ]
    }
  ]
}
```

### MLSSearch `status` string values (documented)

`Active` · `Closed` · `Coming Soon` · `Contingent` · `Expired` · `Off Market` · `Pending` · `Pending Sale` · `Sold` · `Active Under Contract`

### MLSSearch boolean status shortcuts

| Field | Type | Maps To |
|---|---|---|
| `active` | `boolean` | Active listings |
| `cancelled` | `boolean` | Cancelled listings |
| `failed` | `boolean` | Failed listings |
| `pending` | `boolean` | Pending listings |
| `sold` | `boolean` | Sold listings (prefer `sold_date_min`/`sold_date_max`) |

**Unsold closed pattern (single status, no OR block required):**
```json
{
  "status": "Closed",
  "sold": false
}
```

---

## 6. Pagination — `size` and `resultIndex`

Both endpoints share the same cursor-pagination model.

### Request fields

| Field | Type | Default | Rules |
|---|---|---|---|
| `size` | `integer` | `50` (PropertySearch) | Max records returned **per request**. |
| `resultIndex` | `integer` | `0` | Zero-based cursor — server skips this many matching records before returning the page. |
| `count` | `boolean` | `false` | When `true`, returns **`resultCount` only**; no record objects. |

**Per-endpoint `size` limits:**

| Endpoint | Record-pulling mode | `ids_only` mode |
|---|---|---|
| **PropertySearch** | 1–**250** per page (server-enforced cap even if `size` > 250) | N/A |
| **MLSSearch** | 1–**250** per page | 1–**10,000** |

---

### Response fields (both endpoints)

| Field | Type | Meaning |
|---|---|---|
| `data` | `array` | **The record objects for the current page.** |
| `resultCount` | `integer` | **Total matching records** for the query across all pages. |
| `recordCount` | `integer` | **Number of records returned in this response** (current page count). |
| `resultIndex` | `integer` | Cursor value returned by the server; use as the starting index for the next page. |
| `input` | `object` | Echo of the normalized request payload. |
| `statusCode` | `integer` | HTTP-equivalent status (`200` on success). |
| `statusMessage` | `string` | e.g. `"Success"`. |

> **Important:** Records are in **`data`**, not `listings`. Scripts must read `response["data"]`.

---

### Pagination algorithm (official Property Search paging recipe)

```python
result_index = 0
page_size = 50
all_records = []

while True:
    payload = {
        "count": False,
        "size": page_size,
        "resultIndex": result_index,
        # ... your filters ...
    }
    response = requests.post(url, headers=headers, json=payload).json()

    page = response["data"]
    record_count = response["recordCount"]
    result_count = response["resultCount"]

    all_records.extend(page)

    # Single-page result set
    if result_count == record_count:
        break

    result_index += record_count

    if result_index >= result_count:
        break
```

**Step-by-step rules:**

1. **Initialize** `resultIndex = 0`.
2. **Send** POST with fixed filters + current `resultIndex` + `size`.
3. **Append** `data` array to your accumulator.
4. **If** `recordCount == 0` → stop (no more records).
5. **If** `resultCount == recordCount` on the first call → stop (entire result fits in one page).
6. **Else** set `resultIndex = resultIndex + recordCount` (equivalently, use the `resultIndex` value returned in the response for the next call).
7. **Repeat** while `resultIndex < resultCount`.

**Concrete Lamorinda walk-through (33 total records, `size: 50`):**

| Call | Request `resultIndex` | Response `recordCount` | Response `resultCount` | Action |
|---|---|---|---|---|
| 1 | `0` | `33` | `33` | Append 33 records. `resultIndex + recordCount (33) >= resultCount (33)` → **stop** |

**Multi-page walk-through (600 total records, `size: 50`):**

| Call | Request `resultIndex` | `recordCount` | Running total | Next `resultIndex` |
|---|---|---|---|---|
| 1 | `0` | `50` | 50 | `50` |
| 2 | `50` | `50` | 100 | `100` |
| … | … | … | … | … |
| 12 | `550` | `50` | 600 | `600` |
| — | `600 >= 600` | — | **600** | **stop** |

---

## 7. Endpoint Quick-Compare

| Concern | `/v2/MLSSearch` | `/v2/PropertySearch` |
|---|---|---|
| Primary use | Live MLS listing records (IDX-grade; requires MLS dataset access) | Public-record property list building + enrichment via Property Detail |
| Geo `zip` array | ✅ | ✅ |
| `city` + `state` | ✅ (`state` required with `city`) | ✅ |
| Price floor key | `listing_price_min` | `mls_listing_price_min` |
| Property use key | `public_property_use_code` | `property_use_code` |
| Status change dates | `last_status_change_date_min/max` | ❌ (not in schema) |
| MLS status filter | `status`, `active`, `cancelled`, `failed`, `sold`, etc. | `mls_active`, `mls_pending`, `mls_cancelled`, `mls_sold` |
| Foreclosure filter | via `public_*` + MLS status fields | `foreclosure`, `pre_foreclosure`, `reo`, `auction`, `notice_type` |
| Compound OR | `"and": [{ "or": [...] }]` | `"and": [{ "or": [...] }]` |
| Response records key | `data` | `data` |
| Page size max | 250 (50 default on PropertySearch) | 250 |

---

## 8. Common Validation Pitfalls

| Invalid Key | Correct Replacement | Endpoint |
|---|---|---|
| `status_date_min` | `last_status_change_date_min` | MLSSearch |
| `status_date_max` | `last_status_change_date_max` | MLSSearch |
| `list_price_min` | `listing_price_min` | MLSSearch |
| `list_price_min` | `mls_listing_price_min` | PropertySearch |
| `property_use` | `property_use_code` or `public_property_use_code` | PropertySearch / MLSSearch |
| `bankruptcy` | Not available as a search filter | — |
| `divorce` | Not available as a search filter | — |
| `foreclosure_status` | Use `foreclosure: true` and/or `pre_foreclosure: true` with date bounds | PropertySearch |
| `listings` (response) | `data` | Both |

---

## 9. Official Doc Links

- [MLS Search API](https://developer.realestateapi.com/reference/mls-search-api)
- [Property Search API](https://developer.realestateapi.com/reference/property-search-api)
- [Current Status Searches](https://developer.realestateapi.com/reference/current-status-searches)
- [Listing Status Change Date Searches](https://developer.realestateapi.com/reference/listing-status-change-date-searches)
- [Listing Price Searches](https://developer.realestateapi.com/reference/listing-price-searches)
- [Set Your Location(s)](https://developer.realestateapi.com/reference/set-your-locations)
- [Property Search Field Guide](https://developer.realestateapi.com/reference/property-search-field-guide)
- [(Pre-)Foreclosure & Auction Searches](https://developer.realestateapi.com/reference/foreclosure-searches)
- [Property Search Paging Example](https://developer.realestateapi.com/recipes/property-search-paging-example)
- [Property Use Codes Reference](https://developer.realestateapi.com/reference/property-use-codes-reference)
- [Live Swagger (staging)](https://staging.realestateapi.com/swagger)
