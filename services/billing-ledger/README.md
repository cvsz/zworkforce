# Billing Ledger

This service accepts validated usage events from the AI gateway and creates idempotent billing records.

It does not manage wallet keys, MPC shares, card data, or transaction signing.

## Persistence and write safety

The default `MemoryLedgerStore` is an ephemeral test double. It stores state in process-local memory, is not shared between replicas, and loses data on restart. It is permitted only in automated test runs (`NODE_ENV=test`).

All HTTP mutation routes (`/v1/usage`, `/v1/credits`, and `/v1/invoice-intents`) return HTTP 503 whenever `MemoryLedgerStore` is active unless `NODE_ENV` is exactly `test`. Unset, `development`, `production`, `staging`, and all other runtime values fail closed. Do not set `NODE_ENV=test` in a deployed environment to bypass this guard.

`GET /health` reports process liveness only; it does not prove that durable billing writes are available. This guard is containment, not production storage. Before enabling production writes, implement and verify a durable PostgreSQL adapter with database-enforced operation-scoped idempotency, atomic claim/write transactions, compatible forward-only migrations, tenant authorization, concurrency/restart/replay tests, and backup/restore evidence. Record measured RTO/RPO and the exact approved release before production admission. Production enablement remains an explicit release/operator gate.
