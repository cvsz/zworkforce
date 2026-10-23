// Disposable PostgreSQL 17 acceptance: terminate a real backend before COMMIT.
// Not a production database, network partition, PostgreSQL failover, or IdP test.
import assert from 'node:assert/strict';
import { randomUUID } from 'node:crypto';
import test from 'node:test';
import pg from 'pg';
import { PgFinancialStore } from '../pg-store.mjs';

for (const [name, expected] of Object.entries({
  Z_FINANCIAL_PG17_REAL_DRIVER: 'true',
  Z_FINANCIAL_PG17_BACKEND_TERMINATION: 'true',
  PGHOST: '127.0.0.1',
  PGDATABASE: 'zeaz_financial_acceptance',
  PGUSER: 'zeaz_financial_app_test',
})) {
  if (process.env[name] !== expected) throw new Error(`Disposable-only admission refused: ${name}`);
}
if (!process.env.PG_TEST_PASSWORD || !/^\d+$/.test(String(process.env.PGPORT || '5432'))) {
  throw new Error('Disposable PostgreSQL credentials/port required');
}

function newPool() {
  return new pg.Pool({
    host: '127.0.0.1', port: Number(process.env.PGPORT || 5432),
    database: 'zeaz_financial_acceptance', user: 'zeaz_financial_app_test',
    password: process.env.PG_TEST_PASSWORD, max: 2,
    connectionTimeoutMillis: 5000, idleTimeoutMillis: 2000,
    statement_timeout: 5000, query_timeout: 7000,
    application_name: 'zeaz_financial_disposable_backend_termination_v429',
  });
}

for (const kind of ['usage', 'invoice']) {
  test(`PG17 ${kind}: real backend termination before COMMIT is recoverable by same-key retry`, async () => {
    const principal = Object.freeze({ nonce: randomUUID() });
    const tenant = `ci-${randomUUID()}`;
    const resolveTenant = async candidate => {
      if (candidate !== principal) throw new Error('Unverified synthetic principal');
      return tenant;
    };
    const storeFor = db => new PgFinancialStore({
      pool: db, resolveTenant, expectedLoginRole: 'zeaz_financial_app_test',
    });
    const key = randomUUID();
    const payload = kind === 'usage'
      ? {
          event_type: 'ai.usage.recorded.v1', event_version: 'v1',
          tenant_id: tenant, usage_id: randomUUID(), idempotency_key: key,
          subject_id: 'synthetic', model: 'synthetic', input_tokens: 4,
          output_tokens: 6, recorded_at: '2026-10-24T00:00:00.000Z',
        }
      : {
          tenant_id: tenant, intent_id: randomUUID(), idempotency_key: key,
          amount_minor: 1200, currency: 'USD',
          status: 'requires_payment_processor', created_at: '2026-10-24T00:00:00.000Z',
        };
    const invoke = (store, value) => kind === 'usage'
      ? store.recordUsage(principal, value)
      : store.createInvoiceIntent(principal, value);
    const table = kind === 'usage' ? 'usage_events' : 'invoice_intents';
    let pool = newPool();
    const control = newPool();
    let killed = 0;
    let discarded = 0;
    try {
      const faultPool = {
        async connect() {
          const client = await pool.connect();
          const pid = (await client.query('SELECT pg_backend_pid() AS pid')).rows[0].pid;
          return {
            async query(sql, params) {
              if (sql === 'COMMIT' && killed === 0) {
                // A separate least-privilege connection kills only this test session.
                const result = await control.query('SELECT pg_terminate_backend($1) AS terminated', [pid]);
                assert.equal(result.rows[0].terminated, true);
                killed += 1;
              }
              return client.query(sql, params);
            },
            release(error) {
              if (error) discarded += 1;
              client.release(error);
            },
          };
        },
      };
      await assert.rejects(invoke(storeFor(faultPool), payload));
      assert.equal(killed, 1, 'only the intended backend must be terminated');
      assert.equal(discarded, 1, 'uncertain connection must not re-enter pool');
      await pool.end();
      pool = newPool();
      const store = storeFor(pool);
      const counts = async () => store.withTenant(principal, tenant, async client => {
        const rows = await client.query(`SELECT count(*)::int AS n FROM zeaz_financial.${table}`);
        const audit = await client.query('SELECT count(*)::int AS n FROM zeaz_financial.audit_events');
        return { records: rows.rows[0].n, audit: audit.rows[0].n };
      });
      assert.deepEqual(await counts(), { records: 0, audit: 0 }, 'killed transaction must roll back');
      const result = await invoke(store, payload);
      if (kind === 'usage') assert.equal(result.duplicate, false);
      else assert.equal(result.intent_id, payload.intent_id);
      assert.deepEqual(await counts(), { records: 1, audit: 1 });
      const replay = kind === 'usage'
        ? { ...payload, recorded_at: '2026-10-25T00:00:00.000Z' }
        : { ...payload, intent_id: randomUUID(), created_at: '2026-10-25T00:00:00.000Z' };
      const duplicate = await invoke(store, replay);
      if (kind === 'usage') assert.equal(duplicate.duplicate, true);
      else assert.equal(duplicate.intent_id, payload.intent_id);
      assert.deepEqual(await counts(), { records: 1, audit: 1 }, 'replay must not double charge or audit');
    } finally {
      await Promise.allSettled([pool.end(), control.end()]);
    }
  });
}
