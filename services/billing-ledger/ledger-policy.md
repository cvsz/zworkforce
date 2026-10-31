# Ledger Policy

- Accept validated usage events only from authenticated platform services.
- Require an idempotency key and immutable event ID.
- Record usage before creating any invoice or credit action.
- Do not process card data, wallet keys, signing requests, swaps, or KYC data.
- Payment processor and currency decisions require explicit operator configuration.
- The current invoice-intent allowlist is limited to ISO 4217 `THB` and `USD`; adding another code requires a reviewed application change and forward-only database constraint migration.
- Never infer currency support from a three-letter shape check alone.
