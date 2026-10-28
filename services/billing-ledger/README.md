# Billing Ledger

## Persistence and write safety

The in-memory `MemoryLedgerStore` is permitted only in automated test runs (`NODE_ENV=test`). It is an ephemeral test double: state is process-local, is not shared between replicas, and is lost on restart.

All HTTP mutation routes (`/v1/usage`, `/v1/credits`, and `/v1/invoice-intents`) return HTTP 503 when `MemoryLedgerStore` is active outside that exact test runtime. Unset, `development`, and `production` runtime modes must fail closed. Do not set `NODE_ENV=test` in a deployed environment to bypass this guard.

`GET /health` reports process liveness only; it does not prove that durable billing writes are available. This guard is containment, not production storage. Before enabling production writes, implement and verify a durable PostgreSQL adapter with database-enforced operation-scoped idempotency, atomic claim/write transactions, tenant authorization, concurrency/restart/replay tests, and backup/restore evidence. Production enablement remains an explicit release/operator gate.


This service accepts validated usage events from the AI gateway and creates idempotent billing records.

It does not manage wallet keys, MPC shares, card data, or transaction signing.

## Persistence safety

The default `MemoryLedgerStore` keeps state in process-local memory and is not durable. The HTTP mutation endpoints (`/v1/usage`, `/v1/credits`, and `/v1/invoice-intents`) return HTTP 503 whenever the in-memory store is active unless `NODE_ENV` is explicitly `test`. An unset `NODE_ENV`, `development`, `production`, `staging`, or any other value fails closed.

This guard prevents volatile writes from being presented as durable billing state; it does not provide production persistence. Before production admission, implement and validate a durable store with database-enforced idempotency uniqueness, atomic concurrent claims, migrations, restart/replay tests, and backup/restore evidence. Never set `NODE_ENV=test` in production as a workaround.
