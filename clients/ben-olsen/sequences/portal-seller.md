# Portal Seller

Trigger: Tag portal-seller-lead applied on seller inquiry from Realtor.com, Homes.com, or comparable listing portals
FUB stage: New Seller Lead
Action plan: Portal Lead (upgrade to Seller Strategy if intent confirmed)
Exit conditions: Any reply, inbound call, call 2+ minutes, stage change to Engaged / Listing Appointment / Active Seller. Pause-on-response on all email steps.
Nurture handoff: Day 30 moves to 90-day seller nurture, quarterly homeowner market update, no more call tasks
HTML email: seller-programs-v2.html at Day 10, campaign slug portal-seller
Calendly link: https://calendly.com/ben-brightwork/selling

---

<!-- CALENDLY BUTTON SPEC
Label: Meet with Ben
Background: #00aedb
Text color: #ffffff
Padding: 14px 32px
Border-radius: 3px
Font: Arial, sans-serif, 15px, bold
URL pattern: https://calendly.com/ben-brightwork/selling?utm_source=fub&utm_medium=email&utm_campaign=portal-seller&utm_content=day{N}
-->


| Step | Day | Channel | Executed by | Purpose |
|------|-----|---------|-------------|---------|
| 1a | 1 | Email | CoS drafts, Ben approves via Telegram [TELEGRAM APPROVAL REQUIRED - PATH A / FUB AUTO - PATH B] | First touch, no Calendly |
| 1b | 1 | SMS | Ben pastes into FUB [BEN PASTES — CoS drafts, Ben approves via Telegram] | Immediate follow |
| 1c | 1 | Task: Call | Ben | First call attempt |
| 1d | 1 | Task: Call | Ben | Second call attempt, 2+ hrs later |
| 1a | 2 | Email | FUB auto | Private buyer network + Calendly |
| 1b | 1 | Task: Call | Ben | Third call attempt |
| 2 | 2 | SMS | Ben pastes into FUB [BEN PASTES — CoS drafts, Ben approves via Telegram] | Low-friction check-in |
| 3a | 4 | Email | FUB auto | Timeline, Buy Before You Sell, BrightFlip + Calendly |
| 3b | 3 | Task: Call | Ben | Fourth call attempt |
| 5 | 6 | Email | FUB auto | How Ben approaches a listing + Calendly |
| 7a | 7 | SMS | Ben pastes into FUB [BEN PASTES — CoS drafts, Ben approves via Telegram] | Re-engagement |
| 7b | 8 | Email | FUB auto | Market context, Final Offer + Calendly |
| 7c | 7 | Task: Call | Ben | Fifth call attempt |
| 10 | 11 | Email (HTML) | FUB auto | HTML program overview |
| 14a | 15 | Email | FUB auto | Final active pursuit + Calendly |
| 14b | 14 | Task: Call | Ben | Sixth and final call attempt |
| 30 | 31 | Email | FUB auto | Nurture transition + Calendly |

---

## Step 1a — Day 1 Email
FUB auto-sends
Pause-on-response: ON

Subject: Your home value question

Hi %contact_first_name%,

I'll call you today. A real read on your home's value in this market takes more than an algorithm, especially in Lamorinda where condition, floor plan, and timing shift the number in ways the data models don't capture.

If you'd rather start in writing, just reply with a bit about the property.

## Step 1b — Day 1 SMS

[REPLACE WITH FUB-NATIVE EMAIL — PENDING]
[BEN PASTES — CoS drafts, Ben approves via Telegram]

Hi %contact_first_name%, this is Ben Olsen at BrightWork. Just sent you an email about your home's value. Happy to walk through what's happening in your area. (925) 255-9727

---

## Step 1c — Day 1 Task: Call

First attempt. Ben calls within the hour.

---

## Step 1d — Day 1 Task: Call

Second attempt. Schedule 2+ hours after first call.

---

## Step 1a — Day 2 Email

FUB auto-sends

**Subject:** A few things worth knowing about this area

Hi %contact_first_name%,

I tried to reach you yesterday. Still happy to connect when the timing works.

One thing worth mentioning: some of the most interesting options in this market never hit the public portals, or they show up there late. I keep a private list of serious, pre-qualified buyers — many of them relocating from San Francisco and the broader Bay Area — who have opted in specifically for Lamorinda properties. When a home becomes available, they hear about it before anything goes public.

For the right seller, that matters. No days-on-market pressure, no public countdown clock, and sometimes a cleaner transaction than a full MLS launch would have produced.

