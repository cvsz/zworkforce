# Billing Ledger

The service accepts validated AI usage events and records invoice intents. It does not manage wallet keys, MPC shares, card data, transaction signing, or execute payment-provider operations.

## Persistence and readiness

`MemoryLedgerStore` is an ephemeral test double only. It is not shared between replicas and loses state on restart. Mutation routes require both `NODE_ENV=test` and the explicit `allowEphemeralStore: true` test-harness option. Never enable this option in deployed code. All HTTP mutation routes return HTTP 503 when `MemoryLedgerStore` is active outside that explicit test-only opt-in.

The durable PostgreSQL adapter, `PostgresLedgerStore`, persists usage records and invoice intents. This is an implementation step, not production-readiness evidence. The database migration is forward-only and must be applied by an operator or deployment job with a narrowly scoped migration identity:

```sh
psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -f services/billing-ledger/migrations/001_durable_billing_ledger.sql
psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -f services/billing-ledger/migrations/002_supported_invoice_currencies.sql
```

The migration creates database-enforced (tenant_id, idempotency_key) primary keys, payload fingerprints, constrained invoice intent fields, and schema version 1. Migration 002 adds a validated database constraint for the currently supported ISO 4217 invoice currencies: `THB` and `USD`. Adding another currency requires a reviewed application allowlist change and a forward-only database migration. The insert is the atomic idempotency claim: concurrent duplicate requests cannot create two rows. Same-key/same-payload requests replay the stored object; same-key/different-payload requests return HTTP 409.

Configure `DATABASE_URL` for the service. Production startup and any enabled billing-mutation gate require `sslmode=verify-full`. `Z_BILLING_LEDGER_REQUIRE_TLS=true` also enforces this in non-production environments. Without verified TLS, startup fails closed before opening the PostgreSQL pool. Connection and query timeouts are bounded. Do not put database credentials in logs or commit them to the repository.

- `GET /health` is a liveness endpoint only.
- `GET /ready` returns 200 only when PostgreSQL is reachable, schema version 2 is present, both ledger tables exist, and both tenant-scoped idempotency primary keys are present; otherwise it returns 503. This is a schema-admission check, not proof of production recovery or tenant isolation at the deployed gateway.
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

Invoice intents are records with status `requires_payment_processor`. The only currently supported invoice currency codes are `THB` and `USD`; other ISO 4217 codes are rejected until explicitly added in both application validation and a forward-only database migration. They do not charge cards, move customer funds, or call a payment provider.

## Verification

The Node test suite includes in-memory contract tests and PostgreSQL integration tests. To run the latter against a disposable PostgreSQL database, set `Z_BILLING_LEDGER_TEST_DATABASE_URL` to that database and apply the migration first:

```sh
npm install --prefix services/billing-ledger --package-lock-only --ignore-scripts --no-audit --no-fund
npm ci --prefix services/billing-ledger --ignore-scripts --no-audit
psql "$Z_BILLING_LEDGER_TEST_DATABASE_URL" -v ON_ERROR_STOP=1 -f services/billing-ledger/migrations/001_durable_billing_ledger.sql
npm test --prefix services/billing-ledger
```

The dedicated CI workflow also runs the repository-mandated `tests/test_v3_postgres.py` against the same disposable PostgreSQL 17 service. This checks the existing control-plane PostgreSQL contract in addition to the new billing-ledger integration tests; the test database is synthetic and must never point to a customer or production DSN.

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
