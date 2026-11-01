# Financial Membership Lookup — Disposable Candidate v433

This change is **not** a production identity integration. It introduces a
PostgreSQL 17 synthetic membership authority and a dedicated least-privilege
read adapter, stacked on the pinned-JWKS candidate.

## Trust boundary

1. `createFinancialTenantResolver` verifies an RS256 JWT against an operator-pinned
   trusted JWKS and extracts the signed subject/tenant identifiers.
2. `createPgMembershipLookup` performs a **fresh** database lookup for each
   verification. The membership table is authoritative for the disposable test
   only; JWT role claims, request body tenant IDs and caller-supplied membership
   objects are never authorization evidence.
3. The membership DB login is separate from the financial runtime login. It
   must be non-superuser, non-BYPASSRLS and not a member of the financial runtime
   role. Its sole membership grant is EXECUTE on a parameterized SECURITY DEFINER
   function; it has no SELECT on membership or ledger tables.
4. Inactive, revoked, unknown or viewer memberships deny `billing:write`.
   Database outage, privilege drift or ambiguous records fail closed.
5. This is a **candidate**. No production OIDC, authoritative customer membership
   migration, webhook, payment, or financial HTTP mutation is enabled.

## CI evidence

The disposable PostgreSQL runner applies `0002_financial_membership_disposable.sql`
only after verifying the isolated PostgreSQL 17 container. SQL acceptance verifies
least privilege, tenant/role separation and revocation. Real `pg` driver acceptance
combines signed synthetic JWTs with a separate membership login and negative cases.
The in-process test suite checks parameter binding, invalid inputs, role drift,
connection discard and unavailable databases.

## Operator gates

Before any production migration, independently approve the membership source of
truth, account lifecycle and revocation SLA, role provisioning, audited writes,
backup/restore, data retention, monitoring, signed releases, real IdP/JWKS
rotation and cross-service tenant contract. Never reuse the synthetic test login,
fixtures or signing keys. Keep all financial HTTP mutations disabled.

Rollback candidate: revert the isolated branch/PR. Do not run DROP statements on
production and do not re-enable legacy in-memory financial writes.
