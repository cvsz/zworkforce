import assert from 'node:assert/strict';
import test from 'node:test';
import { PgFinancialStore } from '../pg-store.mjs';

const timestamp = '2026-10-23T00:00:00.000Z';
const principal = Object.freeze({ sub: 'synthetic-operator' });
const usage = Object.freeze({
  event_type: 'ai.usage.recorded.v1', event_version: 'v1', tenant_id: 'tenant-a',
  usage_id: 'usage-1', idempotency_key: 'request-1', subject_id: 'subject-1',
  model: 'test-model', input_tokens: 2, output_tokens: 3, recorded_at: timestamp,
});
const invoice = Object.freeze({
  tenant_id: 'tenant-a', intent_id: '00000000-0000-4000-8000-000000000001',
  idempotency_key: 'invoice-1', amount_minor: 1200, currency: 'USD',
  status: 'requires_payment_processor', created_at: timestamp,
});
function harness({ rows = [], role = 'zeaz_financial_runtime', login = 'zeaz_financial_app_test', privileged = false, resolver = async () => 'tenant-a', failInsert = false } = {}) {
  const log = [];
  let released = false;
  const client = {
    async query(sql, params) {
      log.push({ sql: sql.trim(), params });
      if (sql.includes('FROM pg_roles')) return { rows: [{ login_role: login, rolsuper: privileged, rolbypassrls: false, rolcreaterole: false, rolcreatedb: false, rolreplication: false }] };
      if (sql.includes('SELECT current_user AS')) return { rows: [{ current_role: role }] };
      if (sql.includes('INSERT INTO')) {
        if (failInsert) throw Object.assign(new Error('db insert failed'), { code: '23505' });
        return { rows: rows[0] || [] };
      }
      if (sql.includes('SELECT * FROM')) return { rows: rows[1] || [] };
      return { rows: [] };
    },
    release() { released = true; },
  };
  const store = new PgFinancialStore({ pool: { async connect() { return client; } }, resolveTenant: resolver, expectedLoginRole: 'zeaz_financial_app_test' });
  return { store, log, get released() { return released; } };
}
function rowUsage(patch = {}) { return { ...usage, ...patch }; }
function rowInvoice(patch = {}) { return { ...invoice, ...patch }; }

test('rejects untrusted tenant before acquiring a connection', async () => {
  const h = harness({ resolver: async () => 'tenant-b' });
  await assert.rejects(h.store.recordUsage(principal, usage), error => error.status === 403);
  assert.equal(h.log.length, 0);
});
test('rejects privileged database identity and rolls back', async () => {
  const h = harness({ role: 'postgres' });
  await assert.rejects(h.store.recordUsage(principal, usage), error => error.status === 503);
  assert.deepEqual(h.log.map(x => x.sql), ['BEGIN', 'SELECT session_user AS login_role, rolsuper, rolbypassrls,\n               rolcreaterole, rolcreatedb, rolreplication\n        FROM pg_roles WHERE rolname = session_user', 'SET LOCAL ROLE zeaz_financial_runtime', 'SELECT current_user AS current_role', 'ROLLBACK']);
  assert.equal(h.released, true);
});
test('rejects SET ROLE from a privileged login', async () => {
  const h = harness({ login: 'postgres' });
  await assert.rejects(h.store.recordUsage(principal, usage), error => error.status === 503);
  assert.equal(h.log.some(x => x.sql.includes('INSERT')), false);
});
test('uses transaction-local parameterized tenant context and commits', async () => {
  const h = harness({ rows: [[rowUsage()]] });
  const result = await h.store.recordUsage(principal, usage);
  assert.equal(result.duplicate, false);
  assert.deepEqual(h.log.map(x => x.sql.split(' ')[0]), ['BEGIN', 'SELECT', 'SET', 'SELECT', 'SELECT', 'INSERT', 'COMMIT']);
  assert.deepEqual(h.log[4].params, ['tenant-a']);
  assert.match(h.log[4].sql, /set_config\('zeaz.tenant_id', \$1, true\)/);
  assert.equal(h.released, true);
});
test('returns identical usage replay without a second insert', async () => {
  const h = harness({ rows: [[], [rowUsage()]] });
  const result = await h.store.recordUsage(principal, { ...usage, recorded_at: '2026-10-24T00:00:00.000Z' });
  assert.equal(result.duplicate, true);
  assert.equal(result.record.recorded_at, timestamp);
  assert.equal(h.log.at(-1).sql, 'COMMIT');
});
test('rejects conflicting same-key replay and rolls back', async () => {
  const h = harness({ rows: [[], [rowUsage()]] });
  await assert.rejects(h.store.recordUsage(principal, { ...usage, output_tokens: 9 }), error => error.status === 409);
  assert.equal(h.log.at(-1).sql, 'ROLLBACK');
  assert.equal(h.released, true);
});
test('rejects duplicate usage identity under another key', async () => {
  const h = harness({ rows: [[], []] });
  await assert.rejects(h.store.recordUsage(principal, usage), error => error.status === 409);
  assert.equal(h.log.at(-1).sql, 'ROLLBACK');
});
test('rejects unknown payload fields and unsafe token counts before SQL', async () => {
  const h = harness();
  await assert.rejects(h.store.recordUsage(principal, { ...usage, hidden_charge: 5 }), error => error.status === 400);
  await assert.rejects(h.store.recordUsage(principal, { ...usage, input_tokens: Number.MAX_SAFE_INTEGER + 1 }), error => error.status === 400);
  assert.equal(h.log.length, 0);
});
test('invoice duplicate returns original generated identifiers', async () => {
  const h = harness({ rows: [[], [rowInvoice()]] });
  const result = await h.store.createInvoiceIntent(principal, { ...invoice, intent_id: '00000000-0000-4000-8000-000000000002', created_at: '2026-10-24T00:00:00.000Z' });
  assert.equal(result.intent_id, invoice.intent_id);
  assert.equal(h.log.at(-1).sql, 'COMMIT');
});
test('rejects conflicting invoice replay and settlement status', async () => {
  const h = harness({ rows: [[], [rowInvoice()]] });
  await assert.rejects(h.store.createInvoiceIntent(principal, { ...invoice, amount_minor: 2000 }), error => error.status === 409);
  assert.equal(h.log.at(-1).sql, 'ROLLBACK');
  const empty = harness();
  await assert.rejects(empty.store.createInvoiceIntent(principal, { ...invoice, status: 'paid' }), error => error.status === 503);
  assert.equal(empty.log.length, 0);
});
test('maps unique violations to conflict and releases client', async () => {
  const h = harness({ failInsert: true });
  await assert.rejects(h.store.recordUsage(principal, usage), error => error.status === 409);
  assert.equal(h.log.at(-1).sql, 'ROLLBACK');
  assert.equal(h.released, true);
});
test('constructor refuses missing trusted tenant resolver', () => {
  assert.throws(() => new PgFinancialStore({ pool: { connect() {} } }), error => error.status === 503);
});
