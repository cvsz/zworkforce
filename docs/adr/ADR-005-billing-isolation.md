# ADR-005: Billing Isolation

## Status

Accepted

## Context

Billing must own immutable usage records, credits, and invoice intents. Financial signing, card data, KYC payloads, MPC shares, and swap execution must remain outside the billing boundary to limit scope and compliance exposure.

## Decision

`services/billing-ledger` owns:
- Immutable usage records (idempotency-key deduplicated)
- Credit management
- Invoice intent creation

Explicitly prohibited from billing paths:
- `wallet_signature`
- `card_number`
- `kyc_payload`
- `mpc_share`
- `swap_route`

`apps/zwallet` is a billing-ledger adapter only. It forwards invoice intents and credit requests to billing-ledger and explicitly rejects forbidden keys.

ZWallet never signs transactions, processes cards, runs KYC, handles MPC material, or executes swaps.

## Consequences

- Billing-ledger has a minimal, auditable surface.
- Wallet capability restrictions are enforced at the adapter boundary.
- Compliance scope is limited to usage, credits, and invoice intents.
- Any future wallet feature requiring signing/cards/MPC must live in a separate, explicitly scoped service.
