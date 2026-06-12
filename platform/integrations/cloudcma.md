## **CloudCMA Documentation** 

## **1\. Interactive Report Deep-Link Factory (The Presentation Layer)**

Instead of manually scraping MLS boards, your **Draft & Communication Agent** or **Supervisor Agent** can generate 1-click configuration URLs for the realtor. If the realtor is logged into their browser, clicking these links bypasses the setup workflow and routes them directly to a pre-populated generation page.

### **Endpoints and URL Construction**

* **Create a Comparative Market Analysis (CMA):**  
  GET \[https://cloudcma.com/cmas/new\](https://cloudcma.com/cmas/new)  
* **Create a Buyer Tour:**  
  GET \[https://cloudcma.com/tours/new\](https://cloudcma.com/tours/new)  
* **Create a Property Report:**  
  GET \[https://cloudcma.com/properties/new\](https://cloudcma.com/properties/new)  
* **Create a Flyer:**  
  GET \[https://cloudcma.com/flyers/new\](https://cloudcma.com/flyers/new)

### **Core Input Query Parameters**

* mlsnums (Required for Tours/Flyers): A comma-separated string of MLS identifiers (e.g., 12345,12346).  
* address (Required for Address-based CMAs/Properties): The full street address string.  
* title (Optional): Branded header name for the package (e.g., The Smith Family).  
* notes (Optional): Internal textual context injected directly into the report dashboard.  
* prop\_type (Optional): Specific RETS property mapping definition (e.g., RES for Residential).

## **2\. Background Tool: Fully Automated "Quick CMA" API**

For the **Lead Intake & Router Agent**, you can use Cloud CMA’s background widget endpoint to generate and deliver branded reports entirely via API without human intervention.

HTTP

```
POST/GET https://cloudcma.com/cmas/widget
```

### **Parameter Reference Matrix**

| Parameter Name | Data Type | Requirement Style | Functional Purpose for AI Agent |
| :---- | :---- | :---- | :---- |
| api\_key | String | **Required** | The unique user Cloud CMA API Key (Settings \> API). |
| address | String | **Required** | The absolute target consumer property address. |
| name | String | Optional | Consumer's full name to brand across the system context. |
| email\_to | String | Optional | Target recipient email. **Crucial Guardrail:** If left completely blank, Cloud CMA completely suppresses its own outbound email delivery engine. |
| sqft / beds / baths | Integer/Float | Optional | Structural metadata overrides to refine comings/goings matching. |
| months\_back | Integer | Optional | Timeline constraint window for comparables (Default: 12). |
| callback\_url | String | **Highly Recommended** | Unique endpoint on your FastAPI gateway where Cloud CMA will issue an async POST webhook once the PDF finishes publishing. |
| job\_id | String | Optional | Custom internal tracking UUID passed along to map back into the webhook receiver data layer. |

## **3\. The Homebeat Re-Engagement Framework**

Cloud CMA features an automation layer called **Homebeats**. This tool pushes recurring real-time valuation updates to past clients or nurturing targets at a set frequency (e.g., monthly or quarterly), maintaining the client relationship automatically.

HTTP

```
POST https://cloudcma.com/homebeats/widget
```

### **Critical Integration Fields**

* frequency (Required): The execution window string configuration.  
* welcome\_email (Optional): Can be toggled to false if your AI agent handles the client onboarding messaging sequence internally.  
* callback\_url (Optional): Directs Cloud CMA to notify your system rather than broadcasting updates directly to the client. This is ideal if you want the agent to preview the market data, wrap it in a custom text, and send it directly via Telegram.

## **4\. Inbound Webhook Design (FastAPI Gateway)**

When your agent triggers an automated CMA via the callback\_url parameter, Cloud CMA will send an asynchronous payload to your API gateway when execution finishes.

### **Expected Cloud CMA Postback Payload**

JSON

```
{
  "job_id": "cma_brief_job_8349201",
  "status": "success",
  "pdf_url": "https://cloudcma.com/reports/download/a1b2c3d4e5f6.pdf",
  "view_url": "https://cloudcma.com/presentations/a1b2c3d4e5f6",
  "address": "123 Main St, Moraga, CA 94556"
}
```

### **Multi-Agent Routing Flow Upon Postback Ingestion**

1. **Gateway Capture:** Validates the inbound payload and matches the job\_id to an internal fub\_contact\_id stored in the state database.  
2. **FUB Sync:** The agent uses POST /contacts/{id}/notes to write a structured note directly to Follow Up Boss containing the pdf\_url and view\_url assets.  
3. **Telegram Briefing:** The **Supervisor Agent** pings Ben on Telegram:  
   📊 **CMA Complete:** Cloud CMA finished publishing the automated evaluation report for **123 Main St**. The PDF is attached to the client's FUB profile. Tap below to view or approve the follow-up draft.

## **5\. Pydantic Schema Contracts (schemas/property.py)**

To ensure clean parameters are passed to your background API execution blocks, you can add these contracts to your development repository:

Python

```
from pydantic import BaseModel, Field, HttpUrl
from typing import Optional

class QuickCMARequest(BaseModel):
    api_key: str = Field(..., description="The realtor's specific Cloud CMA validation key.")
    address: str = Field(..., description="Authoritative standardized street address string.")
    name: Optional[str] = Field(None, description="Full name of target lead client.")
    email_to: Optional[str] = Field(None, description="If blank, forces Cloud CMA email suppression.")
    sqft: Optional[int] = Field(None, description="Gross living area matching override metric.")
    beds: Optional[int] = Field(None, description="Total bedrooms filter parameter.")
    baths: Optional[float] = Field(None, description="Total bathrooms filter parameter.")
    callback_url: Optional[HttpUrl] = Field(None, description="Internal FastAPI gateway listener link.")
    job_id: Optional[str] = Field(None, description="Correlation identifier tracking code.")

class CloudCMAPostbackPayload(BaseModel):
    job_id: str = Field(..., description="The matching internal system tracking task key.")
    status: str = Field(..., description="Publish result status criteria flag.")
    pdf_url: HttpUrl = Field(..., description="Direct storage link asset containing the print version report.")
    view_url: HttpUrl = Field(..., description="Direct interactive live link presentation console link.")
```

Since Cloud CMA can completely suppress outward-facing emails if email\_to is left blank, your AI agent can take complete control over how data is packaged and sent to the client.

How should the agent handle a scenario where Cloud CMA cannot find matching MLS comps for an address—should it fall back to creating an internal FUB alert for manual realtor compilation, or notify the realtor immediately over Telegram?

