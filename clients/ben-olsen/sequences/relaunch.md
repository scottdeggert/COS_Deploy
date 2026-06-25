Sequence 8: Relaunch Inquiry
Trigger: Tag relaunch-inquiry applied OR form submission on relaunch.brightworkrealty.com
FUB stage: New Seller Lead
Action plan: Relaunch Inquiry
Exit conditions: Any reply, inbound call, call 2+ minutes, stage change to Engaged / Listing Appointment / Active Seller. Pause-on-response ON for all email steps.
Nurture handoff: Day 30 moves to 90-day seller nurture, quarterly homeowner market update, no more call tasks.
HTML email: seller-programs-v2.html at Day 10, campaign slug relaunch
Calendly link: https://calendly.com/ben-brightwork/selling

<!-- CALENDLY BUTTON SPEC
Label: Meet with Ben
Background: #00aedb
Text color: #ffffff
Padding: 14px 32px
Border-radius: 3px
Font: Arial, sans-serif, 15px, bold
URL pattern: https://calendly.com/ben-brightwork/selling?utm_source=fub&utm_medium=email&utm_campaign=relaunch&utm_content=day{N}
-->

Step	Day	Channel	Executed by	Purpose
1a	1	Email	CoS drafts, Ben approves via Telegram [TELEGRAM APPROVAL REQUIRED - PATH A / FUB AUTO - PATH B]	First touch, no Calendly
1b	1	SMS	Ben pastes into FUB [BEN PASTES — CoS drafts, Ben approves via Telegram]	Immediate follow
1c	1	Task: Call	Ben	First call attempt
1d	1	Task: Call	Ben	Second call attempt, 2+ hrs later
1a	2	Email	FUB auto	Quiet Listing, forensic review framing + Calendly
1b	1	Task: Call	Ben	Third call attempt
2	2	SMS	Ben pastes into FUB [BEN PASTES — CoS drafts, Ben approves via Telegram]	Low-friction check-in
3a	4	Email	FUB auto	Deferred maintenance, BrightFlip + Calendly
3b	3	Task: Call	Ben	Fourth call attempt
5	6	Email	FUB auto	Forensic review, Zillow Showcase + Calendly
7a	7	SMS	Ben pastes into FUB [BEN PASTES — CoS drafts, Ben approves via Telegram]	Re-engagement
7b	7	Task: Call	Ben	Fifth call attempt
10	11	Email (HTML)	FUB auto	Program overview + Calendly
14a	15	Email	FUB auto	Final Offer, final active pursuit + Calendly
14b	14	Task: Call	Ben	Sixth and final call attempt
30	31	Email	FUB auto	Nurture transition + Calendly


Step 1a — Day 1 Email
FUB auto-sends
Pause-on-response: ON

Subject: Let's get this right

Hi %contact_first_name%,

Listings that don't sell the first time usually have a fixable story. Pricing, presentation, timing, or some combination. I've relaunched properties in this market that went on to sell well, and the difference almost always came down to what changed before the sign went back up.

I'll call you to talk through what you're working with and what I'd do differently.


Step 1b — Day 1 SMS
[REPLACE WITH FUB-NATIVE EMAIL — PENDING]
[BEN PASTES — CoS drafts, Ben approves via Telegram]
Hi %contact_first_name%, Ben Olsen at BrightWork. Just sent you a note about your home. No pressure — happy to talk through what happened and whether a different approach makes sense. (925) 255-9727

Step 1c — Day 1 Task: Call
First attempt. Ben calls within the hour.

Step 1d — Day 1 Task: Call
Second attempt. Schedule 2+ hours after first call.

Step 1a — Day 2 Email
FUB auto-sends
Pause-on-response: ON
Subject: Trying again without the same playbook
Hi %contact_first_name%,
I tried to reach you yesterday. Still happy to connect when the timing works.
When a home has already sat on the market, the question isn't really whether to try again. It's whether trying again with the same strategy produces a different result. In my experience, it usually doesn't — because the strategy was the problem, not the seller.
Before anything goes back out, I do a forensic review: what's the realistic pricing story for this property, what condition issues are worth addressing, what's missing from the presentation, and what the right portal strategy looks like. For homes that previously didn't sell, that review almost always identifies something specific. It's one of the first things I'd want to walk through with you.
One other thing worth knowing for sellers who don't want the neighborhood watching them try again: Quiet Listing.
If any of this is worth a conversation, you can find time on my calendar below.

