# Agent Referral

Trigger: Tag agent-referral-lead applied when a colleague refers a contact to Ben
FUB stage: New Lead (buyer or seller — assign stage on enrollment based on contact type)
Action plan: Agent Referral
Exit conditions: Any reply (pause sequence, flag Ben), appointment booked, contact asks to stop (exit and tag do-not-contact), inbound call, call 2+ minutes, stage change to Engaged / Listing Appointment / Active Seller / Active Buyer / Closed
Nurture handoff: Day 21 moves contact to general nurture (buyer or seller path per contact type). Not a dead lead.
HTML email: seller-programs-v2.html (seller path) / buyer-programs-v2.html (buyer path) at Day 10, campaign slug agent-referral
Special: Dual-path sequence. Use contact type (buyer/seller) to select the correct path at enrollment. Day 0 includes a conditional note for path assignment. Ben adds the referring agent's name to Day 0 copy before send.

---

| Step | Day | Channel | Executed by | Purpose |
|------|-----|---------|-------------|---------|
| 0a | 0 | Email | CoS drafts, Ben approves via Telegram [TELEGRAM APPROVAL REQUIRED - PATH A / FUB AUTO - PATH B] | First touch, acknowledge referral bridge, no Calendly |
| 0b | 0 | SMS | Ben pastes into FUB [BEN PASTES — CoS drafts, Ben approves via Telegram] | Short intro, Ben calling shortly |
| 2 | 2 | Email | FUB auto | Low-pressure follow-up, brief capability, soft next step |
| 4 | 4 | SMS | Ben pastes into FUB [BEN PASTES — CoS drafts, Ben approves via Telegram] | Human check-in, not a follow-up pitch |
| 7 | 7 | Email | FUB auto | One program door by type, curiosity only |
| 10 | 10 | Email (HTML) | FUB auto | Program overview by type + Calendly |
| 14 | 14 | Email | FUB auto | Light market context + Calendly |
| 21 | 21 | Email | FUB auto | Graceful exit, door open, nurture handoff |

---

## Path Assignment Note

At enrollment, confirm contact type and apply the correct path for all conditional steps (0a, 7, 10, 14, 21). Ben inserts the referring agent's name into Step 0a and Step 0b before approval. Do not name the referring agent in automated steps after Day 0.

---

## Step 0a — Day 0 Email

CoS drafts, Ben approves via Telegram [TELEGRAM APPROVAL REQUIRED - PATH A / FUB AUTO - PATH B]

Ben adds referring agent name before send. No Calendly on Day 0. Ben calls directly.

### Seller path

**Subject:** [Referring agent name] suggested we connect

Hi [first name],

[Referring agent name] reached out and thought we should talk. I take those introductions seriously. When another agent sends someone my way, I know they've put their own reputation on the line, and I want to earn that.

I'm Ben Olsen with BrightWork Realty Advocates. I've worked in Lamorinda and the East Bay since 2004, and I spend most of my time helping homeowners think through timing, preparation, and what a sale would actually look like before anyone commits to a listing.

I'd rather understand your situation first than send you a stack of options. I'll give you a call shortly. If you'd rather reach me first, I'm at (925) 255-9727.

### Buyer path

**Subject:** [Referring agent name] suggested we connect

Hi [first name],

[Referring agent name] reached out and thought we should talk. I take those introductions seriously. When another agent sends someone my way, I know they've put their own reputation on the line, and I want to earn that.

I'm Ben Olsen with BrightWork Realty Advocates. I've worked in Lamorinda and the East Bay since 2004, and I help buyers who want someone local who knows these neighborhoods well and won't rush them into the wrong property.

I'd rather understand what you're looking for first than send you a list of listings. I'll give you a call shortly. If you'd rather reach me first, I'm at (925) 255-9727.

---

## Step 0b — Day 0 SMS

[BEN PASTES — CoS drafts, Ben approves via Telegram]

Ben replaces [referrer] with the referring agent's first name before sending.

Hi [first name], it's Ben Olsen with BrightWork, [referrer] mentioned we should connect, calling you shortly.

---

## Step 2 — Day 2 Email

FUB auto-sends. Assume no response to Day 0.

### Seller path

**Subject:** Still here when you're ready

Hi [first name],

I tried reaching you after that introduction and wanted to follow up once more without filling your inbox.

Most sellers I work with through referrals already have a clear reason to move. What they usually need is someone who knows this market well enough to walk through the options calmly: timing, preparation, and whether a public launch or a more private approach makes sense for their situation.

I'm not going to push you toward a listing agreement. I'd rather have a real conversation and see if I'm the right fit.

https://calendly.com/ben-brightwork/selling?utm_source=fub&utm_medium=email&utm_campaign=agent-referral&utm_content=day2

Or reply here and we'll find a time that works.

### Buyer path

**Subject:** Still here when you're ready

Hi [first name],

I tried reaching you after that introduction and wanted to follow up once more without filling your inbox.

Most buyers I work with through referrals already know roughly where they want to be. What they usually need is someone who knows Lamorinda well enough to help them evaluate neighborhoods, timing, and what a competitive offer actually looks like here without rushing them.

I'm not going to send you a generic list of what's on Zillow. I'd rather understand what you're trying to accomplish and see if I can help.

