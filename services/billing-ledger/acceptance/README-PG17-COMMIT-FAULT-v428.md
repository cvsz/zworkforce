# PG17 Uncertain COMMIT Acknowledgement Acceptance — v428

**Scope:** synthetic, disposable GitHub-hosted PostgreSQL 17 only. This change adds test evidence and does not wire financial HTTP mutations, execute payments, or change production databases.

## Failure model

A query wrapper intercepts exactly one COMMIT per test:
- `before-commit`: fail before forwarding COMMIT to PostgreSQL; the adapter rolls back and discards the uncertain pooled connection.
- `after-commit`: PostgreSQL completes COMMIT but the wrapper discards its acknowledgement; the adapter attempts rollback and discards the uncertain connection.

Both cases restart the `pg` pool, then retry the identical idempotency key. The tests cover usage and invoice intent separately, asserting one durable record and one tenant-scoped audit event after reconciliation. A further same-key retry with a new timestamp (and generated invoice identifier) must not create another record or audit event.

The acknowledgement failure is deterministic **client-side fault injection** against a real disposable database, **not** a network partition, process crash, or PostgreSQL failover. A failing COMMIT must never be reported as a confirmed success, and callers must reconcile using the same key rather than issue a fresh financial identity.

## Verification

The existing `.github/workflows/financial-pg17-disposable.yml` installs `pg@8.23.1` in the disposable runner and executes:

```bash
node --test services/billing-ledger/acceptance/pg17_real_driver_v427.test.mjs services/billing-ledger/acceptance/pg17_commit_ack_fault_v428.test.mjs
```

Do not run against a persistent database or real credentials. Evidence is valid only when the workflow on the exact PR head passes and its job logs show all fault cases.

## Remaining gates

- Genuine network disruption and database failover/partition fault injection.
- Multi-process hard-kill and restart recovery with durable audit reconciliation.
- Authenticated IdP-to-tenant authorization and production role provisioning.
- Committed frozen dependency lockfile, SBOM/provenance and signed release.
- Approved migration, backup/restore/PITR, observed RTO/RPO and SLO evidence.
- Exact-head required CI, independent security review and operator GO.

**Rollback:** revert the scoped v428 test, workflow and documentation commits on the draft branch. Production state remains unchanged.
