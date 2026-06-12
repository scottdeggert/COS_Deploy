Tag Taxonomy for use within the agent

\# brightwork\_tag\_taxonomy.yaml  
\# Source of truth for BrightWork CoS agent tag interpretation  
\# Last updated: June 2026 (updated with new sequence trigger tags)  
\# Scope: Ben Olsen contacts only (assignedTo: Ben Olsen)  
\# Policy: Agent reads structured fields (source, type, stage) first.  
\#         Tags are supplementary signal only.

tags:

  \# ── CONTACT CLASSIFICATION ───────────────────────────────────────────────  
  \- tag: "Buyer"  
    source: fub\_auto  
    description: \>  
      Applied automatically by FUB when a lead arrives with buyer intent.  
      Redundant with the structured \`type\` field. Agent should read \`type\`,  
      not this tag, for contact classification. Do not use as primary signal.

  \- tag: "Seller"  
    source: fub\_auto  
    description: \>  
      Applied automatically by FUB for seller-intent leads.  
      Same redundancy caveat as \`Buyer\`. Read \`type\` field instead.

  \- tag: "Seller Lead"  
    source: mcc\_landing\_page  
    description: \>  
      Applied via MCC landing page form submission. Indicates the contact  
      self-identified as a potential seller through the MCC tool flow.  
      More specific than the generic \`Seller\` tag.

  \- tag: "Future seller"  
    source: manual  
    description: \>  
      Manually applied by Ben. Contact has expressed long-horizon seller  
      intent but is not actively listing. Nurture candidate.

  \# ── MCC LANDING PAGE ─────────────────────────────────────────────────────  
  \# All tags beginning with "MCC" or matching MCC form field values  
  \# originate from the Moraga Country Club Value Estimator landing page.

  \- tag: "MCC Estimator"  
    source: mcc\_landing\_page  
    description: \>  
      Contact submitted the MCC Home Value Estimator form. Indicates  
      seller intent in the MCC/Moraga area. Primary trigger for the  
      MCC Value Estimator sequence.

  \- tag: "mcc-report-request"  
    source: mcc\_landing\_page  
    description: \>  
      Applied when contact requests the full MCC comparable report.  
      Higher-intent signal than MCC Estimator alone.

  \- tag: "Floor Plan: Plan 1"  
    source: mcc\_landing\_page  
    description: MCC form response — contact identified their home as Plan 1\.

  \- tag: "Floor Plan: Plan 2"  
    source: mcc\_landing\_page  
    description: MCC form response — contact identified their home as Plan 2\.

  \- tag: "Floor Plan: Plan 4"  
    source: mcc\_landing\_page  
    description: MCC form response — contact identified their home as Plan 4\.

  \- tag: "Floor Plan: Plan 12"  
    source: mcc\_landing\_page  
    description: MCC form response — contact identified their home as Plan 12\.

  \- tag: "Floor Plan: Plan 13 Expanded"  
    source: mcc\_landing\_page  
    description: MCC form response — contact identified their home as Plan 13 Expanded.

  \- tag: "Floor Plan: Sequoyah"  
    source: mcc\_landing\_page  
    description: MCC form response — contact identified their home as Sequoyah plan.

  \- tag: "plan-3"  
    source: mcc\_landing\_page  
    description: \>  
      MCC form response — kebab-case variant for Plan 3\. Note naming  
      inconsistency with title-case Floor Plan tags. Treat as equivalent.

  \- tag: "Value Tracker"  
    source: mcc\_landing\_page  
    description: \>  
      Contact opted into ongoing home value tracking via the MCC tool.  
      Indicates ongoing engagement intent, not just a one-time inquiry.

  \# ── PIPELINE INTENT ───────────────────────────────────────────────────────  
  \- tag: "Call Requested"  
    source: mcc\_landing\_page  
    description: \>  
      Contact requested a call via MCC form. Highest-intent signal from  
      the MCC flow. Should trigger immediate follow-up alert to Ben.

  \- tag: "Hot 90 Days"  
    source: manual  
    description: \>  
      Manually applied. Contact is actively buying or selling within  
      90 days. Priority for direct outreach.

  \- tag: "Warm 6-12 Months"  
    source: manual  
    description: \>  
      Manually applied. Contact has expressed intent in the 6-12 month  
      window. Mid-priority nurture.

  \- tag: "off-market-lead"  
    source: landing\_page  
    description: \>  
      Applied via off-market inquiry landing page. Contact expressed  
      interest in off-market buying or selling. Canonical form for all  
      off-market landing page conversions.  
      (Supersedes: "Off-Market Candidate", "Off-Market Landing Page")

  \- tag: "Pre-Sale Reno"  
    source: mcc\_landing\_page  
    description: \>  
      Contact indicated interest in pre-sale renovation services via  
      MCC form. Signals seller intent with a renovation timeline need.

  \- tag: "Buy Before Sell"  
    source: mcc\_landing\_page  
    description: \>  
      Contact indicated they need to buy before selling their current  
      home. Signals a dual-transaction opportunity.

  \# ── PROGRAM / SEQUENCE ENROLLMENT ────────────────────────────────────────  
  \- tag: "Program: General Website Inquiry Campaign"  
    source: fub\_sequence  
    description: \>  
      Applied by FUB when contact enters the General Website Inquiry  
      email sequence. Indicates contact is currently in active nurture.  
      Not a manual tag — do not remove.

  \- tag: "Program: Online Leads \- Buyer Email Campaign"  
    source: fub\_sequence  
    description: \>  
      Applied by FUB when contact enters the Online Buyer Leads email  
      sequence. Same policy as above.

  \- tag: "New Inquiries"  
    source: fub\_auto  
    description: \>  
      Applied when a new inbound inquiry arrives. Workflow routing tag.  
      Used to trigger initial response logic. Should age off once contact  
      is worked.

  \- tag: "SeniorWorkshop"  
    source: event\_registration  
    description: \>  
      Contact attended or registered for Ben's Senior Workshop event.  
      Segment for senior-specific nurture and follow-up.

  \- tag: "investment-inquiry"  
    source: landing\_page  
    description: \>  
      Applied via invest.brightworkrealty.com form submission.  
      Contact expressed interest in real estate investing with  
      Ben. Primary trigger for the Real Estate Investing sequence.  
      NOTE: Tag not yet wired in the Cloudflare proxy worker —  
      confirm bw-fub-proxy applies this tag before agent launch.

  \- tag: "agent-referral-lead"  
    source: manual\_or\_fub\_workflow  
    description: \>  
      Applied when a contact is referred to Ben by another agent.  
      High trust, high intent signal. Primary trigger for the  
      Agent Referral sequence. May be applied manually by Ben  
      or via a FUB workflow on leads with source = Referral.

  \- tag: "portal-seller-lead"  
    source: fub\_workflow  
    description: \>  
      Applied to seller leads arriving from real estate portals  
      other than Zillow (Realtor.com, Homes.com, etc.). Primary  
      trigger for the Portal Seller sequence. Applied via FUB  
      workflow based on source field value.

  \- tag: "portal-buyer-lead"  
    source: fub\_workflow  
    description: \>  
      Applied to buyer leads arriving from real estate portals  
      other than Zillow (Realtor.com, Homes.com, etc.). Primary  
      trigger for the Portal Buyer sequence. Applied via FUB  
      workflow based on source field value.

  \# ── IMPORT / BATCH ────────────────────────────────────────────────────────  
  \- tag: "Import"  
    source: manual\_import  
    description: \>  
      Applied to all batch-imported contacts. Indicates record did not  
      originate from an inbound lead. No behavioral signal — use only  
      to identify import-origin contacts.

  \- tag: "Corliss Neighbors"  
    source: manual\_import  
    description: \>  
      Neighborhood canvass batch imported June 2026 — homeowners on or  
      near Corliss Drive, Moraga. No active outreach. Contacts may receive  
      direct mail and digital ads. Agent should not enroll in email  
      sequences without explicit Ben approval. Flag if contact becomes  
      inbound lead.

  \# ── VIP / RELATIONSHIP ────────────────────────────────────────────────────  
  \# These tags are Ben's manual designations for relationship-tier contacts.  
  \# They are inclusion signals, not pipeline or suppression signals.  
  \# The agent uses these to qualify contacts for event invitations,  
  \# personalized direct mail, and any outreach Ben initiates rather than  
  \# responds to. Always check for Unsubscribed or \#NeverMail before acting.

  \- tag: "\#HitList"  
    source: manual  
    description: \>  
      Ben's personal VIP list. Contacts he actively wants to reach —  
      friends, past clients, sphere influencers, and community relationships  
      he cultivates directly. Primary use cases: open house invitations,  
      special event invites, personalized postcards, and personal text or  
      call outreach from Ben. This list is maintained manually by Ben and  
      should never be auto-populated by imports or platform integrations.  
      When Ben has an open house or event, this list is the first audience  
      to notify. Agent should surface \#HitList contacts as a named segment  
      for any direct mail, event invite, or personal outreach task.  
      Always cross-check against Unsubscribed and \#NeverMail before  
      including in any campaign send.

  \- tag: "\#AlwaysMail"  
    source: manual  
    description: \>  
      Ben's personal override tag. Contact should always receive  
      direct mail regardless of other suppression signals.

  \# ── DELIVERABILITY / SUPPRESSION ─────────────────────────────────────────  
  \- tag: "Unsubscribed"  
    source: fub\_auto  
    description: \>  
      Contact opted out of email. Hard suppression. Agent must never  
      enroll this contact in any email sequence. Check before any  
      outreach action.

  \- tag: "Bounced"  
    source: fub\_auto  
    description: \>  
      Email address has bounced. Do not send email. Flag for data  
      cleanup if no alternate email exists.

  \- tag: "\#NeverMail"  
    source: manual  
    description: \>  
      Hard suppression for direct mail. Do not add to any mail list.

  \# ── AUTH / PLATFORM ───────────────────────────────────────────────────────  
  \- tag: "Google Sign-On"  
    source: website\_platform  
    description: \>  
      Contact authenticated via Google SSO on the BrightWork or MCC  
      website. Indicates a real email address was verified. Mild  
      engagement signal.

  \# ── ZILLOW-INJECTED (READ-ONLY, DO NOT ACT ON) ───────────────────────────  
  \# These tags are written directly by Zillow's API and cannot be  
  \# intercepted or renamed. Agent ignores these tags and reads the  
  \# structured \`source\` field instead to identify Zillow leads.

  \- tag: "Zillow Connected"  
    source: zillow\_api  
    description: Zillow API injection. Read \`source\` field instead.

  \- tag: "Zillow Property Tour"  
    source: zillow\_api  
    description: Contact requested a property tour via Zillow.

  \- tag: "Zillow High Intent Buyer"  
    source: zillow\_api  
    description: Zillow behavioral classification.

  \- tag: "Zillow likely Homeowner"  
    source: zillow\_api  
    description: Zillow behavioral classification.

  \- tag: "Zillow likely Mortgage Submitter"  
    source: zillow\_api  
    description: Zillow behavioral classification.

  \- tag: "Zillow specific Home Interest"  
    source: zillow\_api  
    description: Zillow behavioral classification.

  \- tag: "Zillow browsing New Area"  
    source: zillow\_api  
    description: Zillow behavioral classification.

  \- tag: "Zillow reengaged Buyer"  
    source: zillow\_api  
    description: Zillow behavioral classification.

  \- tag: "Zillow Smart List"  
    source: zillow\_api  
    description: Zillow behavioral classification.

  \- tag: "Zillow high Intent Seller"  
    source: zillow\_api  
    description: Zillow behavioral classification.

  \- tag: "Zillow real Time Tour"  
    source: zillow\_api  
    description: Zillow behavioral classification.

  \- tag: "Zillow zhl Status: No Longer Active"  
    source: zillow\_api  
    description: Zillow Home Loans pipeline status.

  \- tag: "ZHL Transferred"  
    source: zillow\_api  
    description: Contact transferred within Zillow Home Loans workflow.

  \- tag: "ZHL Opportunity"  
    source: zillow\_api  
    description: Zillow Home Loans opportunity flag.

  \# ── CITY/LOCATION (NOISE — IGNORE) ────────────────────────────────────────  
  \# These tags remain on Zillow-sourced contacts from Zillow's browsing  
  \# data payload. They represent areas the contact searched, not where  
  \# they live or intend to buy. Geography is read from \`customZipCodeOrigin\`.  
  \# Agent ignores all city-name tags.  
  \# Examples: ORINDA, WALNUT CREEK, MORAGA, Lafayette, Oakland, ALAMO,  
  \# CONCORD, DANVILLE, BERKELEY, and dozens of out-of-area city names.

