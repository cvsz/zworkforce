# PostgreSQL 17 Financial Adapter Candidate — v426

**Status: test-only, not connected to any production route.**

This change adds a dependency-injected `PgFinancialStore` prototype and a
disposable PostgreSQL 17 dedicated-login acceptance contract. It does not
change the running billing server, enable financial HTTP writes, execute
payments, apply migrations to customer data, or authorize production use.

## Security contract

- `resolveTenant(principal)` MUST be a separately reviewed server-side
  AuthN/AuthZ resolver. Do not implement it by returning a tenant ID from
  headers, request bodies, or other untrusted caller claims. This PR does not
  supply that resolver and therefore **does not establish tenant authorization**.
- The operator provisions a separate non-privileged PostgreSQL LOGIN and grants
  membership in the schema's `zeaz_financial_runtime` NOLOGIN role. Configure
  `expectedLoginRole` to that exact login. Never use a superuser, schema owner,
  BYPASSRLS role, or arbitrary caller-controlled role name.
- Every operation begins a transaction, verifies login privilege flags,
  activates `SET LOCAL ROLE zeaz_financial_runtime`, sets a parameterized
  transaction-local tenant context, and releases its connection after
  commit/rollback. SQL inserts and lookups are tenant-scoped and parameterized.
- Usage and invoice insertions use database unique constraints and
  `ON CONFLICT DO NOTHING` followed by semantic replay verification.
  Conflicting replay and cross-key identity reuse return 409. Invoice
  settlement and credits remain unauthorized.
- Unknown financial fields are rejected instead of silently discarded. This
  adapter is intentionally **not** a drop-in replacement for the existing
  `MemoryLedgerStore` API; it requires a trusted principal argument.

## Evidence and limitations

Run offline: `node --test services/billing-ledger/test/pg-store-v426.test.mjs`.
These tests use a fake pool and verify query order, tenant mismatch, role
checks, replay conflicts, rollback, and release. They are **not** evidence
that the Node adapter ran against PostgreSQL.

The existing disposable PG17 runner additionally executes
`acceptance/pg17_dedicated_login_contract.sql`, exercising the NOLOGIN
runtime-role membership, `SET LOCAL ROLE`, RLS, transactional audit, and
transaction-local reset against a synthetic login. This is real PostgreSQL
evidence **only if the exact-head hosted job succeeds**.

## Blocked before production

1. Implement and independently verify the authenticated principal-to-tenant
   resolver and real `pg` driver pool; do not inject a fake or caller-controlled
   resolver.
2. Run end-to-end real-driver concurrent replay, process crash/restart,
   connection pool reuse, transaction rollback, and audit reconciliation tests.
3. Verify production migration planning separately, with tested backup/restore,
   PITR, rollback, signed release provenance, and operator approval.
4. Obtain full exact-head CI, independent security approval, required checks,
   and branch-protection evidence before any merge.
5. Preserve the HTTP 503 financial mutation containment and never execute
   real customer money operations under this candidate.

## Rollback

Close the draft PR or revert the scoped feature-branch commits. No existing
production database schema, endpoint, secret, or deployment is changed.