https://calendly.com/ben-brightwork/buying?utm_source=fub&utm_medium=email&utm_campaign=agent-referral&utm_content=day2

Or reply here and we'll find a time that works.

---

## Step 4 — Day 4 SMS

[BEN PASTES — CoS drafts, Ben approves via Telegram]

### Seller path

Hi [first name], Ben Olsen at BrightWork. Just checking in after [referrer]'s intro. No rush on my end, happy to talk whenever timing works. (925) 255-9727

### Buyer path

Hi [first name], Ben Olsen at BrightWork. Just checking in after [referrer]'s intro. No rush on my end, happy to talk whenever timing works. (925) 255-9727

---

## Step 7 — Day 7 Email

FUB auto-sends. One program mention only in the entire plain-text cadence. Curiosity only — no explanation.

### Seller path

**Subject:** One thing worth knowing about

Hi [first name],

I haven't heard back, and that's fine. I'll keep this short.

Some homeowners in your position want to understand whether a Quiet Listing makes sense before anything goes public. It's not the right fit for everyone, but when it is, it's worth knowing about.

https://quiet.brightworkrealty.com?utm_source=fub&utm_medium=email&utm_campaign=quiet-listing&utm_content=day7

If you'd rather just talk it through, I'm easy to reach at (925) 255-9727.

### Buyer path

**Subject:** One thing worth knowing about

Hi [first name],

I haven't heard back, and that's fine. I'll keep this short.

Some buyers in your position want early access to homes that never hit the public portals. Off-Market Access is worth a look if that's the kind of edge you're trying to build.

https://offmarket.brightworkrealty.com?utm_source=fub&utm_medium=email&utm_campaign=off-market&utm_content=day7

If you'd rather just talk it through, I'm easy to reach at (925) 255-9727.

---

## Step 10 — Day 10 Email (HTML Program Overview)

FUB auto-sends

**Subject:** A few programs worth knowing about

### Seller path

**Template:** `realtors/ben-olsen/sequences/templates/seller-programs-v2.html`

Rendered HTML email. Campaign slug: agent-referral. All links use utm_campaign=agent-referral and utm_content=day10.

Calendly CTA: https://calendly.com/ben-brightwork/selling?utm_source=fub&utm_medium=email&utm_campaign=agent-referral&utm_content=day10

### Buyer path

**Template:** `realtors/ben-olsen/sequences/templates/buyer-programs-v2.html`

Rendered HTML email. Campaign slug: agent-referral. All links use utm_campaign=agent-referral and utm_content=day10.

Calendly CTA: https://calendly.com/ben-brightwork/buying?utm_source=fub&utm_medium=email&utm_campaign=agent-referral&utm_content=day10

---

## Step 14 — Day 14 Email

FUB auto-sends. Light market context + Calendly.

### Seller path

**Subject:** What's happening in Lamorinda right now

Hi [first name],

Quick note on the market here, since context matters when you're thinking about timing.

Lamorinda inventory is still tight relative to demand, but buyers are more selective than they were two years ago. Homes that show well and are priced with current comps in mind are moving. Homes that need work or are priced on last year's numbers tend to sit longer, and days on market becomes part of the story whether you want it to or not.

None of that means rush. It means when you do decide to move, the preparation and positioning matter more than they used to.

Happy to talk through what that would look like for your specific situation:

https://calendly.com/ben-brightwork/selling?utm_source=fub&utm_medium=email&utm_campaign=agent-referral&utm_content=day14

### Buyer path

**Subject:** What's happening in Lamorinda right now

Hi [first name],

Quick note on the market here, since context matters when you're looking.

Lamorinda inventory is still limited, but buyers have more room to be selective than they did at the peak. Well-prepared homes in Lafayette, Moraga, and Orinda are still attracting serious interest. Properties that need significant work or are priced above what recent comps support tend to sit, which gives buyers more leverage when they do find the right fit.

None of that means wait forever. It means knowing what you're looking for and being ready to move when the right property surfaces matters.

Happy to talk through what that looks like for your search:

https://calendly.com/ben-brightwork/buying?utm_source=fub&utm_medium=email&utm_campaign=agent-referral&utm_content=day14

---

## Step 21 — Day 21 Email

FUB auto-sends. Sequence ends, general nurture begins.

### Seller path

**Subject:** I'll step back for now

Hi [first name],

I've reached out a few times since we were introduced and haven't been able to connect. I'm going to step back rather than keep filling your inbox.

Referrals like this don't expire. When the timing shifts and you're closer to a decision about selling, I'm easy to find. And if you'd rather stay informed on what's actually happening in the market near you, I send periodic updates to homeowners who've asked. No pitch, just useful context from someone who knows this area well.

https://calendly.com/ben-brightwork/selling?utm_source=fub&utm_medium=email&utm_campaign=agent-referral&utm_content=day21

### Buyer path

**Subject:** I'll step back for now

Hi [first name],

I've reached out a few times since we were introduced and haven't been able to connect. I'm going to step back rather than keep filling your inbox.

Referrals like this don't expire. When the timing shifts and you're ready to get serious about your search, I'm easy to find. And if you'd rather stay informed on what's coming to market in Lamorinda before it hits the portals, that's something we can set up too.

https://calendly.com/ben-brightwork/buying?utm_source=fub&utm_medium=email&utm_campaign=agent-referral&utm_content=day21
