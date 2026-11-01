// Disposable PostgreSQL 17 commit-acknowledgement fault injection only.
// This simulates loss of a client acknowledgement; it is NOT a real network partition.
import assert from 'node:assert/strict';
import { randomUUID } from 'node:crypto';
import test from 'node:test';
import pg from 'pg';
import { PgFinancialStore } from '../pg-store.mjs';

for (const [name, expected] of Object.entries({
  Z_FINANCIAL_PG17_REAL_DRIVER: 'true',
  PGHOST: '127.0.0.1',
  PGDATABASE: 'zeaz_financial_acceptance',
  PGUSER: 'zeaz_financial_app_test',
})) {
  if (process.env[name] !== expected) throw new Error(`Disposable-only admission refused: ${name}`);
}
if (!process.env.PG_TEST_PASSWORD || !/^\d+$/.test(String(process.env.PGPORT || '5432'))) {
  throw new Error('Disposable PostgreSQL test credentials/port required');
}

const newPool = () => new pg.Pool({
  host: '127.0.0.1', port: Number(process.env.PGPORT || 5432),
  database: 'zeaz_financial_acceptance', user: 'zeaz_financial_app_test',
  password: process.env.PG_TEST_PASSWORD, max: 2,
  connectionTimeoutMillis: 5000, idleTimeoutMillis: 2000,
  statement_timeout: 5000, query_timeout: 7000,
  application_name: 'zeaz_financial_disposable_commit_fault_v428',
});

for (const kind of ['usage', 'invoice']) {
  for (const timing of ['before-commit', 'after-commit']) {
    test(`PG17 ${kind}: ${timing} acknowledgement fault reconciles by idempotency key`, async () => {
      const principal = Object.freeze({ nonce: randomUUID() });
      const tenant = `ci-${randomUUID()}`;
      const resolveTenant = async candidate => {
        if (candidate !== principal) throw new Error('Unverified synthetic principal');
        return tenant;
      };
      const makeStore = db => new PgFinancialStore({
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
      let injected = 0;
      let discarded = 0;
      try {
        const faultPool = {
          async connect() {
            const client = await pool.connect();
            return {
              async query(sql, params) {
                if (sql === 'COMMIT' && injected === 0) {
                  injected += 1;
                  if (timing === 'after-commit') await client.query(sql, params);
                  throw new Error('synthetic COMMIT acknowledgement unavailable');
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
        await assert.rejects(
          invoke(makeStore(faultPool), payload),
          /synthetic COMMIT acknowledgement unavailable/,
        );
        assert.equal(injected, 1, 'exactly one acknowledgement fault must fire');
        assert.equal(discarded, 1, 'uncertain pooled session must be discarded');

        // Restart the entire driver pool before reconciling the uncertain outcome.
        await pool.end();
        pool = newPool();
        const store = makeStore(pool);
        const counts = async () => store.withTenant(principal, tenant, async client => {
          const row = await client.query(`SELECT count(*)::int AS n FROM zeaz_financial.${table}`);
          const audit = await client.query(
            'SELECT count(*)::int AS n FROM zeaz_financial.audit_events',
          );
          return { rows: row.rows[0].n, audit: audit.rows[0].n };
        });
        const committed = timing === 'after-commit';
        assert.deepEqual(await counts(), {
          rows: committed ? 1 : 0, audit: committed ? 1 : 0,
        });
        const result = await invoke(store, payload);
        if (kind === 'usage') assert.equal(result.duplicate, committed);
        else assert.equal(result.intent_id, payload.intent_id);
        assert.deepEqual(await counts(), { rows: 1, audit: 1 });
        await invoke(store, kind === 'usage'
          ? { ...payload, recorded_at: '2026-10-25T00:00:00.000Z' }
          : { ...payload, intent_id: randomUUID(), created_at: '2026-10-25T00:00:00.000Z' });
        assert.deepEqual(await counts(), { rows: 1, audit: 1 });
      } finally {
        await pool.end();
      }
    });
  }
}
