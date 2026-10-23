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

## Strict service Authorization scheme

Authenticated service calls must use `Authorization: Bearer <token>`. The
scheme is case-insensitive and may contain multiple separating spaces, but a
bare token, Basic/Token scheme, tab separator, or appended second credential
returns 401. Token comparison remains length-checked and timing-safe. Missing
service credentials fail closed. This deliberately removes nonstandard bare
token compatibility; callers must use the documented Bearer format.

Verify the HTTP contract with:

```bash
node --check services/billing-ledger/server.mjs
node --test services/billing-ledger/test/*.test.mjs
```

Rollback only the Bearer parsing change on a development branch if a verified
compatibility issue requires it. Never remove financial HTTP containment or
enable financial writes as part of rollback. Downstream stacked billing PRs
must be reconciled with this branch before admission.
