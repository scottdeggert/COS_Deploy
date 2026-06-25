# Zillow Buyer

Trigger: Tag zillow-lead applied + buyer intent signal
FUB stage: New Buyer Lead
Action plan: Portal Lead — Buyer
Exit conditions: Any reply, inbound call, call 2+ minutes, stage change to Engaged / Showing / Active Buyer / Under Contract. Pause-on-response ON for all email steps.
Nurture handoff: Day 30 moves to 90-day buyer nurture, monthly new listing alerts, no more call tasks
HTML email: buyer-programs.html at Day 10 [PLACEHOLDER — not yet built]
Calendly link: https://calendly.com/ben-brightwork/buying

<!-- CALENDLY BUTTON SPEC
Label: Meet with Ben
Background: #00aedb
Text color: #ffffff
Padding: 14px 32px
Border-radius: 3px
Font: Arial, sans-serif, 15px, bold
URL pattern: https://calendly.com/ben-brightwork/selling?utm_source=fub&utm_medium=email&utm_campaign=zillow-buyer&utm_content=day{N}
-->

Step	Day	Channel	Executed by	Purpose
1a	1	Email	CoS drafts, Ben approves via Telegram [TELEGRAM APPROVAL REQUIRED - PATH A / FUB AUTO - PATH B]	First touch, no Calendly
1b	1	SMS	Ben pastes into FUB [BEN PASTES — CoS drafts, Ben approves via Telegram]	Immediate follow
1c	1	Task: Call	Ben	First call attempt
1d	1	Task: Call	Ben	Second call attempt, 2+ hrs later
1a	2	Email	FUB auto	Off-Market Access + Calendly
1b	1	Task: Call	Ben	Third call attempt
2	2	SMS	Ben pastes into FUB [BEN PASTES — CoS drafts, Ben approves via Telegram]	Low-friction check-in
3a	4	Email	FUB auto	Timeline, Buy Before You Sell + Calendly
3b	3	Task: Call	Ben	Fourth call attempt
5	6	Email	FUB auto	How Ben works with buyers + Calendly
7a	7	SMS	Ben pastes into FUB [BEN PASTES — CoS drafts, Ben approves via Telegram]	Re-engagement
7b	7	Task: Call	Ben	Fifth call attempt
10	11	Email (HTML)	FUB auto	Program overview + Calendly [PLACEHOLDER]
14a	15	Email	FUB auto	Final active pursuit + Calendly
14b	14	Task: Call	Ben	Sixth and final call attempt
30	31	Email	FUB auto	Nurture transition + Calendly


Step 1a — Day 1 Email
FUB auto-sends
Pause-on-response: ON

Subject: The listing you asked about

Hi %contact_first_name%,

Thanks for reaching out. I'll call you in a few minutes.

One thing worth knowing: some of the best properties in Lamorinda move before they ever hit Zillow. I keep a private list of homes where sellers want to test buyer interest quietly before going public. Worth a quick conversation about what you're looking for.


Step 1b — Day 1 SMS
[REPLACE WITH FUB-NATIVE EMAIL — PENDING]
[BEN PASTES — CoS drafts, Ben approves via Telegram]
Hi %contact_first_name%, this is Ben Olsen at BrightWork. Just sent you an email about your Zillow inquiry. Happy to talk through what's available in your target area. (925) 255-9727

Step 1c — Day 1 Task: Call
First attempt. Ben calls within the hour.

Step 1d — Day 1 Task: Call
Second attempt. Schedule 2+ hours after first call.

Step 1a — Day 2 Email
FUB auto-sends
Subject: A few things worth knowing about this market
Hi %contact_first_name%,
I tried to reach you yesterday. Still happy to connect when the timing works.
One thing worth mentioning early: some of the best opportunities in Lamorinda never show up on Zillow first — or they show up there late, after the serious buyers have already heard about them. I maintain access to private listings through Off-Market Access, a network of homes that test the market quietly before going fully public.
For buyers who know what they want and move quickly, that access matters. You're not competing with every buyer scanning the portals. You're seeing options most people don't know exist yet.
If you'd like to talk through what you're looking for and whether that kind of access would help, you can find time on my calendar below.

<table cellpadding="0" cellspacing="0" role="presentation" style="margin-top:24px;margin-bottom:8px;">
  <tr>
    <td style="background-color:#00aedb;border-radius:3px;">
      <a href="https://calendly.com/ben-brightwork/buying?utm_source=fub&utm_medium=email&utm_campaign=zillow-buyer&utm_content=day1" style="display:inline-block;color:#ffffff;font-family:Arial,sans-serif;font-size:15px;font-weight:700;letter-spacing:0.5px;text-decoration:none;padding:14px 32px;">Meet with Ben</a>
    </td>
  </tr>
</table>
Or call me directly at (925) 255-9727.

Step 1b — Day 1 Task: Call
Third attempt.

Step 2 — Day 2 SMS
[REPLACE WITH FUB-NATIVE EMAIL — PENDING]
[BEN PASTES — CoS drafts, Ben approves via Telegram]
Hey %contact_first_name%, Ben Olsen here. Following up on your Zillow inquiry. Happy to talk through what's available in your target area — no obligation. (925) 255-9727

Step 3a — Day 4 Email
FUB auto-sends
Subject: Quick question about your timeline
Hi %contact_first_name%,
I don't want to keep reaching out if the timing isn't right. Let me just ask directly.
Are you actively looking right now, or still in the early research phase? And is there a complicating factor — like needing to sell your current home before you can make a non-contingent offer on the next one?
That situation comes up constantly in this market. Buyers assume they have to sell first, wait, then buy — and miss homes they would have loved. Buy Before You Sell is worth understanding before you assume the timing has to work that way.
If any of that is relevant, it's worth a conversation. You can find time on my calendar below.

