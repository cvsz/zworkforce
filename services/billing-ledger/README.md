# Billing Ledger

This service accepts validated usage events from the AI gateway and creates idempotent billing records.

It does not manage wallet keys, MPC shares, card data, or transaction signing.

## Persistence safety

The default `MemoryLedgerStore` keeps state in process-local memory and is not durable. The HTTP mutation endpoints (`/v1/usage`, `/v1/credits`, and `/v1/invoice-intents`) return HTTP 503 whenever the in-memory store is active unless `NODE_ENV` is explicitly `test`. An unset `NODE_ENV`, `development`, `production`, `staging`, or any other value fails closed.

This guard prevents volatile writes from being presented as durable billing state; it does not provide production persistence. Before production admission, implement and validate a durable store with database-enforced idempotency uniqueness, atomic concurrent claims, migrations, restart/replay tests, and backup/restore evidence. Never set `NODE_ENV=test` in production as a workaround.