<table cellpadding="0" cellspacing="0" role="presentation" style="margin-top:24px;margin-bottom:8px;">
  <tr>
    <td style="background-color:#00aedb;border-radius:3px;">
      <a href="https://calendly.com/ben-brightwork/selling?utm_source=fub&utm_medium=email&utm_campaign=relaunch&utm_content=day1" style="display:inline-block;color:#ffffff;font-family:Arial,sans-serif;font-size:15px;font-weight:700;letter-spacing:0.5px;text-decoration:none;padding:14px 32px;">Meet with Ben</a>
    </td>
  </tr>
</table>
Or call me directly at (925) 255-9727.

Step 1b — Day 1 Task: Call
Third attempt.

Step 2 — Day 2 SMS
[REPLACE WITH FUB-NATIVE EMAIL — PENDING]
[BEN PASTES — CoS drafts, Ben approves via Telegram]
Hey %contact_first_name%, Ben Olsen here. Following up on my note about your home. Happy to talk through what happened and whether a different approach makes sense — no obligation. (925) 255-9727

Step 3a — Day 4 Email
FUB auto-sends
Pause-on-response: ON
Subject: What the home may need before round two
Hi %contact_first_name%,
I don't want to keep reaching out if the timing isn't right. Let me just ask directly.
Are you thinking about relisting in the next few months, or still working through whether it's worth trying again at all? And is there a complicating factor — like needing to buy your next place before you can actually sell this one?
Those questions matter because a relaunch isn't just about changing agents or dropping the price. Sometimes the home itself needs something before it's ready to compete — deferred maintenance that showed up in showings, a dated kitchen that buyers compared unfavorably to recent closings, cosmetic updates that would have cost less to address upfront than the price reduction that followed.
That's a common thread in listings that sat. The home went out before it was ready, and the market responded accordingly. BrightFlip is worth knowing about if that sounds familiar.
None of this requires a commitment to relist. It's just the kind of thing the forensic review usually surfaces, and it's better to understand it before you decide anything.
If any of that is relevant, grab a time below when you're ready.

<table cellpadding="0" cellspacing="0" role="presentation" style="margin-top:24px;margin-bottom:8px;">
  <tr>
    <td style="background-color:#00aedb;border-radius:3px;">
      <a href="https://calendly.com/ben-brightwork/selling?utm_source=fub&utm_medium=email&utm_campaign=relaunch&utm_content=day3" style="display:inline-block;color:#ffffff;font-family:Arial,sans-serif;font-size:15px;font-weight:700;letter-spacing:0.5px;text-decoration:none;padding:14px 32px;">Meet with Ben</a>
    </td>
  </tr>
</table>
Or just reply to this email and we'll go from there.

Step 3b — Day 3 Task: Call
Fourth attempt.

Step 5 — Day 6 Email
FUB auto-sends
Pause-on-response: ON
Subject: What a forensic review usually finds
Hi %contact_first_name%,
Most listings go to market hoping the best offer shows up. The photos go up, the price goes in, and everyone waits to see what happens. When nothing happens, the default response is usually a price reduction — and sometimes another one after that.
We work the other direction. Before anything lists — or relists — I do a forensic review of what actually went wrong. Not in theory. In the specific categories that determine whether a home sells: the pricing story relative to what's closed recently, the condition and presentation, the preparation and disclosure strategy, the timing relative to what else is competing, and how the home showed up on the major portals — Zillow, Redfin, homes.com.
Poor portal presentation is one of the most common failure points I see on expired listings. When that was part of the problem the first time, Zillow Showcase is one of the levers worth pulling.
The goal isn't to retry harder. It's to identify what was missing and build a strategy around fixing it. That's the difference between a relaunch and a repeat.
If you want to understand what that would look like for your home, you can find time on my calendar below.