<table cellpadding="0" cellspacing="0" role="presentation" style="margin-top:24px;margin-bottom:8px;">
  <tr>
    <td style="background-color:#00aedb;border-radius:3px;">
      <a href="https://calendly.com/ben-brightwork/buying?utm_source=fub&utm_medium=email&utm_campaign=zillow-buyer&utm_content=day3" style="display:inline-block;color:#ffffff;font-family:Arial,sans-serif;font-size:15px;font-weight:700;letter-spacing:0.5px;text-decoration:none;padding:14px 32px;">Meet with Ben</a>
    </td>
  </tr>
</table>
Or just reply to this email and we'll go from there.

Step 3b — Day 3 Task: Call
Fourth attempt.

Step 5 — Day 6 Email
FUB auto-sends
Subject: How I work with buyers here
Hi %contact_first_name%,
Every buyer who comes through Zillow has already done a lot of homework online. The floor plans, the school ratings, the commute estimates — you've probably toured half the neighborhood on your phone already.
What I add is local pattern recognition. I've lived in Lamorinda my whole life and I've been through enough cycles to know which streets feel different at rush hour, which floor plans actually live the way the photos suggest, and what sellers in this market respond to when an offer comes in clean.
My job isn't to send you every listing that matches a filter. It's to help you understand tradeoffs — location vs. condition vs. timing — and put you in position to move when the right home shows up, including ones you wouldn't have found on your own.
If you want to talk through what that would look like for your search, grab a time below when you're ready.

<table cellpadding="0" cellspacing="0" role="presentation" style="margin-top:24px;margin-bottom:8px;">
  <tr>
    <td style="background-color:#00aedb;border-radius:3px;">
      <a href="https://calendly.com/ben-brightwork/buying?utm_source=fub&utm_medium=email&utm_campaign=zillow-buyer&utm_content=day5" style="display:inline-block;color:#ffffff;font-family:Arial,sans-serif;font-size:15px;font-weight:700;letter-spacing:0.5px;text-decoration:none;padding:14px 32px;">Meet with Ben</a>
    </td>
  </tr>
</table>

Step 7a — Day 7 SMS
[REPLACE WITH FUB-NATIVE EMAIL — PENDING]
[BEN PASTES — CoS drafts, Ben approves via Telegram]
Hi %contact_first_name%, Ben here. I've sent a few notes about your Zillow inquiry and haven't been able to connect. Still happy to talk when the time is right. (925) 255-9727

Step 7b — Day 7 Task: Call
Fifth attempt.

Step 10 — Day 11 Email (HTML Program Overview)
FUB auto-sends
Subject: A few programs worth knowing about
[PLACEHOLDER — buyer-programs.html not yet built. See realtors/ben-olsen/sequences/templates/buyer-programs-placeholder.md]
Programs: Off-Market Access and Buy Before You Sell only. Campaign slug: zillow-buyer. All links use utm_campaign=zillow-buyer and utm_content=day10. Calendly: https://calendly.com/ben-brightwork/buying?utm_source=fub&utm_medium=email&utm_campaign=zillow-buyer&utm_content=day10

Step 14a — Day 15 Email
FUB auto-sends
Subject: I'll stop here for now
Hi %contact_first_name%,
I've reached out several times since your Zillow inquiry and haven't been able to connect. I'm going to stop rather than keep filling your inbox.
When the timing is right or the search picks back up, I'm easy to find. Most of what I do at this stage is help buyers understand what's actually available — on and off the portals — before they need to make a decision under pressure.
If that time comes, my calendar is below.

<table cellpadding="0" cellspacing="0" role="presentation" style="margin-top:24px;margin-bottom:8px;">
  <tr>
    <td style="background-color:#00aedb;border-radius:3px;">
      <a href="https://calendly.com/ben-brightwork/buying?utm_source=fub&utm_medium=email&utm_campaign=zillow-buyer&utm_content=day14" style="display:inline-block;color:#ffffff;font-family:Arial,sans-serif;font-size:15px;font-weight:700;letter-spacing:0.5px;text-decoration:none;padding:14px 32px;">Meet with Ben</a>
    </td>
  </tr>
</table>

Step 14b — Day 14 Task: Call
Sixth and final active pursuit call.

Step 30 — Day 31 Email
FUB auto-sends. Sequence ends, nurture begins.
Subject: Checking in, no pressure
Hi %contact_first_name%,
It's been a few weeks since your Zillow inquiry. I wanted to check in once more before I move you to a lighter touch.
If you'd like to stay informed on what's new in the areas you're watching — listings that match what you described, including off-market options when they come up — I send monthly alerts to buyers who've asked. No pitch, just useful information from someone who knows this market well.
And if the timing has shifted and you're closer to making a move than you were a month ago, you can find time on my calendar below.

<table cellpadding="0" cellspacing="0" role="presentation" style="margin-top:24px;margin-bottom:8px;">
  <tr>
    <td style="background-color:#00aedb;border-radius:3px;">
      <a href="https://calendly.com/ben-brightwork/buying?utm_source=fub&utm_medium=email&utm_campaign=zillow-buyer&utm_content=day30" style="display:inline-block;color:#ffffff;font-family:Arial,sans-serif;font-size:15px;font-weight:700;letter-spacing:0.5px;text-decoration:none;padding:14px 32px;">Meet with Ben</a>
    </td>
  </tr>
</table>
