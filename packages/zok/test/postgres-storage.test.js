import test from 'node:test';
import assert from 'node:assert/strict';
import { createPostgresStorage } from '../server/storage/postgres-storage.js';

function createFakePool({ failOperation = false } = {}) {
  const calls = [];
  let released = 0;
  let ended = 0;
  const client = {
    async query(text, values) {
      calls.push({ text, values });
      if (failOperation && text === 'SELECT application_work') throw new Error('force rollback');
      return { rows: [{ ok: true }] };
    },
    release() {
      released += 1;
    },
  };
  return {
    pool: {
      async connect() { return client; },
      async end() { ended += 1; },
    },
    calls,
    released: () => released,
    ended: () => ended,
  };
}

test('PostgreSQL storage binds tenant context transaction-locally and releases pooled clients', async () => {
  const tenantId = '66666666-6666-4666-8666-666666666666';
  const fake = createFakePool();
  const storage = createPostgresStorage({ pool: fake.pool });

  const result = await storage.withTenantTransaction(tenantId, tx => tx.query('SELECT application_work'));
  assert.equal(result.rows[0].ok, true);
  assert.deepEqual(fake.calls, [
    { text: 'BEGIN', values: undefined },
    { text: "SELECT set_config('app.tenant_id', $1, true)", values: [tenantId] },
    { text: 'SELECT application_work', values: undefined },
    { text: 'COMMIT', values: undefined },
  ]);
  assert.equal(fake.released(), 1);

  await storage.close();
  assert.equal(fake.ended(), 1);
});

test('PostgreSQL storage binds an authenticated identity to its tenant transaction', async () => {
  const tenantId = '77777777-7777-4777-8777-777777777777';
  const fake = createFakePool();
  const storage = createPostgresStorage({ pool: fake.pool });
  const identity = Object.freeze({ userId: 'user-1', role: 'owner', tenantId });

  const result = await storage.withIdentityTransaction(identity, tx => tx.query('SELECT application_work'));
  assert.equal(result.rows[0].ok, true);
  assert.deepEqual(fake.calls[1], {
    text: "SELECT set_config('app.tenant_id', $1, true)",
    values: [tenantId],
  });

  await storage.close();
});

test('PostgreSQL storage rejects missing tenant context before acquiring a pooled client', async () => {
  const fake = createFakePool();
  let connects = 0;
  fake.pool.connect = async () => {
    connects += 1;
    throw new Error('must not connect');
  };
  const storage = createPostgresStorage({ pool: fake.pool });

  await assert.rejects(
    () => storage.withTenantTransaction('', async () => undefined),
    /tenantId is required/i,
  );
  await assert.rejects(
    () => storage.withIdentityTransaction({ userId: 'user-1', role: 'owner' }, async () => undefined),
    /identity tenantId is required/i,
  );
  assert.equal(connects, 0);
  await storage.close();
});

test('PostgreSQL storage rolls back failed tenant transactions and releases the client', async () => {
  const tenantId = '88888888-8888-4888-8888-888888888888';
  const fake = createFakePool({ failOperation: true });
  const storage = createPostgresStorage({ pool: fake.pool });

  await assert.rejects(
    () => storage.withTenantTransaction(tenantId, tx => tx.query('SELECT application_work')),
    /force rollback/,
  );
  assert.equal(fake.calls.at(-1).text, 'ROLLBACK');
  assert.equal(fake.released(), 1);
  await storage.close();
});
