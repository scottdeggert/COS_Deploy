# HomeLight

Trigger: Tag homelight-lead applied on HomeLight warm transfer
FUB stage: New Seller Lead
Action plan: HomeLight
Exit conditions: Any reply, inbound call, call 2+ minutes, stage change to Engaged / Listing Appointment / Active Seller
Nurture handoff: Day 14 moves to 90-day seller nurture, quarterly homeowner market update, no more call tasks
HTML email: seller-programs-v2.html at Day 4-5, campaign slug homelight
Special: Day 0 includes HomeLight platform compliance task

---

<!-- CALENDLY BUTTON SPEC
Label: Meet with Ben
Background: #00aedb
Text color: #ffffff
Padding: 14px 32px
Border-radius: 3px
Font: Arial, sans-serif, 15px, bold
URL pattern: https://calendly.com/ben-brightwork/selling?utm_source=fub&utm_medium=email&utm_campaign=homelight&utm_content=day{N}
-->


| Step | Day | Channel | Executed by | Purpose |
|------|-----|---------|-------------|---------|
| 1a | 1 | Email | CoS drafts, Ben approves via Telegram [TELEGRAM APPROVAL REQUIRED - PATH A / FUB AUTO - PATH B] | First touch, no Calendly |
| 1b | 1 | Task: HomeLight platform | Ben | Referral compliance — log first contact attempt |
| 1c | 1 | Task: Call | Ben | First call attempt |
| 1a | 2 | Email | FUB auto | Options framing, Quiet Listing + Calendly |
| 1b | 1 | Task: Call | Ben | Second call attempt |
| 3 | 4 | Email | FUB auto | Timeline, Buy Before You Sell, BrightFlip + Calendly |
| 5 | 6 | Email (HTML) | FUB auto | Program overview + Calendly |
| 7 | 7 | SMS | Ben pastes into FUB [BEN PASTES — CoS drafts, Ben approves via Telegram] | Low-friction check-in |
| 10 | 11 | Email | FUB auto | Final active pursuit + Calendly |
| 14 | 15 | Email | FUB auto | Nurture transition + Calendly |

---

## Step 1a — Day 1 Email
FUB auto-sends
Pause-on-response: ON

Subject: Good to connect earlier

Hi %contact_first_name%,

Good talking with you. I wanted to follow up with a few things in writing so you have them.

I work directly with every client from first conversation through close. No handoffs to a team or an assistant. That's by design, and it's part of why HomeLight matched us.

If anything came up after our call, reply here or grab time on my calendar below.

---

## Step 1b — Day 1 Task: HomeLight Platform

Ben logs first contact attempt in HomeLight platform immediately after Day 0 outreach.

Log first contact attempt in HomeLight platform. Required for referral compliance. ~33% referral fee structure.

---

## Step 1c — Day 1 Task: Call

First attempt. Ben calls within the hour.

---

## Step 1a — Day 2 Email

FUB auto-sends

**Subject:** A few things worth knowing about selling here

Hi %contact_first_name%,

I tried to reach you after HomeLight connected us. Still happy to connect when the timing works.

A lot of sellers I talk to through referrals are further along than they realize — they have real equity, a clear reason to move, and mostly need someone local who can walk through the options without rushing them. That's usually where I start: what's the timeline, what does the home need before it would show well, and is there a complicating factor like needing to buy the next place before this one closes?

For some homeowners in this area, a Quiet Listing is worth understanding — testing whether the right buyer is already in my private network before anything goes public. For others, it's about preparation and positioning for a full launch. The right answer depends on your situation.

If you'd like to talk through it: https://calendly.com/ben-brightwork/selling?utm_source=fub&utm_medium=email&utm_campaign=homelight&utm_content=day1
Or call me at (925) 255-9727.

---

## Step 1b — Day 1 Task: Call

Second attempt.

---

## Step 3 — Day 4 Email

FUB auto-sends

**Subject:** Quick question about your timeline

Hi %contact_first_name%,

