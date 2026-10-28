import assert from "node:assert/strict";
import { randomUUID } from "node:crypto";
import test from "node:test";
import { Pool } from "pg";

import { BillingLedger } from "../server.mjs";
import { PostgresLedgerStore } from "../postgres-store.mjs";

const databaseUrl = process.env.Z_BILLING_LEDGER_TEST_DATABASE_URL;

test("PostgreSQL ledger persists idempotency across concurrency and a new store instance", {
  skip: !databaseUrl,
}, async (t) => {
  const pool = new Pool({
    connectionString: databaseUrl,
    max: 10,
    connectionTimeoutMillis: 3000,
    statement_timeout: 5000,
    query_timeout: 7000,
    application_name: "billing-ledger-integration-test",
  });
  const restartedPool = new Pool({
    connectionString: databaseUrl,
    max: 2,
    connectionTimeoutMillis: 3000,
    statement_timeout: 5000,
    query_timeout: 7000,
    application_name: "billing-ledger-restart-test",
  });
  t.after(async () => {
    await Promise.all([pool.end(), restartedPool.end()]);
  });

  const tenantId = `ci-${randomUUID()}`;
  const key = `usage-${randomUUID()}`;
  const payload = {
    tenant_id: tenantId,
    usage_id: `usage-id-${randomUUID()}`,
    idempotency_key: key,
    subject_id: "synthetic-subject",
    model: "test:model",
    input_tokens: 12,
    output_tokens: 7,
    recorded_at: "2026-10-28T00:00:00.000Z",
    event_type: "ai.usage.recorded.v1",
    event_version: "v1",
  };

  const ledger = new BillingLedger({ store: new PostgresLedgerStore({ pool }) });
  assert.equal(await ledger.store.assertReady(), true);

  const concurrent = await Promise.all(
    Array.from({ length: 8 }, () => ledger.recordUsage(payload)),
  );
  assert.equal(concurrent.filter((result) => result.duplicate === false).length, 1);
  assert.equal(concurrent.filter((result) => result.duplicate === true).length, 7);
  assert.ok(concurrent.every((result) => result.record.tenant_id === tenantId));

  const restartedLedger = new BillingLedger({
    store: new PostgresLedgerStore({ pool: restartedPool }),
  });
  const replay = await restartedLedger.recordUsage(payload);
  assert.equal(replay.duplicate, true);
  assert.equal(replay.record.idempotency_key, key);

  await assert.rejects(
    restartedLedger.recordUsage({ ...payload, output_tokens: 99 }),
    (error) => error.status === 409,
  );

  const otherTenant = await restartedLedger.recordUsage({
    ...payload,
    tenant_id: `ci-${randomUUID()}`,
  });
  assert.equal(otherTenant.duplicate, false);
});

test("PostgreSQL invoice intents are durable and reject changed-payload replay", {
  skip: !databaseUrl,
}, async (t) => {
  const pool = new Pool({
    connectionString: databaseUrl,
    max: 8,
    connectionTimeoutMillis: 3000,
    statement_timeout: 5000,
    query_timeout: 7000,
    application_name: "billing-ledger-invoice-test",
  });
  t.after(() => pool.end());

  const tenantId = `ci-${randomUUID()}`;
  const key = `invoice-${randomUUID()}`;
  const input = {
    tenant_id: tenantId,
    idempotency_key: key,
    currency: "USD",
    amount_minor: 1234,
  };
  const ledger = new BillingLedger({ store: new PostgresLedgerStore({ pool }) });

  const concurrent = await Promise.all(
    Array.from({ length: 6 }, () => ledger.createInvoiceIntent(input)),
  );
  assert.equal(new Set(concurrent.map((intent) => intent.intent_id)).size, 1);
  assert.ok(concurrent.every((intent) => intent.status === "requires_payment_processor"));

  await assert.rejects(
    ledger.createInvoiceIntent({ ...input, amount_minor: 4321 }),
    (error) => error.status === 409,
  );
});

test("PostgreSQL constraints reject negative usage counts and unsafe invoice amounts", {
  skip: !databaseUrl,
}, async (t) => {
  const pool = new Pool({
    connectionString: databaseUrl,
    max: 2,
    connectionTimeoutMillis: 3000,
    statement_timeout: 5000,
    query_timeout: 7000,
    application_name: "billing-ledger-schema-constraints-test",
  });
  t.after(() => pool.end());

  await assert.rejects(
    pool.query(
      `INSERT INTO billing_usage_records
         (tenant_id, idempotency_key, usage_id, input_tokens, output_tokens, payload_hash, record)
       VALUES ($1, $2, $3, $4, $5, $6, $7::jsonb)`,
      [
        `ci-${randomUUID()}`,
        `invalid-usage-${randomUUID()}`,
        `usage-${randomUUID()}`,
        -1,
        0,
        "a".repeat(64),
        JSON.stringify({ input_tokens: -1, output_tokens: 0 }),
      ],
    ),
    (error) => error.code === "23514",
  );

  await assert.rejects(
    pool.query(
      `INSERT INTO billing_invoice_intents
         (tenant_id, idempotency_key, intent_id, payload_hash, currency, amount_minor, status, intent)
       VALUES ($1, $2, $3, $4, $5, $6, $7, $8::jsonb)`,
      [
        `ci-${randomUUID()}`,
        `invalid-invoice-${randomUUID()}`,
        `intent-${randomUUID()}`,
        "b".repeat(64),
        "USD",
        Number.MAX_SAFE_INTEGER + 1,
        "requires_payment_processor",
        JSON.stringify({ amount_minor: Number.MAX_SAFE_INTEGER + 1 }),
      ],
    ),
    (error) => error.code === "23514",
  );
});
