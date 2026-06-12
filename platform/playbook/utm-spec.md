# UTM Specification
# Chief of Staff — Platform Standard
# Maintained by: MKTNG.co
# Last updated: June 2026

## Purpose

This document defines the UTM parameter convention for all Chief of Staff deployments. UTMs are read primarily by PostHog. They enable the agent to attribute lead source, channel, and program interest to individual contacts and surface that context in pre-appointment briefs.

## Parameters in Use

Four parameters are used. utm_term is not used — it is reserved for paid search keyword tracking, which is out of scope for this product.

| Parameter | Required | Purpose |
|---|---|---|
| utm_source | Always | Where the traffic originated |
| utm_medium | Always | The channel type |
| utm_campaign | When program-specific | Which program or initiative |
| utm_content | Automated only | Specific asset — sequences and QR codes only |

## Rules

1. utm_source and utm_medium are required on every tagged link.
2. utm_campaign is required when the link points to a program landing page.
3. utm_content is built by the agent for sequence emails and printed on direct mail QR codes. It is never manually added to social posts.
4. All values are lowercase kebab-case. No spaces, no capitals, no freeform values outside the approved lists below.
5. Generic homepage or contact page links do not require utm_campaign.

## Approved Values

### utm_source

zillow
realtorcom
finaloffercom
activepipe
fub
instagram
facebook
linkedin
google
sms
direct-mail
referral
lamorinda-report

### utm_medium

email
social
qr
sms
listing-portal
referral

### utm_campaign

Use only when linking to a specific program page.

quiet-listing
brightflip
buy-before-you-sell
final-offer
zillow-showcase
mcc-estimator
off-market
seniors
relaunch
invest

## Example URLs

Instagram post linking to BrightFlip page:
https://brightflip.brightworkrealty.com?utm_source=instagram&utm_medium=social&utm_campaign=brightflip

FUB sequence email linking to Quiet Listing page (agent-built):
https://quiet.brightworkrealty.com?utm_source=fub&utm_medium=email&utm_campaign=quiet-listing&utm_content=day7

Lamorinda Report newsletter linking to Off-Market page:
https://offmarket.brightworkrealty.com?utm_source=lamorinda-report&utm_medium=email&utm_campaign=off-market

Direct mail QR code linking to BrightFlip page:
https://brightflip.brightworkrealty.com?utm_source=direct-mail&utm_medium=qr&utm_campaign=brightflip&utm_content=q3-2026

## Adding New Values

New source, medium, or campaign values must be added to this spec before use. Do not invent freeform values in the field. Unapproved values fragment PostHog data and break attribution reporting.

To add a value: update this file, update the tenant utm-catalog.md, commit both together.
