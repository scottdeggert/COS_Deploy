# East Bay Real Estate Lead Ingestion Engine

A production-grade data pipeline utilizing the RealEstateAPI (v2) to extract, cleanly deduplicate, and segment high-intent real estate leads across multiple client configurations.

## 🛠️ System Architecture & Data Velocity

The system splits data processing into two distinct execution pathways based on data velocity and campaign intent:

### 1. Dynamic Lead Generation (High Velocity)

* **Script:** `extract_all_leads.py`
* **Target Datasets:** Expired Listings, Divorces (Quit Claims), Distressed Homeowners, Pre-Foreclosures
* **Execution Interval:** Scheduled weekly or monthly via `cron`.
* **State Management:** Tracks increments natively using `data_state.json`. It captures the date of the last successful pull so the system never queries or bills for the same historical data twice.

### 2. Demographic Geographic Farming (Static/Low Velocity)

* **Script:** `build_static_farm.py`
* **Target Datasets:** Long-Term Seniors (30+ Years Owned), Free & Clear Properties
* **Execution Interval:** Manual, ad-hoc execution (typically 1–2 times per year per market).
* **Intent:** Sourcing highly stable local data arrays for educational workshops, living trust planning seminars, and geographic neighborhood branding campaigns.

---

## 🎯 Lead Stream Definitions & Strategic Marketing Playbooks

To ensure outbound marketing campaigns (Direct Mail, Phone/Email Outreach) maximize conversion rates and maintain strict regulatory and privacy boundaries, agents must align their copy with these technical data definitions:

### 1. Expired Listings (`Expired_Listings.csv`)

**Technical Definition:** Sourced via `v2/MLSSearch`. Tracks properties where an active MLS listing contract was moved to a status of `"Closed"` but the sold indicator is explicitly `False`. This captures canceled, withdrawn, and expired listings using a strict timeframe boundary (`last_status_change_date_min` / `last_status_change_date_max`).

**The Marketing Angle:** High transactional intent with immediate frustration. The property didn't sell, and the listing contract has failed.

**The Script Rule:** Focus on process engineering and local data correction. *"Your property has undeniable structural appeal, but the data indicates the previous marketing campaign hit an exposure friction point. We specialize in localized repositioning to unlock market attention."*

### 2. Family Capital Shifts (`Divorces.csv`)

**Technical Definition:** Sourced via `v2/PropertySearch`. Tracks properties utilizing the `"quit_claim": true` filter parameter. This captures legal title transfers where one stakeholder signs over their ownership rights to another via a recorded deed change.

**The Marketing Angle:** Structural equity redistribution. While heavily correlated with final divorce settlements, it can also signify family estate reallocations or trust structural updates.

**The Script Rule:** NEVER use the word "Divorce" or reference court records. Position the agent as an administrative, neutral third-party fiduciary. *"We provide parallel, decoupled real estate transaction management. We understand that asset re-allocations require independent reporting channels, separate duplicate status updates for both parties, and absolute discretion."*

### 3. Financial Distressed Owners (`Distressed_Homeowners.csv`)

**Technical Definition:** Sourced via `v2/PropertySearch`. **CRITICAL METRIC:** RealEstateAPI does not index live federal bankruptcy court petitions. To isolate this high-intent profile without throwing API validation errors, this list uses a compound logical `"or"` array nested inside an `"and"` block, combining three distinct underlying distress signals:

* `{"pre_foreclosure": true}` — Mortgage default flags
* `{"judgment": true}` — Active civil court or financial debt judgments attached to title
* `{"tax_delinquent_year_min": 2020}` — Multi-year un-paid county property tax liabilities

**The Marketing Angle:** General financial stress, capital constraints, and equity preservation. The homeowner is facing heavy balance sheet liabilities but may not have filed a formal legal bankruptcy petition.

**The Script Rule:** NEVER use the words "Bankruptcy", "Foreclosure", or "Debt". Position the agent as a financial protector who can extract liquid wealth before equity is erased by legal clouds. *"We specialize in real estate wealth protection. Our focus is helping property owners leverage current market conditions to neutralize structural liabilities, allowing you to preserve your cash equity and hit the reset button cleanly."*

### 4. Direct Structural Defaults (`PreForeclosures.csv`)

**Technical Definition:** Sourced via `v2/PropertySearch`. Isolates properties where a formal Notice of Default (NOD) or Lis Pendens has been physically recorded against the property title at the county recorder level.

**The Marketing Angle:** Time-sensitive, acute financial and legal distress.

**The Script Rule:** Urgent informational advocacy. Offer a complimentary guide outlining structural options to stop public auctions, negotiate loan modifications, or sell seamlessly before court-mandated deadlines expire.

---

## 🗂️ Project Directory Structure

```text
Expired_Listings/
├── .cursorrules                  # Global Cursor developer directives & relative validation pathing
├── .env                          # Local private API keys (Exempt from Git tracking)
├── .gitignore                    # Git exclusions file (Blocks .env, raw CSVs, and logs)
├── RE_API_SCHEMA.md              # Flat API property parameter schema dictionaries
├── REAPI_Search_Payload_Reference.md # Validated JSON query documentation and parameters
├── REAPI_Execution_Audit.txt     # Local transaction receipts log (Tracks API credit spend)
├── data_state.json               # Automated multi-client checkpoint registry (By Client Name)
├── extract_all_leads.py          # Dynamic Master Orchestrator (The Cron Switch)
├── build_static_farm.py          # Static Batch Orchestrator (The Workshop Switch)
├── module_expired.py             # MLS feed processor (Closed + Unsold)
├── module_divorce.py             # Public record quit-claim processor (DTQC)
├── module_distressed.py          # Stacked financial distress proxy processor (Compound OR)
├── module_pre_foreclosure.py     # Public record notice-of-default processor (NOD)
├── module_seniors.py             # Public record demographic longevity processor
└── data_exports/                 # Automatically generated clean client file arrays
    ├── {Client_Name}/
    │   └── {YYYY-MM}/            # Segregated by client and execution month
    │       ├── Expired_Listings.csv
    │       ├── Divorces.csv
    │       ├── Distressed_Homeowners.csv
    │       └── PreForeclosures.csv
```

---

## 🛡️ Security & Environmental Best Practices

* All active authentication headers must reside exclusively inside a hidden root `.env` file using the key variable `REAPI_API_KEY`.
* Global parsing assumptions are governed continuously via local relative pathing controls inside `.cursorrules` to avoid hardcoded environment path collisions.
* Never commit raw `.csv` data exports or your local `.env` environment files to public GitHub repositories.
