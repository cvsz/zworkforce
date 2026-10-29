# ZWallet Adapter

This app is an audited billing adapter boundary for Z Platform.

It forwards credits and invoice-intent requests to `services/billing-ledger` only. It does not include wallet signing, swaps, cards, KYC, MPC, private keys, or payment-provider credentials.

## Runtime

- `GET /health` reports adapter status and explicitly confirms no wallet/card authority.
- `POST /api/invoice-intents` forwards invoice-intent creation to Billing Ledger.
- `POST /api/credits` forwards credit updates to Billing Ledger.
- Missing ledger configuration, transport failures, downstream non-2xx responses, and invalid successful JSON fail closed with HTTP `503` and `Cache-Control: no-store`.
- The adapter does not automatically retry financial mutations and does not expose downstream response bodies or transport exception details.

## Required environment

- `Z_PLATFORM_BILLING_LEDGER_URL`
- `Z_PLATFORM_SERVICE_TOKEN`

## Financial retry and reconciliation contract

A `503` means the adapter could not establish a trustworthy successful response; it does **not** prove that a downstream mutation did not commit. Callers must not blindly retry with a new key. Reconcile the operation using the same durable, operation-specific idempotency key and the authoritative Billing Ledger record before deciding whether another attempt is safe. The Billing Ledger must keep production mutations fail-closed until durable storage and database-enforced idempotency are verified.

## Validation

Run `npm test` from this directory. Tests cover the adapter's restricted authority, downstream outage and transport handling, non-leaking error responses, no-store behavior, missing configuration, and the absence of automatic retries.
