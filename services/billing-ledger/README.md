# Billing Ledger

This service accepts validated usage events from the AI gateway and creates idempotent billing records.

It does not manage wallet keys, MPC shares, card data, or transaction signing.

## Persistence safety

The default `MemoryLedgerStore` is ephemeral and is not durable, shared across replicas, or restart-safe. HTTP mutation endpoints (`/v1/usage`, `/v1/credits`, and `/v1/invoice-intents`) return HTTP 503 whenever the in-memory store is active unless the server is explicitly created with `allowEphemeralStore: true` and `NODE_ENV` is exactly `development` or `test`.

The option defaults to `false`. Setting `NODE_ENV=development` or `NODE_ENV=test` alone does not enable memory-backed writes. The explicit option cannot enable ephemeral writes in `production`, `staging`, or any other runtime mode. Keep this option disabled outside local development and automated tests.

This guard prevents volatile writes from being presented as durable billing state. It does not provide production persistence. Before production admission, implement and validate a durable store with database-backed idempotency uniqueness, atomic concurrent claims, migration compatibility, backup/restore, and restart/replay tests. Never set `NODE_ENV=development` in production as a workaround.
