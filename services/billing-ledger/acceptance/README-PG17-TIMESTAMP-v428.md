# Financial PostgreSQL timestamp validation (candidate v428)

## Scope

The unwired `PgFinancialStore` candidate validates `recorded_at` and
`created_at` before obtaining a PostgreSQL connection. Financial timestamps
must use an explicit RFC3339 timezone (`Z` or a numeric offset), a valid
Gregorian calendar day, and at most millisecond fractional precision.

Reject timezone-less timestamps, nonexistent calendar days, offsets outside
the accepted RFC3339 range, and sub-millisecond precision rather than silently
normalizing or truncating financial audit timestamps. Valid UTC timestamps,
offset timestamps, and leap days continue to normalize to UTC ISO strings.

## Verification

```bash
node --check services/billing-ledger/pg-store.mjs
node --test services/billing-ledger/test/pg-store-timestamp-v428.test.mjs
node --test services/billing-ledger/test/*.test.mjs
git diff --check
```

The isolated regression suite uses a synthetic pool that throws when reached.
It proves invalid timestamps are rejected before database access, but it does
not prove real PostgreSQL transaction safety, principal authorization, or
production readiness. The parent disposable PG17 acceptance and exact-head
CI must be independently verified.

## Compatibility and rollback

This is a deliberate fail-closed tightening of the **unwired** candidate
adapter input contract. Callers supplying timezone-less or non-RFC3339
timestamps must convert them to explicit UTC or offset timestamps before any
future integration. No HTTP financial mutation routes are enabled; they remain
503 for authenticated callers.

Rollback only this scoped change in a new development branch after checking
dependent commits. Never roll back financial HTTP containment or deploy the
candidate SQL to an existing or production database.

## Production blockers

Trusted authenticated principal-to-tenant resolution, real driver fault
injection, durable replay and crash recovery, migration approval, independent
review, complete exact-head required checks, backup/restore/PITR and HA
evidence remain mandatory before production admission.
