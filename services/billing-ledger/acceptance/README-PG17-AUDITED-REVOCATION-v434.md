# Audited Financial Membership Revocation — Disposable Candidate v434

**Scope:** PostgreSQL 17 disposable CI database only. This is not a production
identity authority, customer migration, revocation API, or financial release.

## Contract

- A dedicated non-superuser `zeaz_financial_membership_revoker_app_test` inherits
  only the `zeaz_financial_membership_revoker` role. It has no direct membership,
  ledger or audit table privileges and cannot issue billing mutations.
- The sole authorized mutation is
  `zeaz_financial.revoke_billing_membership(request_id, subject, tenant, reason)`.
  It is a bounded `SECURITY DEFINER` function with a fixed `search_path`,
  parameter validation, a transaction-scoped replay lock, and exact tenant/subject
  matching. The definer is a dedicated NOLOGIN, non-superuser role with
  column-limited membership SELECT/UPDATE and audit SELECT/INSERT, not the
  postgres superuser. Its `session_user` is recorded as the audit actor; no actor value
  can be supplied by an untrusted request.
- The membership update and append-only-to-app audit insertion are atomic.
  A repeated identical request ID returns `false` without a second event.
  A request ID reused for another subject, tenant, reason, or login is rejected.
  Unknown/inactive memberships fail closed; no implicit grants or reactivation.
- The reader role cannot execute the revoker function; the revoker cannot read
  the ledger or audit tables. The database owner/DBA remains privileged and
  therefore requires separate operator governance and audit-log retention.
- The v433 membership lookup is unchanged and must observe a revoked membership
  as inactive on the next request. No authorization caching is introduced.

## CI acceptance

`financial-pg17-membership.yml` first runs v433 identity + real driver tests,
then applies `0003_financial_membership_audit_disposable.sql` and executes
`pg17_membership_revocation_audit_v434.sql` in the same attested disposable
PostgreSQL 17 container. The SQL acceptance asserts:

1. Revoker least privilege and reader inability to revoke.
2. First revocation, idempotent replay and conflicting replay denial.
3. Exactly one actor-attributed audit event, durable state change and no
   cross-tenant modification.
4. Transaction rollback removes both membership mutation and audit event.

The same workflow also runs two real `node-postgres` concurrency scenarios:
identical request IDs must yield exactly one new mutation, and two different
request IDs racing to revoke one membership must yield one success and one
fail-closed rejection. A PostgreSQL-side check asserts one audit row per
membership. The driver uses a random disposable-only revoker password.

A green CI run proves only these disposable contracts. It does not establish
a production operator identity, revocation SLA, WORM/off-host audit retention,
customer IdP integration, cross-service propagation, HA, PITR or DR.

## Operator gates and rollback

Before production consideration, identify and independently approve the
customer membership source of truth, revocation authority and dual-control
process, login provisioning, event retention policy, external audit export,
alerting, backup/restore/PITR, cross-service tenant consistency, IdP/JWKS,
staging negative E2E and signed release. Do not copy synthetic fixtures,
database roles, passwords or migration into production.

Rollback this **candidate branch/PR** without applying SQL to any persistent
database. Never restore financial HTTP mutations as a rollback action.
