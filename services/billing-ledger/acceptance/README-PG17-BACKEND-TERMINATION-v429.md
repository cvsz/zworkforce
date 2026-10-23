# PostgreSQL 17 Backend-Termination Acceptance — v429

**Scope:** GitHub-hosted, disposable PostgreSQL 17 only. This candidate is not connected to customer billing or production HTTP endpoints.

## Failure model

The test uses two independent `node-postgres` pools with the same dedicated non-superuser login. Immediately before the adapter sends `COMMIT`, a separate connection calls `pg_terminate_backend(pid)` for the active test transaction. This is an actual PostgreSQL backend termination, not a synthetic exception or a network partition. The expected outcome is a failed client transaction, a discarded pooled session, and a server-side rollback.

For **usage** and **invoice intent** separately, the test asserts:
1. Exactly one targeted backend was terminated; the connection was discarded.
2. After a full driver-pool restart, there is **zero** committed financial record and **zero** audit record.
3. Retrying with the **same** tenant and idempotency key creates exactly one record and one audit event.
4. A second same-key replay with changed generated metadata leaves cardinality at one.

The test refuses to run unless the disposable CI marker, loopback host, fixed test database/user, and ephemeral password are present. The workflow's PostgreSQL container identity is passed only to the test. No production secrets are logged.

## Evidence boundary

- Local `node --check` validates syntax only; it is **not** real PostgreSQL acceptance.
- Only a successful **exact-head** `Financial PostgreSQL 17 Disposable Admission` run proves the new server-side backend termination scenarios executed.
- This does **not** prove actual network partition, process hard-kill, failover/HA, multi-region, production identity authorization, or production backup/restore.
- Financial HTTP mutations remain disabled. Never deploy this test against a persistent database.

## Operator and rollback

The workflow requires no production credentials, DNS changes, payments, ad spend, trades, or migrations. To revert, remove the v429 test and documentation from the draft branch and restore the prior driver test command/environment in `.github/workflows/financial-pg17-disposable.yml`. Keep financial HTTP mutations disabled and do not bypass required CI/review gates.
