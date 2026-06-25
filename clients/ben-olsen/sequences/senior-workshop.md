Sequence 11: Senior Workshop Registrant
Trigger: Tag workshop-registration OR workshop-interest-list applied
FUB stage: New Seller Lead
Action plan: Senior Workshop
Exit conditions: Any reply, inbound call, call 2+ minutes, stage change to Engaged / Listing Appointment / Active Seller. Pause-on-response ON for all email steps.
Nurture handoff: Day 30 moves to 90-day seller nurture, quarterly homeowner market update, no more call tasks.
HTML email: seller-programs-v2.html at Day 7, campaign slug seniors
Calendly link: https://calendly.com/ben-brightwork/selling

<!-- CALENDLY BUTTON SPEC
Label: Meet with Ben
Background: #00aedb
Text color: #ffffff
Padding: 14px 32px
Border-radius: 3px
Font: Arial, sans-serif, 15px, bold
URL pattern: https://calendly.com/ben-brightwork/selling?utm_source=fub&utm_medium=email&utm_campaign=seniors&utm_content=day{N}
-->

Step	Day	Channel	Executed by	Purpose
1	1	Email	CoS drafts, Ben approves via Telegram [TELEGRAM APPROVAL REQUIRED - PATH A / FUB AUTO - PATH B]	First touch after workshop, no Calendly
1b	1	Task: Call (optional)	Ben	Only if contact requested a call on the registration form
3	3	Email	FUB auto	Transition thinking, options and control + Calendly
7	7	Email (HTML)	FUB auto	Program overview + Calendly
14	14	Email	FUB auto	Gentle follow-up, Quiet Listing by name + Calendly
30	30	Email	FUB auto	Nurture transition + Calendly


Step 1 — Day 1 Email
FUB auto-sends
Pause-on-response: ON

Subject: Senior real estate services in Lamorinda

Hi %contact_first_name%,

Thanks for reaching out. I've been helping seniors and their families navigate real estate decisions in Lamorinda for over 20 years. These situations are rarely just about the transaction. Timing, family dynamics, what makes the most financial sense, what creates the least disruption. I take all of it seriously.

No pressure on next steps. I'll reach out, and feel free to reply anytime with questions.


Step 1b — Day 1 Task: Call (optional)
Only enroll this step when the contact checked "request a call" (or equivalent) on the workshop registration form. Ben calls within one business day. No second call attempt. No SMS.

Step 3 — Day 3 Email
FUB auto-sends
Subject: A few questions worth sitting with
Hi %contact_first_name%,
I wanted to follow up with something practical from the workshop — the questions that usually matter more than any market statistic.
What does this move actually need to accomplish? Is it about simplifying day-to-day life, staying closer to family, unlocking equity for the next chapter, or keeping options open for a few more years? The answer shapes everything that comes after it.
And how important is staying in this specific community versus having more flexibility somewhere else? I've seen families in Lamorinda choose every path — sell and stay local in a smaller place, rent the family home and try a new setup, hold the property for the kids and downsize later. None of those is wrong. They just solve different problems.
If securing the next home before letting go of this one is part of the picture, Buy Before You Sell is worth knowing about by name. It's one of several ways to take the timing pressure off. The details belong in a conversation, not an email.
I've also kept a planning page updated for people at this stage, whether you're the homeowner or the adult child helping sort it out:
https://seniors.brightworkrealty.com?utm_source=fub&utm_medium=email&utm_campaign=seniors&utm_content=day3
Whenever it would be useful to talk through your situation — no agenda, no rush — you can find time here:
Or just reply to this email. I'm easy to reach either way.
<table cellpadding="0" cellspacing="0" role="presentation" style="margin-top:24px;margin-bottom:8px;">
  <tr>
    <td style="background-color:#00aedb;border-radius:3px;">
      <a href="https://calendly.com/ben-brightwork/selling?utm_source=fub&utm_medium=email&utm_campaign=seniors&utm_content=day3" style="display:inline-block;color:#ffffff;font-family:Arial,sans-serif;font-size:15px;font-weight:700;letter-spacing:0.5px;text-decoration:none;padding:14px 32px;">Meet with Ben</a>
    </td>
  </tr>
</table>

Step 7 — Day 7 Email (HTML Program Overview)
FUB auto-sends
Subject: A few programs worth knowing about
Template: realtors/ben-olsen/sequences/templates/senior-workshop-programs.html
Rendered HTML email. Campaign slug: seniors. All links use utm_campaign=seniors and utm_content=day7.

Step 14 — Day 14 Email
FUB auto-sends
Subject: Whenever the timing is right
Hi %contact_first_name%,
I haven't heard back since the workshop, and that's completely fine. These decisions unfold on their own schedule, and I'd rather be a useful resource than a persistent one.
One thing I hear often from seniors and the families helping them: privacy matters. Not everyone wants neighbors watching a for-sale sign go up or a days-on-market counter ticking on Zillow while they're still processing a major life change. When discretion is the priority, Quiet Listing is an option worth knowing about — it lets us test whether the right buyer is already out there before anything goes public.
If you're helping a parent through this, the hardest part is often just getting clear on what they actually want versus what everyone around them assumes they should do. I've had good conversations with adult children who needed a neutral third party to lay out the options without adding pressure. That's a role I'm comfortable playing.
The planning page is here if you want to revisit the framework from the workshop:
https://seniors.brightworkrealty.com?utm_source=fub&utm_medium=email&utm_campaign=seniors&utm_content=day14
And if a conversation would help — for you or for someone you're supporting — my calendar is open:
<table cellpadding="0" cellspacing="0" role="presentation" style="margin-top:24px;margin-bottom:8px;">
  <tr>
    <td style="background-color:#00aedb;border-radius:3px;">
      <a href="https://calendly.com/ben-brightwork/selling?utm_source=fub&utm_medium=email&utm_campaign=seniors&utm_content=day14" style="display:inline-block;color:#ffffff;font-family:Arial,sans-serif;font-size:15px;font-weight:700;letter-spacing:0.5px;text-decoration:none;padding:14px 32px;">Meet with Ben</a>
    </td>
  </tr>
</table>

Step 30 — Day 30 Email
FUB auto-sends. Sequence ends, nurture begins.
Subject: Moving you to a lighter touch
Hi %contact_first_name%,
It's been about a month since the workshop. I'm going to step back from active follow-up and move you to a lighter touch from here.
A few times a year, I send a market update to homeowners in this area — what's selling, what buyers are paying, how conditions are shifting. Useful context whether you're actively planning a transition or simply keeping a long-held home on your radar. No pitch, no pressure.
The decision you came to the workshop to think through doesn't expire. When the timing shifts — for you or for a parent you're helping — I'm easy to find:
And the planning resource stays here whenever you want it:
<table cellpadding="0" cellspacing="0" role="presentation" style="margin-top:24px;margin-bottom:8px;">
  <tr>
    <td style="background-color:#00aedb;border-radius:3px;">
      <a href="https://calendly.com/ben-brightwork/selling?utm_source=fub&utm_medium=email&utm_campaign=seniors&utm_content=day30" style="display:inline-block;color:#ffffff;font-family:Arial,sans-serif;font-size:15px;font-weight:700;letter-spacing:0.5px;text-decoration:none;padding:14px 32px;">Meet with Ben</a>
    </td>
  </tr>
</table>
https://seniors.brightworkrealty.com?utm_source=fub&utm_medium=email&utm_campaign=seniors&utm_content=day30
