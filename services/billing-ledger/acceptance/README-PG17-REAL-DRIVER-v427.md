# v427 — Real Node PostgreSQL 17 driver acceptance (disposable CI only)

This candidate extends the existing PostgreSQL 17 SQL-only contract to execute
`PgFinancialStore` using a real `node-postgres` driver and a dedicated
non-superuser login. It is not connected to the application HTTP routes.

## Execution boundary

- GitHub-hosted disposable `postgres:17-alpine` service only, verified by
  the existing fail-closed disposable admission script before driver execution.
- The job maps port 5432 to the isolated runner for the duration of the job.
- The SQL contract creates the dedicated login; the runner assigns a new random
  password only after the dependency installation step and masks it in logs.
- The runtime role remains `zeaz_financial_runtime`; the login is
  `zeaz_financial_app_test`. No production DSN or customer data is used.
- The synthetic `WeakMap` principal registry is test scaffolding, **not**
  verified OIDC/JWKS authentication or an authorization implementation.

## Acceptance checks

The real driver test checks same-key replay and conflict, eight concurrent
replays, tenant authorization mismatch, cross-tenant RLS read isolation,
transactional audit cardinality, invoice intent conflicts, forbidden settlement,
transaction-local session context cleanup, and persistence after pool restart.

Run this only via the dedicated hosted workflow on the exact PR head.
`node --check` can validate syntax offline, but it is **not** real PG17 evidence.

## Outstanding blockers

- Supply chain: `pg@8.23.1` is pinned for this isolated CI step but the
  transitive dependency graph is **not yet captured in a committed lockfile**.
  Convert to a reviewed lockfile with frozen `npm ci` before production
  dependency admission. Do not treat a passing CI install as SBOM provenance.
- No network partition/uncertain COMMIT fault injection or multi-process
  crash/restart drill has been completed.
- No production IdP principal-to-tenant resolver, authorization audit, approved
  migration, PITR/restore, RTO/RPO, HA, load, release signature or SLO evidence.
- The HTTP financial mutation endpoints remain disabled (503).

## Rollback

Revert only the v427 test, workflow, and documentation commits from the draft
branch. Do not execute the disposable SQL migration against an existing
database. Do not enable production payment, credits, or invoice settlement.
