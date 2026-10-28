# Billing Ledger

This service accepts validated usage events from the AI gateway and creates idempotent billing records.

It does not manage wallet keys, MPC shares, card data, or transaction signing.


## Persistence safety

The default `MemoryLedgerStore` is ephemeral and is suitable only for explicit local development and automated tests. Mutating HTTP endpoints (`/v1/usage`, `/v1/credits`, and `/v1/invoice-intents`) return HTTP 503 unless `NODE_ENV` is explicitly `development` or `test` when the in-memory store is active. An unset `NODE_ENV`, `production`, `staging`, or any other value fails closed.

This guard prevents volatile writes from being presented as durable billing state. It does not provide production persistence. Before production admission, implement and validate a durable store with database-backed uniqueness for idempotency keys, atomic concurrent claims, migrations, backup/restore, and restart/replay tests. Do not set `NODE_ENV=development` in production as a workaround.
