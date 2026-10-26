# Billing Ledger

This service accepts validated usage events from the AI gateway and creates idempotent billing records.

It does not manage wallet keys, MPC shares, card data, or transaction signing.

## Emergency HTTP containment

The financial HTTP mutation routes (`POST /v1/usage`, `POST /v1/credits`, and
`POST /v1/invoice-intents`) return `503` to authenticated callers without
invoking the ledger. Unauthenticated requests continue to return `401`.
`GET /health` remains available. Query parameters cannot bypass containment.
Credit writes are also disabled at both the direct `BillingLedger` and
`MemoryLedgerStore` boundaries.

This intentionally interrupts financial writes. Upstream callers must queue or
retry safely and must not treat `503` as success. The invoice-intent method
remains available only as an in-process synthetic contract; the HTTP route is
disabled and no payment processor is called.

Do not remove this containment until all of the following are independently
verified:

- Trusted server-side tenant identity and per-tenant authorization.
- Durable PostgreSQL transactions and idempotency keys scoped to tenant and operation.
- Same-key/different-payload replay rejection.
- Concurrency, restart, and cross-tenant isolation tests.
- Exact-head CI/security checks and independent review.
- External backup/restore, DR/HA, and rollback evidence.

## Validation

```bash
node --check services/billing-ledger/server.mjs
node --test services/billing-ledger/test/*.test.mjs
```

## Rollback

Do not restore the vulnerable financial HTTP mutation routes in production. If
containment causes operational issues, keep the routes disabled and roll back
only unrelated changes. Re-enable financial writes only in a separately reviewed
candidate after every admission requirement above has passed.
