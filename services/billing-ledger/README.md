# Billing Ledger

This service accepts validated usage events from the AI gateway and creates idempotent billing records.

It does not manage wallet keys, MPC shares, card data, or transaction signing.

## Runtime safety

The default `MemoryLedgerStore` is process-local and is not a production persistence layer. HTTP POST routes for usage, credits, and invoice intents return HTTP 503 when this store is active unless `NODE_ENV` is explicitly `development` or `test`. An unset `NODE_ENV` is fail-closed. This guard is containment only; production mutations require a durable store, database-enforced idempotency, tenant authorization, independent review, and backup/restore evidence.
