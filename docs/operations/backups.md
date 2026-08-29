# Backup and Restore Runbook

## Scope

Backups apply only to operator-approved durable stores:

- workspace metadata store
- agent job store
- agent queue dead-letter store
- billing ledger
- audit/event store
- generated project object store

## Exclusions

Do not back up provider credentials, wallet signing keys, MPC shares, card data, or production payment secrets into application-owned stores.

## Minimum policy

| Data | RPO | RTO | Retention |
|---|---:|---:|---:|
| Billing ledger | 15 min | 4 h | 7 years or jurisdiction policy |
| Audit events | 15 min | 4 h | 1 year minimum |
| Workspace metadata | 1 h | 8 h | tenant retention policy |
| Agent jobs | 1 h | 8 h | 90 days default |

## Restore checklist

1. Confirm incident commander and operator approval.
2. Restore into isolated staging first.
3. Run integrity checks and idempotency duplicate checks.
4. Verify service health endpoints.
5. Promote to production only after rollback notes are updated.
