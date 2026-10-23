# Financial PostgreSQL 17 Disposable Admission (v424 candidate)

## Scope

This PR adds a **test-only** PostgreSQL 17 schema and hosted SQL acceptance job.
The migration is **not authorized for production**, and no runtime database
connection, payment execution, credit mutation, invoice settlement, or HTTP
financial write endpoint is enabled. The current authenticated HTTP mutation
response remains 503.

## Verified only when the exact-head hosted job passes

- A new PostgreSQL 17 service is created by the GitHub-hosted job.
- The runner verifies the Docker service identity, disposable label, expected
  database, major version, and absence of the financial schema **before**
  executing any SQL.
- Tenant-scoped uniqueness, RLS reads/writes, initial invoice status,
  JavaScript safe-integer range, transactional audit insert, append-only audit,
  rollback, and competing inserts are exercised with synthetic records.
- No production DSN, secrets, Kubernetes credentials, or customer records are
  accessed. The job does not establish that the application uses this adapter.

## Operator gates that remain BLOCKED

1. Implement and independently review a real PostgreSQL adapter with a
   dedicated least-privilege login; never use the schema owner or a superuser.
2. Bind tenant context to verified server-side identity. A client-controlled
   `SET LOCAL zeaz.tenant_id` is **not authentication**.
3. Verify semantic same-key replay (not just SQL uniqueness), multi-process
   retries, pool restarts, crash recovery, and audit durability using the real
   application driver.
4. Establish approved migrations, backups, restore/PITR drills, observed
   RTO/RPO, load limits, SLOs, release provenance, and rollback artifacts.
5. Obtain independent review and explicit operator authorization before any
   deployment or production database change.

## Reproduce (isolated CI only)

Run `Financial PostgreSQL 17 Disposable Admission` against the exact PR
commit in GitHub Actions. The script refuses execution unless it receives an
attested, empty, disposable Docker PostgreSQL 17 service. Do not set the
attestation flag on any persistent or production database.

## Rollback

Close/revert this draft PR without touching the production database. If CI
fails, preserve logs and investigate in a new disposable service; do not
disable RLS, weaken constraints, reuse an existing database, or bypass checks.
