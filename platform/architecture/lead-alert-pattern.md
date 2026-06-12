### **Lead Alert — Feature Pattern**

**Feature name:** Lead Alert **Interface:** Telegram (inline keyboard) **Trigger:** New contact created in FUB (webhook: `new_contact`) **Target:** Ben Olsen only (assignedTo: user ID 1\)

---

#### **What it does**

When a new inbound lead arrives, the agent reads the contact from FUB, drafts a first-touch text message in Ben's voice, and sends Ben a structured Telegram notification within \~30 seconds. Ben sees everything he needs to make a judgment call, with three actions available in one tap.

---

#### **Telegram card format**

```
New lead — [Program Name]
[First Last] · [Phone Number]
via [lead source / domain]

"[Form notes or submission text, verbatim]"

Draft text:
"[Agent-drafted first-touch SMS in Ben's voice]"

[ APPROVE ]   [ EDIT ]   [ CALL [FIRST NAME] ]
```

---

#### **Button behavior**

**APPROVE** Saves the drafted text to the FUB contact as a note flagged for send. Sends Ben a Telegram confirmation. Does not autonomously send the SMS. Ben sends from FUB.

**EDIT** Prompts Ben in Telegram to type a revised message. On reply, saves revised text to FUB contact note. Sends Ben a confirmation.

**CALL \[FIRST NAME\]** Sends Ben a `tel:` link for the contact's phone number. One tap opens the native dialer. Logs a note to FUB that Ben requested a direct call.

---

#### **Fallback (30-minute window)**

If Ben doesn't respond within 30 minutes, the agent logs a note to the FUB contact: "Lead Alert draft unanswered — fallback sequence eligible." Sequence enrollment is triggered from that flag. The agent never goes silent; it never sends without approval.

---

#### **Post-call state management (known edge case, Sprint 2\)**

If Ben taps CALL and has a live conversation, the 30-minute fallback will still fire unless the system knows he called. FUB won't detect this automatically if Ben dials from his native phone rather than the FUB dialer.

**Designed solution:** After Ben taps CALL, the agent sends a follow-up ping:

```
Did you reach [First Name]?
[ REACHED ]   [ VOICEMAIL ]   [ NO ANSWER ]
```

Sequence enrollment and next-step logic branch from that response. This is deferred to Sprint 2 — build the three-button card first.

---

#### **Routing rule: not every lead gets this**

The agent reserves Lead Alert for inbound leads with real intent signals. Long-nurture contacts go straight to sequence without triggering the alert.

**Alert eligible:**

* Any inbound form submission from a BrightWork program landing page  
* Stage: Hot 90 Days or Call Requested  
* Any lead flagged with a transaction timeline under 6 months

**Goes straight to sequence (no alert):**

* Value Tracker / long-nurture contacts  
* Bulk imports  
* Referrals without a form submission

---

#### **Calendly / scheduling note**

No Calendly link in the agent-drafted first-touch text. The high-trust Lamorinda market treats an instant scheduling link as impersonal. Calendly belongs in second touches and long-nurture sequence emails, not the first message from Ben.