If you'd like to understand whether that applies to your home, or just want a real read on what your property would do in the current market, you can find time on my calendar below.

<table cellpadding="0" cellspacing="0" role="presentation" style="margin-top:24px;margin-bottom:8px;">
  <tr>
    <td style="background-color:#00aedb;border-radius:3px;">
      <a href="https://calendly.com/ben-brightwork/selling?utm_source=fub&utm_medium=email&utm_campaign=portal-seller&utm_content=day1" style="display:inline-block;color:#ffffff;font-family:Arial,sans-serif;font-size:15px;font-weight:700;letter-spacing:0.5px;text-decoration:none;padding:14px 32px;">Meet with Ben</a>
    </td>
  </tr>
</table>

Or call me directly at (925) 255-9727.

---

## Step 1b — Day 1 Task: Call

Third attempt.

---

## Step 2 — Day 2 SMS

[REPLACE WITH FUB-NATIVE EMAIL — PENDING]
[BEN PASTES — CoS drafts, Ben approves via Telegram]

Hey %contact_first_name%, Ben Olsen here. Still happy to give you a real read on your home's value. No obligation, just a conversation. (925) 255-9727

---

## Step 3a — Day 4 Email

FUB auto-sends

**Subject:** Quick question about your timeline

Hi %contact_first_name%,

I don't want to keep reaching out if the timing isn't right. Let me just ask directly.

Are you thinking about a move in the next six months, or is this more of a longer-term question? And is there a complicating factor — like needing to buy your next place before you can actually list this one?

That situation comes up a lot in this market, and there are ways to structure it so you're not stuck making a contingent offer or bridging two transactions at once. It's worth understanding your options before you assume it has to be complicated.

Separately: is there work the home needs before it would be ready to show? I work with BrightFlip for sellers who want to address deferred maintenance or cosmetic updates before listing but don't want to pay out of pocket before the sale closes. We look at the numbers first and only recommend it when the math actually makes sense.

If any of that is relevant to your situation, it's worth a conversation. You can find time on my calendar below.

<table cellpadding="0" cellspacing="0" role="presentation" style="margin-top:24px;margin-bottom:8px;">
  <tr>
    <td style="background-color:#00aedb;border-radius:3px;">
      <a href="https://calendly.com/ben-brightwork/selling?utm_source=fub&utm_medium=email&utm_campaign=portal-seller&utm_content=day3" style="display:inline-block;color:#ffffff;font-family:Arial,sans-serif;font-size:15px;font-weight:700;letter-spacing:0.5px;text-decoration:none;padding:14px 32px;">Meet with Ben</a>
    </td>
  </tr>
</table>

Or just reply to this email and we'll go from there.

---

## Step 3b — Day 3 Task: Call

Fourth attempt.

---

## Step 5 — Day 6 Email

FUB auto-sends

**Subject:** How we prepare a listing differently

Hi %contact_first_name%,

Most listings go to market hoping the best offer shows up. The photos go up, the price goes in, and everyone waits to see what the buyer's inspection turns up.

We work the other direction. Before anything is listed, I do a forensic review — what's the realistic pricing story for this property, what condition issues are worth addressing, what's missing from the presentation, and what the right portal strategy looks like. For homes that previously sat on the market without selling, that review usually identifies something specific that went wrong. It's rarely just the price.

A few things I bring to listings that most agents don't: premium placement on the major portals where buyers actually search, 3D tours for out-of-area buyers, and Final Offer — a platform that creates real-time transparency among competing buyers for listings where I expect strong multi-offer interest. None of these are standard for every home. They're decisions I make based on the specific property and what the market is doing at that moment.

If you want to understand what a real strategy would look like for your home, you can find time on my calendar below.

<table cellpadding="0" cellspacing="0" role="presentation" style="margin-top:24px;margin-bottom:8px;">
  <tr>
    <td style="background-color:#00aedb;border-radius:3px;">
      <a href="https://calendly.com/ben-brightwork/selling?utm_source=fub&utm_medium=email&utm_campaign=portal-seller&utm_content=day5" style="display:inline-block;color:#ffffff;font-family:Arial,sans-serif;font-size:15px;font-weight:700;letter-spacing:0.5px;text-decoration:none;padding:14px 32px;">Meet with Ben</a>
    </td>
  </tr>
</table>

---

## Step 7a — Day 7 SMS

[REPLACE WITH FUB-NATIVE EMAIL — PENDING]
[BEN PASTES — CoS drafts, Ben approves via Telegram]

