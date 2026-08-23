# U.Perfect Sales Response Assets and API Onboarding Design

**Date:** 10 August 2026
**Status:** Approved for implementation
**Scope:** Customer-response assets, deterministic close-sale behavior, and TH/EN API onboarding for Facebook Messenger, TikTok Shop, Shopee, and LINE Messaging API.

## Goal

Give U.Perfect operators a single, auditable source for customer replies and
provider setup. The local chatbot must answer product questions, handle common
objections, guide a customer toward a draft order, and stop at payment review.
Provider credentials remain server-side and provider statuses remain truthful.

## Design

1. `assets/chatbot/sales_response_assets.json` stores bilingual response
   templates, intent aliases, objection handling, close-sale CTAs, product
   image references, and safety rules.
2. `app/services/sales_assets.py` loads and validates that JSON at startup.
   The loader rejects missing fields, unknown catalog IDs, unsafe public URLs,
   and reply templates that contain unverified price claims.
3. `ConversationService` uses the asset pack for greeting, price, ingredient,
   delivery, buy, payment, address, objection, and fallback responses. It keeps
   deterministic catalog matching and payment-review guards.
4. `GET /api/sales-assets` exposes a secret-free summary for the dashboard.
   The response includes provider-neutral assets and image paths only; it never
   includes credential values.
5. The Integrations view links operators to bilingual onboarding documents. The
   documents explain where to create an app/channel, which values belong in the
   server environment, how to configure callbacks/webhooks, how to verify the
   first event, and which approval gates remain outside this repository.

## Catalog safety rules

- Only price and promotion values present in the canonical SQLite catalog may be
  used by an automated close-sale reply.
- The current verified-in-system serum offer is `98 THB` per item and `169 THB`
  for the seeded two-item promotion, both marked for merchant verification
  before live checkout.
- Mala Chili Oil has no seeded price, so the bot must request admin confirmation
  instead of quoting an amount or generating a payment instruction.
- Product media is local-only. The asset manifest references existing files and
  does not claim that TikTok media was exported.
- Ingredient text is merchant-provided information, not a medical diagnosis or
  guaranteed outcome. Sensitive-skin replies include patch-test and stop-use
  guidance.

## Provider onboarding boundary

The API guide is operational documentation, not a claim that accounts are
approved. Shopee, TikTok Shop, Facebook, and LINE require account-owner action,
official permissions, HTTPS callback reachability, and provider verification.
The local no-cost profile keeps these integrations `unconfigured` until the
server receives the required values and the official test succeeds.

## Acceptance criteria

- Asset JSON validates with a test and every referenced image exists.
- TH/EN assets cover greeting, product lookup, ingredients, price, delivery,
  buy, payment, address, objections, human takeover, and unpriced-product
  escalation.
- A local message using the serum can reach a clear close-sale CTA without
  claiming payment approval; a message using Mala Chili Oil cannot invent a
  price.
- `/api/sales-assets` is available and contains no token, secret, or credential
  value.
- API onboarding documents exist in both Thai and English and cover all four
  providers, exact environment variable names, callback paths, webhook
  verification, rate/policy boundaries, and safe secret handling.
- README and final release report link the new assets and documents.
- Existing local-only, PWA, integration, and packaging tests remain green.
