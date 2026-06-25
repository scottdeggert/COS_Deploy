# MCC Value Estimator

Trigger: Tag mcc-estimator applied OR form submission on moragacountryclubrealestate.com
FUB stage: New Seller Lead
Action plan: MCC Estimator
Exit conditions: Any reply, inbound call, call 2+ minutes, stage change to Engaged / Listing Appointment / Active Seller
Nurture handoff: Day 30 moves to quarterly homeowner market updates for MCC homeowners. No call tasks.
HTML email: seller-programs-v2.html at Day 10, campaign slug mcc-estimator
Optional: Ben may choose to call at his discretion. No call tasks in this sequence.

---

<!-- CALENDLY BUTTON SPEC
Label: Meet with Ben
Background: #00aedb
Text color: #ffffff
Padding: 14px 32px
Border-radius: 3px
Font: Arial, sans-serif, 15px, bold
URL pattern: https://calendly.com/ben-brightwork/selling?utm_source=fub&utm_medium=email&utm_campaign=mcc-estimator&utm_content=day{N}
-->


| Step | Day | Channel | Executed by | Purpose |
|------|-----|---------|-------------|---------|
| 1 | 1 | Email | CoS drafts, Ben approves via Telegram [TELEGRAM APPROVAL REQUIRED - PATH A / FUB AUTO - PATH B] | Warm, neighborly acknowledgment of the floor plan tool |
| 2 | 3 | Email | FUB auto | MCC market context, genuinely useful |
| 3 | 10 | Email (HTML) | FUB auto | Program overview, low pressure |
| 4 | 30 | Email | FUB auto | Transition to quarterly market updates |

---

## Step 1 — Day 1 Email
FUB auto-sends
Pause-on-response: ON

Subject: Your Moraga Country Club question

Hi %contact_first_name%,

I've been working in Moraga Country Club since 2004. It's its own market within a market. Floor plan, condition, and where you sit on the course all move the number in ways the online estimates miss.

If you're thinking about what's next for your home, I'm happy to give you a real picture. I'll reach out. Feel free to reply anytime.

---

## Step 2 — Day 3 Email

**Pause-on-response:** ON

**Subject:** How floor plan shapes value at MCC

**Body:**

Hi %contact_first_name%,

I thought I'd share a few things about the MCC market that the valuation tool can't tell you on its own. Might be useful whether you're just curious or keeping an eye on things over time.

Moraga Country Club is a small market. When homes sell here, buyers usually already know the community. They understand the club lifestyle, the commute, the schools, and which floor plans work for their family. That means the floor plan itself matters a lot. Two homes with the same square footage but different layouts can trade for meaningfully different prices depending on how the rooms flow, whether there's a usable downstairs, and how the lot sits.

What's been selling lately tends to be the plans that feel open and current, with updated kitchens and primary suites that work for how people actually live. Buyers who want into the club are often comparing your plan against two or three others they've already toured. Condition matters, but so does which plan you have and how yours compares to recent closings in the same layout.

The other thing buyers look for here is discretion. A lot of MCC homeowners value privacy, and the market respects that. How a home is positioned and presented can make a real difference in how smoothly a transaction goes.

None of this is urgent. It's just context I pay attention to as someone who's been in and around this community for a long time.

If you ever want to dig into any of it, I'm around:
<table cellpadding="0" cellspacing="0" role="presentation" style="margin-top:24px;margin-bottom:8px;">
  <tr>
    <td style="background-color:#00aedb;border-radius:3px;">
      <a href="https://calendly.com/ben-brightwork/selling?utm_source=fub&utm_medium=email&utm_campaign=mcc-estimator&utm_content=day3" style="display:inline-block;color:#ffffff;font-family:Arial,sans-serif;font-size:15px;font-weight:700;letter-spacing:0.5px;text-decoration:none;padding:14px 32px;">Meet with Ben</a>
    </td>
  </tr>
</table>

---

## Step 3 — Day 10 Email (HTML Program Overview)

**Pause-on-response:** ON

**Subject:** A few programs worth knowing about

**Template:** `realtors/ben-olsen/sequences/templates/mcc-estimator-programs.html`

**Body:** Rendered HTML. See template file. Campaign slug: mcc-estimator. Calendly UTM content: day10.

---

## Step 4 — Day 30 Email

**Pause-on-response:** ON

**Subject:** Quarterly market updates for MCC homeowners

**Body:**

Hi %contact_first_name%,

I'm going to move you to a lighter touch from here.

A few times a year, I send a market update to MCC homeowners who've connected through the club site. What's actually selling, what buyers are paying, how different floor plans are performing. Useful information if you own here, whether or not you have any plans to do anything with your home.

It's a service for people in this community, not a sales follow-up. You'll hear from me when there's something worth sharing. And if a question comes up in the meantime, I'm easy to reach:

<table cellpadding="0" cellspacing="0" role="presentation" style="margin-top:24px;margin-bottom:8px;">
  <tr>
    <td style="background-color:#00aedb;border-radius:3px;">
      <a href="https://calendly.com/ben-brightwork/selling?utm_source=fub&utm_medium=email&utm_campaign=mcc-estimator&utm_content=day30" style="display:inline-block;color:#ffffff;font-family:Arial,sans-serif;font-size:15px;font-weight:700;letter-spacing:0.5px;text-decoration:none;padding:14px 32px;">Meet with Ben</a>
    </td>
  </tr>
</table>
