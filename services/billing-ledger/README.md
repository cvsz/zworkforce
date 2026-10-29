# Billing Ledger

This service accepts validated usage events from the AI gateway and creates idempotent billing records.

It does not manage wallet keys, MPC shares, card data, or transaction signing.

## Runtime safety

The default `MemoryLedgerStore` is process-local and is not a production persistence layer. HTTP POST routes for usage, credits, and invoice intents return HTTP 503 when this store is active unless `NODE_ENV` is explicitly `development` or `test`. An unset `NODE_ENV` is fail-closed. This guard is containment only; production mutations require a durable store, database-enforced idempotency, tenant authorization, independent review, and backup/restore evidence.

`GET /health` is a liveness endpoint and may remain healthy while the service is unable to accept writes. `GET /ready` returns HTTP 503 with `durable_store_required` when the default in-memory store is active outside explicit development/test mode, so production schedulers can keep the instance out of service until durable storage is configured.