<table cellpadding="0" cellspacing="0" role="presentation" style="margin-top:24px;margin-bottom:8px;">
  <tr>
    <td style="background-color:#00aedb;border-radius:3px;">
      <a href="https://calendly.com/ben-brightwork/selling?utm_source=fub&utm_medium=email&utm_campaign=relaunch&utm_content=day5" style="display:inline-block;color:#ffffff;font-family:Arial,sans-serif;font-size:15px;font-weight:700;letter-spacing:0.5px;text-decoration:none;padding:14px 32px;">Meet with Ben</a>
    </td>
  </tr>
</table>

Step 7a — Day 7 SMS
[REPLACE WITH FUB-NATIVE EMAIL — PENDING]
[BEN PASTES — CoS drafts, Ben approves via Telegram]
Hi %contact_first_name%, Ben here. I've sent a few notes about your home and haven't been able to connect. Still happy to talk when the time is right — it's a short conversation. (925) 255-9727

Step 7b — Day 7 Task: Call
Fifth attempt.

Step 10 — Day 11 Email (HTML Program Overview)
FUB auto-sends
Pause-on-response: ON
Subject: A few programs worth knowing about
Template: realtors/ben-olsen/sequences/templates/relaunch-programs.html
Rendered HTML email. Campaign slug: relaunch. All links use utm_campaign=relaunch and utm_content=day10.

Step 14a — Day 15 Email
FUB auto-sends
Pause-on-response: ON
Subject: I'll stop here for now
Hi %contact_first_name%,
I've reached out several times since your inquiry and haven't been able to connect. I'm going to stop rather than keep filling your inbox.
You didn't come to this decision lightly — looking at trying again after a home didn't sell takes something. That doesn't expire, and neither does the question of whether a different approach would produce a different outcome.
Most of what I do at this stage is the forensic review: an honest look at what went wrong the first time and whether the fix is something that would actually change the result. No pitch until the diagnosis is clear.
One thing worth knowing for homes with genuine buyer demand: Final Offer. If offer uncertainty was part of what hurt you last time, it's worth understanding before you decide anything.
If that time comes, my calendar is below.

<table cellpadding="0" cellspacing="0" role="presentation" style="margin-top:24px;margin-bottom:8px;">
  <tr>
    <td style="background-color:#00aedb;border-radius:3px;">
      <a href="https://calendly.com/ben-brightwork/selling?utm_source=fub&utm_medium=email&utm_campaign=relaunch&utm_content=day14" style="display:inline-block;color:#ffffff;font-family:Arial,sans-serif;font-size:15px;font-weight:700;letter-spacing:0.5px;text-decoration:none;padding:14px 32px;">Meet with Ben</a>
    </td>
  </tr>
</table>

Step 14b — Day 14 Task: Call
Sixth and final active pursuit call.

Step 30 — Day 31 Email
FUB auto-sends. Sequence ends, nurture begins.
Pause-on-response: ON
Subject: Checking in, no pressure
Hi %contact_first_name%,
It's been a few weeks since your inquiry about relisting. I wanted to check in once more before I move you to a lighter touch.
If you'd like to stay informed on what's actually happening in the market near you — what's selling, what's sitting, what buyers are paying — I send periodic updates to a short list of homeowners who've asked. No pitch, just useful information from someone who knows this market well.
And if the timing has shifted and you're closer to a decision than you were a month ago, you can find time on my calendar below.

<table cellpadding="0" cellspacing="0" role="presentation" style="margin-top:24px;margin-bottom:8px;">
  <tr>
    <td style="background-color:#00aedb;border-radius:3px;">
      <a href="https://calendly.com/ben-brightwork/selling?utm_source=fub&utm_medium=email&utm_campaign=relaunch&utm_content=day30" style="display:inline-block;color:#ffffff;font-family:Arial,sans-serif;font-size:15px;font-weight:700;letter-spacing:0.5px;text-decoration:none;padding:14px 32px;">Meet with Ben</a>
    </td>
  </tr>
</table>
