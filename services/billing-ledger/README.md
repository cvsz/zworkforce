# Billing Ledger

This service accepts validated usage events from the AI gateway and creates idempotent billing records.

It does not manage wallet keys, MPC shares, card data, or transaction signing.

## Emergency HTTP containment

The three financial HTTP mutation routes (`POST /v1/usage`, `POST /v1/credits`,
`POST /v1/invoice-intents`) return `503` to authenticated callers and do not
execute ledger methods. Unauthenticated requests continue to return `401`.
`GET /health` is unchanged. This intentionally interrupts financial writes:
upstream callers must queue/retry safely and must not treat `503` as success.

**Do not remove this containment** until trusted server-side tenant identity,
per-tenant authorization, PostgreSQL transactional idempotency, replay-conflict
checks, concurrency/restart tests, and exact-head security/CI review are complete.
Direct `BillingLedger` calls still use the legacy in-memory store and are not
production-safe. No real payments, credits, or invoices are processed here.

Rollback: revert this patch only in an isolated development checkout; do not
restore the vulnerable HTTP mutation routes in production. If containment
causes operational issues, keep the financial endpoints disabled and roll back
only unrelated changes.
