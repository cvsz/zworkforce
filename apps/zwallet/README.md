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

## Validation

Run `npm test` to verify the adapter rejects wallet signing, card, KYC, MPC, and swap payloads.
