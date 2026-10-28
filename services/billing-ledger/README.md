# Billing Ledger

This service accepts validated usage events from the AI gateway and creates idempotent billing records.

It does not manage wallet keys, MPC shares, card data, or transaction signing.

## Persistence and write safety

The default `MemoryLedgerStore` is an ephemeral test double. It stores state in process-local memory, is not shared between replicas, and loses data on restart. HTTP mutation routes require both `NODE_ENV=test` and the explicit `allowEphemeralStore: true` option; setting `NODE_ENV=test` alone does not enable memory-backed writes. Never enable this option in deployed code.

All HTTP mutation routes (`/v1/usage`, `/v1/credits`, and `/v1/invoice-intents`) return HTTP 503 whenever `MemoryLedgerStore` is active unless the server is explicitly constructed with `allowEphemeralStore: true` while `NODE_ENV` is exactly `test`. Unset, `development`, `production`, `staging`, and all other runtime values fail closed even when the option is set.

`GET /health` reports process liveness only; it does not prove that durable billing writes are available. This guard is containment, not production storage. Before enabling production writes, implement and verify a durable PostgreSQL adapter with database-enforced operation-scoped idempotency, atomic claim/write transactions, compatible forward-only migrations, tenant authorization, concurrency/restart/replay tests, and backup/restore evidence. Record measured RTO/RPO and the exact approved release before production admission. Production enablement remains an explicit release/operator gate.