I don't want to keep reaching out if the timing isn't right. Let me just ask directly.

Are you thinking about a move in the next six months, or is this more exploratory? And is there anything that complicates the picture — deferred maintenance before you'd want to list, or needing to line up your next home before this one closes?

That second question comes up constantly in this market. Buy Before You Sell is worth knowing about if timing is the constraint. And if the home needs work before it's ready to show, BrightFlip is an option we look at when the math clearly favors doing the work before listing.

None of this requires a decision today. It's just worth understanding what's available.
Or reply to this email and we'll go from there.
<table cellpadding="0" cellspacing="0" role="presentation" style="margin-top:24px;margin-bottom:8px;">
  <tr>
    <td style="background-color:#00aedb;border-radius:3px;">
      <a href="https://calendly.com/ben-brightwork/selling?utm_source=fub&utm_medium=email&utm_campaign=homelight&utm_content=day3" style="display:inline-block;color:#ffffff;font-family:Arial,sans-serif;font-size:15px;font-weight:700;letter-spacing:0.5px;text-decoration:none;padding:14px 32px;">Meet with Ben</a>
    </td>
  </tr>
</table>

---

## Step 5 — Day 6 Email (HTML Program Overview)

FUB auto-sends

**Subject:** A few programs worth knowing about

**Template:** `realtors/ben-olsen/sequences/templates/homelight-programs.html`

Rendered HTML email. Campaign slug: homelight. All links use utm_campaign=homelight and utm_content=day5.

---

## Step 7 — Day 7 SMS

[REPLACE WITH FUB-NATIVE EMAIL — PENDING]
[BEN PASTES — CoS drafts, Ben approves via Telegram]

Hi %contact_first_name%, Ben Olsen at BrightWork. Following up after your HomeLight connection. Still happy to talk through your options when the timing works. (925) 255-9727

---

## Step 10 — Day 11 Email

FUB auto-sends

**Subject:** I'll stop here for now

Hi %contact_first_name%,

I've reached out a few times since HomeLight connected us and haven't been able to connect. I'm going to stop rather than keep filling your inbox.

You reached out for a reason — most sellers who get to this point have real questions about equity, timing, and what selling would actually look like. Those questions don't expire. When the timing is right, I'm easy to find.

<table cellpadding="0" cellspacing="0" role="presentation" style="margin-top:24px;margin-bottom:8px;">
  <tr>
    <td style="background-color:#00aedb;border-radius:3px;">
      <a href="https://calendly.com/ben-brightwork/selling?utm_source=fub&utm_medium=email&utm_campaign=homelight&utm_content=day10" style="display:inline-block;color:#ffffff;font-family:Arial,sans-serif;font-size:15px;font-weight:700;letter-spacing:0.5px;text-decoration:none;padding:14px 32px;">Meet with Ben</a>
    </td>
  </tr>
</table>

---

## Step 14 — Day 15 Email

FUB auto-sends. Sequence ends, nurture begins.

**Subject:** Checking in, no pressure

Hi %contact_first_name%,

I'm going to move you to a lighter touch from here.

If you'd like to stay informed on what's actually happening in the market near you — what's selling, what's sitting, what buyers are paying — I send periodic updates to a short list of homeowners who've asked. No pitch, just useful information from someone who knows this market well.

And if the timing has shifted and you're closer to a decision than you were a couple of weeks ago, you can always find time here:
<table cellpadding="0" cellspacing="0" role="presentation" style="margin-top:24px;margin-bottom:8px;">
  <tr>
    <td style="background-color:#00aedb;border-radius:3px;">
      <a href="https://calendly.com/ben-brightwork/selling?utm_source=fub&utm_medium=email&utm_campaign=homelight&utm_content=day14" style="display:inline-block;color:#ffffff;font-family:Arial,sans-serif;font-size:15px;font-weight:700;letter-spacing:0.5px;text-decoration:none;padding:14px 32px;">Meet with Ben</a>
    </td>
  </tr>
</table>
