# ZWallet Adapter

This app is an audited billing adapter boundary for Z Platform.

It forwards credits and invoice-intent requests to `services/billing-ledger` only. It does not include wallet signing, swaps, cards, KYC, MPC, private keys, or payment-provider credentials.

## Runtime

- `GET /health` reports adapter status and explicitly confirms no wallet/card authority.
- `POST /api/invoice-intents` forwards invoice intent creation to Billing Ledger.
- `POST /api/credits` forwards credit updates to Billing Ledger.

## Required environment

- `Z_PLATFORM_BILLING_LEDGER_URL`
- `Z_PLATFORM_SERVICE_TOKEN`

## Failure and retry contract

- The adapter returns HTTP 503 with a generic body when Billing Ledger is unavailable, times out/connects unsuccessfully, returns 5xx/429, is not configured, or returns invalid success JSON.
- Responses include `Cache-Control: no-store`. The adapter does not retry automatically and does not forward upstream error bodies or `Retry-After`.
- A 503 does **not** prove whether a financial mutation committed. Reconcile with Billing Ledger using the same durable, operation-specific `idempotency_key` before retrying; never generate a new key solely because the response was 503.
- Upstream client errors remain HTTP 400 with a generic message. Forbidden wallet/card/KYC/MPC/swap payloads remain rejected.

## Validation

Run `npm test` to verify the adapter rejects wallet signing, card, KYC, MPC, and swap payloads and preserves the retryable 503 contract.
