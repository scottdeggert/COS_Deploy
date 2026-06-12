This exhaustive catalog outlines the Follow Up Boss (FUB) REST API and webhook functionality as defined by your system product specification. This document serves as a technical reference contract for your development team and the context engine of your Chief of Staff AI Agent.

FUB API Documentation: [https://docs.followupboss.com/reference/getting-started](https://docs.followupboss.com/reference/getting-started)

## **1\. Core API Connectivity & Operational Constraints**

The FUB CRM acts as the absolute source of truth for contact identity, pipelines, lifecycle stages, tags, notes, and sequence enrollment states.

* **API Version:** REST API v1.  
* **Base URL:** \[https://api.followupboss.com/v1\](https://api.followupboss.com/v1).  
* **Authentication:** HTTP Basic Auth using the FUB\_API\_KEY as the username and an empty password.  
* **Rate Limits:** Strict cap of **500 requests/hour**.  
* **Retry Policy:** Mandatory exponential backoff for HTTP 429 (Too Many Requests) errors across 3 sequential attempts at **2s, 4s, and 8s** intervals.  
* **API Failure Fallback:** If a network or server error (5xx) occurs, operations must be queued in a local SQLite database for automatic retry within 5 minutes. If the operation fails 3 consecutive times, an escalation alert is issued to the realtor via Telegram.

## 

## **2\. API Endpoints & CRUD Capabilities Catalog**

The agent interacts with the following explicit FUB endpoints to drive automation workflows:

### **Contact Management Endpoints**

* GET /contacts?email={email}  
  * **Capability:** Read.  
  * **Application:** Deterministic identity lookup to find an existing contact by their exact email string.  
* GET /contacts/{id}  
  * **Capability:** Read.  
  * **Application:** Fetches a single complete contact record, including custom fields, stages, historical notes, and attached tags.  
* POST /contacts  
  * **Capability:** Write (Create).  
  * **Application:** Provisions a completely new unique contact profile in the CRM during lead intake or scheduling sync loops.  
* PUT /contacts/{id}  
  * **Capability:** Write (Update).  
  * **Application:** Updates existing contact data fields (e.g., pipeline stages, background metadata).

### 

### **Tagging & Note Endpoints**

* POST /contacts/{id}/tags  
  * **Capability:** Write (Append).  
  * **Application:** Applies system, behavioral, and lifecycle tags from the canonical taxonomy to a contact profile.  
* POST /contacts/{id}/notes  
  * **Capability:** Write (Append).  
  * **Application:** Commits structured, source-attributed internal notes (e.g., transcript extractions, pre-appointment brief contents, intake audit records).

### 

### **Communications & Automation Endpoints**

* POST /contacts/{id}/emails  
  * **Capability:** Write (Draft Queue).  
  * **Application:** Generates email content drafts in the realtor's verified voice and stages them inside the FUB native communication queue for manual human approval.  
* POST /contacts/{id}/sequences  
  * **Capability:** Write (Enrollment).  
  * **Application:** Enrolls a specific contact ID into an automated drip narrative or postcard tracking sequence.  
* POST /events  
  * **Capability:** Write (Logging).  
  * **Application:** Pushes historical or current timeline activity records back into the FUB timeline ledger.  
* GET /pipelines  
  * **Capability:** Read.  
  * **Application:** Resolves and maps the specific pipeline stage IDs and naming schemas configured in the brokerage architecture.

## 

## **3\. Data Architecture: Authoritative Schema Fields**

To maintain strict CRM hygiene, the AI agent must prioritize structured fields directly populated by FUB or integrations over loose metadata like text tags.

| Field Name | Data Source | Primary Functional Purpose for AI Agent |
| :---- | :---- | :---- |
| source | Native FUB Payload | The foundational entry channel (e.g., Zillow, Website) used to initialize strict lead-routing logic branches. |
| type | Auto-populated by FUB | Defines the primary customer persona segment: **Buyer**, **Seller**, or **Investor**. |
| stage | Bidirectional (Read/Write) | The system source of truth for funnel localization. Governs automations like the closed-transaction trigger. |
| customZipCodeOrigin | Custom Schema Field | Dedicated geographical string mapping used to replace messy legacy location text tags. |
| assignedTo | Account Context Filter | Strict operation scoping boundary; the AI agent restricts its execution window solely to leads assigned to the active realtor. |
| lastActivity | Automated FUB Metric | Tracks contact recency to optimize lead-scoring snapshots and prioritize proactive morning digests. |

## 

## **4\. Webhook Specification & Payload Triggers**

FUB pushes immediate, real-time JSON webhooks to the internal FastAPI gateway layer (POST /fub/webhook) to notify the multi-agent system of critical CRM events.

### **Security and Validation**

Inbound payloads carry a cryptographic shared signature hash in the `FUB-Signature` header. The gateway must Base64-encode the raw JSON payload (non-prettified), compute HMAC-SHA256 using the X-System-Key, and compare the result to the header value before passing the event payload to the async task queue.

### **Monitored Webhook Trigger Events**

* `peopleCreated`: Fired instantly upon new lead insertion. Launches the state machine transitions: RECEIVED → ENRICHING → ROUTING → ENROLLED → NOTIFIED.
* `peopleStageUpdated`: Monitored explicitly for pipeline shifts. Triggers the **Closed Transaction Workflow** if the updated stage matches a configured `closed_stage_ids` entry.
* `appointmentsCreated` / `appointmentsUpdated`: Intercepted for FUB-native appointments to build cross-system associations, verify client identity records, and schedule pre-appointment brief generation for T-24h. (These events do not fire for appointments synced from integrated calendars.)
* `peopleTagsCreated`: Analyzed to watch for intent shifts, micro-state changes, or specific campaign exposures.

## 

## **5\. Architectural Guardrails and UI Cleanup Rules**

* **Idempotency & Loop Control:** The ingestion layer must track incoming webhook IDs. If an update event is generated by the agent's own API key or service account, it must be dropped instantly to prevent an infinite loop of CRM modification webhooks.  
* **The Non-Send Restraint:** The agent has zero direct authorization or tool bindings to send transactional client-facing emails, texts, or WhatsApp messages autonomously. It is strictly limited to writing to the FUB draft queue via fub.create\_draft(), requiring explicit realtor signature authentication before execution.  
* **FUB Auto-Tagging Invalidation:** FUB's default account-level city/zip code extraction parsing features must be toggled off inside the administrator panel (Admin \> Tags \> uncheck City and Zip Code). Geography metrics must navigate directly through the structured customZipCodeOrigin model.  
* **External Payload Resilience:** Loose UI tags injected by external tools (e.g., Zillow Connected) that slip past the canonical \~60-tag taxonomy listed in tag\_taxonomy.csv must be ignored. The agent will fall back to reading the native, immutable source and type fields to preserve structured business processing logic.

