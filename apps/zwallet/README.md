# ZWallet Adapter

This app is an audited billing adapter boundary for Z Platform.

It forwards credits and invoice-intent requests to `services/billing-ledger` only. It does not include wallet signing, swaps, cards, KYC, MPC, private keys, or payment-provider credentials.

## Runtime

- `GET /health` reports adapter status and explicitly confirms no wallet/card authority.
- `POST /api/invoice-intents` forwards invoice intent creation to Billing Ledger.
- `POST /api/credits` is temporarily contained with HTTP 503.
- `POST /api/invoice-intents` is temporarily contained with HTTP 503.

## Emergency financial mutation containment

Both public mutation routes return HTTP 503 with `Cache-Control: no-store` before parsing request bodies or calling Billing Ledger. Query strings do not bypass the gate. This is intentional until caller authentication supplies trusted tenant identity and the ledger has durable tenant/operation-scoped idempotency, replay-conflict rejection, and cross-tenant/concurrency/restart evidence.

Do not interpret HTTP 503 as proof that an earlier request did not commit. Do not automatically retry with a new idempotency key. Keep writes disabled until an independently reviewed candidate passes exact-head CI, security, governance, and external recovery gates.

## Rollback

Do not restore public financial mutation routes as a rollback. If this containment disrupts operations, keep financial writes disabled and roll back only unrelated changes. Re-enable routes only after the authorization and idempotency admission requirements above are verified.

## Required environment

- `Z_PLATFORM_BILLING_LEDGER_URL`
- `Z_PLATFORM_SERVICE_TOKEN`

## Validation

Run `npm test` to verify the adapter rejects wallet signing, card, KYC, MPC, and swap payloads.
