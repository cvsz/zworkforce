import test from 'node:test';
import assert from 'node:assert/strict';
import { PgFinancialStore } from '../pg-store.mjs';

function harness({ failBegin = false, failRollback = false, failCommit = false } = {}) {
  const log = [];
  const releases = [];
  const client = {
    async query(sql) {
      const statement = sql.trim();
      log.push(statement);
      if (statement === 'BEGIN' && failBegin) throw new Error('synthetic begin failure');
      if (statement === 'COMMIT' && failCommit) throw new Error('synthetic commit failure');
      if (statement === 'ROLLBACK' && failRollback) throw new Error('synthetic rollback failure');
      if (statement.includes('FROM pg_roles')) return { rows: [{
        login_role: 'zeaz_financial_app_test', rolsuper: false, rolbypassrls: false,
        rolcreaterole: false, rolcreatedb: false, rolreplication: false,
      }] };
      if (statement === 'SELECT current_user AS current_role') {
        return { rows: [{ current_role: 'zeaz_financial_runtime' }] };
      }
      return { rows: [] };
    },
    release(error) { releases.push(error); },
  };
  const store = new PgFinancialStore({
    pool: { async connect() { return client; } },
    resolveTenant: async () => 'tenant-a',
    expectedLoginRole: 'zeaz_financial_app_test',
  });
  return { store, log, releases };
}
const execute = (h, action = async () => { throw new Error('synthetic action failure'); }) =>
  h.store.withTenant({ sub: 'synthetic' }, 'tenant-a', action);

test('successful transaction returns connection to pool', async () => {
  const h = harness();
  assert.equal(await execute(h, async () => 42), 42);
  assert.equal(h.releases.length, 1);
  assert.equal(h.releases[0], undefined);
});
test('successful rollback returns connection to pool', async () => {
  const h = harness();
  await assert.rejects(execute(h), /synthetic action failure/);
  assert.equal(h.releases.length, 1);
  assert.equal(h.releases[0], undefined);
  assert.equal(h.log.at(-1), 'ROLLBACK');
});
test('failed rollback discards connection and preserves original failure', async () => {
  const h = harness({ failRollback: true });
  await assert.rejects(execute(h), /synthetic action failure/);
  assert.equal(h.releases.length, 1);
  assert.ok(h.releases[0] instanceof Error);
});
test('failed BEGIN discards uncertain connection', async () => {
  const h = harness({ failBegin: true });
  await assert.rejects(execute(h), /synthetic begin failure/);
  assert.equal(h.releases.length, 1);
  assert.ok(h.releases[0] instanceof Error);
  assert.equal(h.log.includes('ROLLBACK'), false);
});
test('failed COMMIT discards uncertain connection even if rollback succeeds', async () => {
  const h = harness({ failCommit: true });
  await assert.rejects(execute(h, async () => 42), /synthetic commit failure/);
  assert.equal(h.releases.length, 1);
  assert.ok(h.releases[0] instanceof Error);
  assert.equal(h.log.at(-1), 'ROLLBACK');
});
