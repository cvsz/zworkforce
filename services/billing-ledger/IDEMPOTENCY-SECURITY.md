# Billing Ledger Tenant-Scoped In-Memory Idempotency

## Scope

This corrective change applies to the existing in-process `MemoryLedgerStore`
only. Both usage records and invoice intents now index idempotency entries by
`JSON.stringify([tenant_id, idempotency_key])` rather than a global key.
Structured tuple encoding prevents delimiter collisions. A replay within the
same tenant returns the original response only when financial business fields
match. A changed usage identity, token count, model, subject, invoice amount,
currency or status returns 409 without modifying the original record. Generated
timestamps and invoice IDs are excluded from semantic comparison. Different
tenants remain isolated.

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
- Same-tenant idempotency replays with changed financial business fields return
  409; exact semantic replays remain idempotent. Server-generated metadata is
  excluded from replay comparison.
- Ledger-level token normalization accepts non-negative numeric safe integers or canonical decimal-integer strings (e.g., `"0"`, `"42"`). Boolean, array, object, hexadecimal, exponent, signed/padded, fractional, and whitespace-containing strings are rejected with 400 before idempotency lookup. Omitted/null token counts retain the legacy zero default; direct-store calls require numeric safe integers.
- In-process usage token counts must be non-negative safe integers. Non-finite,
  fractional, and unsafe counts fail with 400 before any record or identity-index
  mutation. The direct `MemoryLedgerStore.recordUsage()` boundary requires numeric
  safe integers and rejects missing counts and numeric strings; `BillingLedger`
  continues to normalize valid integral numeric strings before delegation.
- Invoice-intent `amount_minor` must be a positive JavaScript safe integer at both the
  `BillingLedger` and direct `MemoryLedgerStore` boundaries. Unsafe, missing,
  fractional, non-finite, negative and zero values fail with 400 before
  idempotency lookup or mutation. The ledger retains valid numeric-string
  normalization for canonical decimal-integer strings only (`"100"` accepted; `"0100"` rejected); booleans, arrays,
  objects, hexadecimal/exponent forms and whitespace-padded strings are rejected;
  direct store calls require numeric values. This change does not authorize
  payment execution.
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

## Semantic replay hardening (draft)

- Same-key conflicting financial payloads return HTTP-style 409 at the in-process store boundary; exact replays remain idempotent.
- Replay comparison excludes only generated metadata: usage `recorded_at`, invoice `intent_id` and `created_at`.
- Returned records are defensive clones, so callers cannot mutate the in-memory financial ledger by editing a replay result.
- The HTTP financial mutation endpoints remain disabled (503). These checks are **not** durable or authenticated tenant authorization and do not permit payment execution.