Hi %contact_first_name%, Ben here. I've sent a few notes about your home's value and haven't been able to connect. Still happy to talk through it when the time is right. (925) 255-9727

---

## Step 7b — Day 8 Email

FUB auto-sends

**Subject:** What's actually happening near your home right now

Hi %contact_first_name%,

The market in [neighborhood/area] has shifted over the last 90 days in ways that affect what your home would realistically sell for and how long it would take. I can put together a quick look at what's closed nearby, what's sitting, and how offers have been landing — which tells you more about your real position than any automated estimate will.

One thing worth knowing: I recently ran a Final Offer campaign on a Lamorinda listing that the neighborhood had mentally priced at one number. Final Offer lets every serious buyer see activity in real time, so instead of one buyer guessing what it takes to win, the market finds the actual price. It sold for considerably more than anyone expected. Not every home is the right fit for it, but when it works, it changes the outcome.

If you want to talk through any of this, my calendar is below.

<table cellpadding="0" cellspacing="0" role="presentation" style="margin-top:24px;margin-bottom:8px;">
  <tr>
    <td style="background-color:#00aedb;border-radius:3px;">
      <a href="https://calendly.com/ben-brightwork/selling?utm_source=fub&utm_medium=email&utm_campaign=portal-seller&utm_content=day7" style="display:inline-block;color:#ffffff;font-family:Arial,sans-serif;font-size:15px;font-weight:700;letter-spacing:0.5px;text-decoration:none;padding:14px 32px;">Meet with Ben</a>
    </td>
  </tr>
</table>

---

## Step 7c — Day 7 Task: Call

Fifth attempt.

---

## Step 10 — Day 11 Email (HTML Program Overview)

FUB auto-sends. Pause-on-response: ON

**Subject:** A few programs worth knowing about

**Template:** `realtors/ben-olsen/sequences/templates/seller-programs-v2.html`

Rendered HTML email. Campaign slug: portal-seller. All links use utm_campaign=portal-seller and utm_content=day10.

Calendly CTA: https://calendly.com/ben-brightwork/selling?utm_source=fub&utm_medium=email&utm_campaign=portal-seller&utm_content=day10

---

## Step 14a — Day 15 Email

FUB auto-sends

**Subject:** I'll stop here for now

Hi %contact_first_name%,

I've reached out several times since your inquiry and haven't been able to connect. I'm going to stop rather than keep filling your inbox.

When the timing is right or the question comes back up, I'm easy to find. Most of what I do is help homeowners understand their options before they need to make a decision — so there's no wrong time to have the conversation.

If that time comes, my calendar is below.

<table cellpadding="0" cellspacing="0" role="presentation" style="margin-top:24px;margin-bottom:8px;">
  <tr>
    <td style="background-color:#00aedb;border-radius:3px;">
      <a href="https://calendly.com/ben-brightwork/selling?utm_source=fub&utm_medium=email&utm_campaign=portal-seller&utm_content=day14" style="display:inline-block;color:#ffffff;font-family:Arial,sans-serif;font-size:15px;font-weight:700;letter-spacing:0.5px;text-decoration:none;padding:14px 32px;">Meet with Ben</a>
    </td>
  </tr>
</table>

---

## Step 14b — Day 14 Task: Call

Sixth and final active pursuit call.

---

## Step 30 — Day 31 Email

FUB auto-sends. Sequence ends, nurture begins.

**Subject:** Checking in, no pressure

Hi %contact_first_name%,

It's been a few weeks since you were looking into your home's value. I wanted to check in once more before I move you to a lighter touch.

If you'd like to stay informed on what's actually happening in the market near you — what's selling, what's sitting, what buyers are paying — I send periodic updates to a short list of homeowners who've asked. No pitch, just useful information from someone who knows this market well.

And if the timing has shifted and you're closer to a decision than you were a month ago, you can find time on my calendar below.

<table cellpadding="0" cellspacing="0" role="presentation" style="margin-top:24px;margin-bottom:8px;">
  <tr>
    <td style="background-color:#00aedb;border-radius:3px;">
      <a href="https://calendly.com/ben-brightwork/selling?utm_source=fub&utm_medium=email&utm_campaign=portal-seller&utm_content=day30" style="display:inline-block;color:#ffffff;font-family:Arial,sans-serif;font-size:15px;font-weight:700;letter-spacing:0.5px;text-decoration:none;padding:14px 32px;">Meet with Ben</a>
    </td>
  </tr>
</table>
