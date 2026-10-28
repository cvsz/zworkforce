# Billing Ledger

The service accepts validated AI usage events and records invoice intents. It does not manage wallet keys, MPC shares, card data, transaction signing, or execute payment-provider operations.

## Persistence and readiness

`MemoryLedgerStore` is an ephemeral test double only. It is not shared between replicas and loses state on restart. Mutation routes require both `NODE_ENV=test` and the explicit `allowEphemeralStore: true` test-harness option. Never enable this option in deployed code. All HTTP mutation routes return HTTP 503 when `MemoryLedgerStore` is active outside that explicit test-only opt-in.

The durable PostgreSQL adapter, `PostgresLedgerStore`, persists usage records and invoice intents. This is an implementation step, not production-readiness evidence. The database migration is forward-only and must be applied by an operator or deployment job with a narrowly scoped migration identity:

```sh
psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -f services/billing-ledger/migrations/001_durable_billing_ledger.sql
```

The migration creates database-enforced (tenant_id, idempotency_key) primary keys, payload fingerprints, constrained invoice intent fields, and a schema-version marker. The insert is the atomic idempotency claim: concurrent duplicate requests cannot create two rows. Same-key/same-payload requests replay the stored object; same-key/different-payload requests return HTTP 409.

Configure `DATABASE_URL` for the service. Set `Z_BILLING_LEDGER_REQUIRE_TLS=true` for remote database connections; with that setting, the URL must specify `sslmode=verify-full`. Connection and query timeouts are bounded. Do not put database credentials in logs or commit them to the repository.

- `GET /health` is a liveness endpoint only.
- `GET /ready` returns 200 only when PostgreSQL is configured and schema version 1 is present; otherwise it returns 503.
- Without `DATABASE_URL`, the service can start for diagnostics but all production mutation routes fail closed.
- Database errors are redacted from HTTP responses.

## Explicit mutation gates

Durable `/v1/usage` and `/v1/invoice-intents` writes require all of the following:

1. A durable PostgreSQL store with the migration applied.
2. `Z_BILLING_LEDGER_ENABLE_MUTATIONS=true`.
3. `Z_BILLING_LEDGER_TENANT_AUTHZ_MODE=trusted-gateway`.
4. A trusted `X-Authenticated-Tenant` assertion matching the request's `tenant_id`.
5. The normal service bearer token.

The trusted ingress must authenticate the calling workload, authorize its tenant, remove any client-supplied `X-Authenticated-Tenant` header, and inject the verified tenant assertion. Do not expose this service directly to untrusted clients. A shared service token by itself is not tenant authorization. Keep mutation gates unset until gateway enforcement and external deployment evidence are verified.

`/v1/credits` remains disabled for durable stores. The existing absolute setter has no operation idempotency key or append-only audit contract; replace it with a reviewed, tenant-authorized adjustment API before implementing credit mutations. The memory-backed setter is only for isolated unit tests.

Invoice intents are records with status `requires_payment_processor`. They do not charge cards, move customer funds, or call a payment provider.

## Verification

The Node test suite includes in-memory contract tests and PostgreSQL integration tests. To run the latter against a disposable PostgreSQL database, set `Z_BILLING_LEDGER_TEST_DATABASE_URL` to that database and apply the migration first:

```sh
npm install --prefix services/billing-ledger --package-lock-only --ignore-scripts --no-audit --no-fund
npm ci --prefix services/billing-ledger --ignore-scripts --no-audit
psql "$Z_BILLING_LEDGER_TEST_DATABASE_URL" -v ON_ERROR_STOP=1 -f services/billing-ledger/migrations/001_durable_billing_ledger.sql
npm test --prefix services/billing-ledger
```

Never point integration tests at a customer or production database. Tests use synthetic tenant IDs and append-only rows in a disposable database.

## Remaining production gates

This implementation is a code change, not production-readiness evidence. Before production admission, still require:

- A committed dependency lockfile and dependency/SBOM review for the Node service.
- Independent security review of the trusted-gateway tenant assertion and service-token rotation.
- Tenant isolation tests at the deployed ingress, not only unit/integration tests.
- Backup/restore and PITR drills against the target PostgreSQL service, with measured RTO/RPO.
- Monitoring/alerts for readiness failures, database pool saturation, 5xx rates, duplicate/conflicting idempotency requests, and migration drift.
- Signed release provenance, a reviewed rollout/rollback plan, and external deployment verification.
- An audited append-only credit-adjustment API before enabling credit writes.

No production traffic, customer money movement, payment execution, or destructive migration is authorized by this change.
