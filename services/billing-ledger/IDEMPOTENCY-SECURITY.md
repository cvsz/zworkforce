# Billing Ledger Tenant-Scoped In-Memory Idempotency

## Scope

This corrective change applies to the existing in-process `MemoryLedgerStore`
only. Both usage records and invoice intents now index idempotency entries by
`JSON.stringify([tenant_id, idempotency_key])` rather than a global key.
Structured tuple encoding prevents delimiter collisions. A replay within the
same tenant retains the prior duplicate response behavior; the same key in a
different tenant cannot return another tenant's record or invoice intent.

## Security boundaries

- Financial HTTP mutation routes remain disabled (authenticated HTTP 503).
- Direct credit writes remain disabled (503).
- Direct invoice-intent store calls reject missing tenant and idempotency identities.
- Tenant IDs are still supplied by callers of the in-process API; they are
  **not authenticated** by this change.
- Storage remains process-local and non-durable. No restart, multi-process,
  or concurrent PostgreSQL transactional idempotency guarantee is provided.
- A repeated `usage_id` under a different request key within one tenant is
  rejected with `409`; the original record and identity index are preserved.
  Another tenant may reuse the same `usage_id` independently.
- Replays with the same tenant/request key but conflicting payloads retain the
  legacy duplicate behavior. Full semantic replay-conflict detection is a
  separate admission gate; invoice intents still lack this conflict check.
- In-process usage token counts must be non-negative safe integers. Non-finite,
  fractional, and unsafe counts fail with 400 before any record or identity-index
  mutation; zero and valid integral numeric-string inputs remain supported.
- This is **not** authorization to enable payments, credits, or invoices.

## Verification

```bash
node --check services/billing-ledger/server.mjs
node --test services/billing-ledger/test/*.test.mjs
git diff --check
```

Regression coverage includes cross-tenant usage and invoice key reuse,
same-tenant replay compatibility, delimiter collision resistance, duplicate
usage-identity rejection, direct-store identity validation, and HTTP mutation
containment. Hosted CI must run on the exact candidate SHA.

## Rollback and admission

Revert only in a development checkout. Do not restore globally keyed replay
storage in production. Keep financial HTTP writes disabled if rollback is
required. Before any financial write admission, implement trusted tenant
identity, per-tenant authorization, durable PostgreSQL transactions with
uniqueness constraints, payload conflict handling, concurrency/restart tests,
independent security review, and external production evidence.
