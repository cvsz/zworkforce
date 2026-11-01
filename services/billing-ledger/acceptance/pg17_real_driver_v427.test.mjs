// Disposable PostgreSQL 17 + real node-postgres driver acceptance only.
// No production DSN, payment execution, or authenticated IdP integration.
import assert from 'node:assert/strict';
import { randomUUID } from 'node:crypto';
import test from 'node:test';
import pg from 'pg';
import { PgFinancialStore } from '../pg-store.mjs';

for (const [key, expected] of Object.entries({
  Z_FINANCIAL_PG17_REAL_DRIVER: 'true',
  PGHOST: '127.0.0.1',
  PGDATABASE: 'zeaz_financial_acceptance',
  PGUSER: 'zeaz_financial_app_test',
})) {
  if (process.env[key] !== expected) throw new Error(`Disposable admission refused: ${key}`);
}
if (!process.env.PG_TEST_PASSWORD || !/^\d+$/.test(String(process.env.PGPORT || '5432'))) {
  throw new Error('Disposable PostgreSQL driver credentials/port missing');
}

const { Pool } = pg;
const makePool = () => new Pool({
  host: '127.0.0.1', port: Number(process.env.PGPORT || 5432),
  database: 'zeaz_financial_acceptance', user: 'zeaz_financial_app_test',
  password: process.env.PG_TEST_PASSWORD, max: 4,
  connectionTimeoutMillis: 5000, idleTimeoutMillis: 2000,
  statement_timeout: 5000, query_timeout: 7000,
  application_name: 'zeaz_financial_disposable_v427',
});

// Opaque registry is synthetic only, not an OIDC/JWKS authorization provider.
const verifiedTenants = new WeakMap();
const principalA = Object.freeze({ id: randomUUID() });
const principalB = Object.freeze({ id: randomUUID() });
const tenantA = `ci-${randomUUID()}`;
const tenantB = `ci-${randomUUID()}`;
verifiedTenants.set(principalA, tenantA);
verifiedTenants.set(principalB, tenantB);
const resolveTenant = async principal => {
  const tenant = principal && verifiedTenants.get(principal);
  if (!tenant) throw new Error('Unauthenticated synthetic principal');
  return tenant;
};
const storeFor = pool => new PgFinancialStore({
  pool, resolveTenant, expectedLoginRole: 'zeaz_financial_app_test',
});
const usageId = randomUUID();
const key = randomUUID();
const usage = (tenant, changes = {}) => ({
  event_type: 'ai.usage.recorded.v1', event_version: 'v1', tenant_id: tenant,
  usage_id: usageId, idempotency_key: key, subject_id: 'synthetic-subject',
  model: 'synthetic-model', input_tokens: 7, output_tokens: 3,
  recorded_at: '2026-10-24T00:00:00.000Z', ...changes,
});

await test('PG17 real driver: tenant binding, replay, concurrency, pool restart, audit', async () => {
  let pool = makePool();
  try {
    let store = storeFor(pool);
    assert.equal((await store.recordUsage(principalA, usage(tenantA))).duplicate, false);
    await assert.rejects(store.recordUsage(principalA, usage(tenantB)), e => e.status === 403);
    const replay = await Promise.all(Array.from({ length: 8 }, () =>
      store.recordUsage(principalA, usage(tenantA, {
        recorded_at: '2026-10-25T00:00:00.000Z',
      }))));
    assert.equal(replay.filter(r => r.duplicate).length, 8);
    await assert.rejects(store.recordUsage(principalA, usage(tenantA, {
      input_tokens: 8,
    })), e => e.status === 409);
    assert.equal((await store.recordUsage(principalB, usage(tenantB))).duplicate, false);
    for (const [principal, tenant] of [[principalA, tenantA], [principalB, tenantB]]) {
      const counts = await store.withTenant(principal, tenant, async client => {
        const records = await client.query('SELECT count(*)::int AS n FROM zeaz_financial.usage_events');
        const audits = await client.query('SELECT count(*)::int AS n FROM zeaz_financial.audit_events');
        return { records: records.rows[0].n, audits: audits.rows[0].n };
      });
      assert.deepEqual(counts, { records: 1, audits: 1 });
    }
    const invoice = {
      tenant_id: tenantA, intent_id: randomUUID(), idempotency_key: randomUUID(),
      amount_minor: 1200, currency: 'USD', status: 'requires_payment_processor',
      created_at: '2026-10-24T00:00:00.000Z',
    };
    const created = await store.createInvoiceIntent(principalA, invoice);
    assert.equal(created.amount_minor, 1200);
    const duplicate = await store.createInvoiceIntent(principalA, {
      ...invoice, intent_id: randomUUID(), created_at: '2026-10-25T00:00:00.000Z',
    });
    assert.equal(duplicate.intent_id, created.intent_id);
    await assert.rejects(store.createInvoiceIntent(principalA, {
      ...invoice, amount_minor: 1201,
    }), e => e.status === 409);
    await assert.rejects(store.createInvoiceIntent(principalA, {
      ...invoice, status: 'paid',
    }), e => e.status === 503);
    const after = await pool.query("SELECT current_user AS role, coalesce(current_setting('zeaz.tenant_id', true), '') AS tenant");
    assert.equal(after.rows[0].role, 'zeaz_financial_app_test');
    assert.equal(after.rows[0].tenant, '');
    await pool.end();
    pool = makePool();
    store = storeFor(pool);
    assert.equal((await store.recordUsage(principalA, usage(tenantA))).duplicate, true);
    const audit = await store.withTenant(principalA, tenantA, async client => {
      const rows = await client.query('SELECT entity_type, count(*)::int AS n FROM zeaz_financial.audit_events GROUP BY entity_type ORDER BY entity_type');
      return rows.rows;
    });
    assert.deepEqual(audit, [
      { entity_type: 'invoice_intent', n: 1 }, { entity_type: 'usage', n: 1 },
    ]);
  } finally {
    await pool.end();
  }
});
