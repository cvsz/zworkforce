import test from 'node:test';
import assert from 'node:assert/strict';
import { createSessionStore } from '../server/storage/postgres/session-store.js';

function createFakePool({ queryError = false } = {}) {
  const queries = [];
  let queryIndex = 0;
  const results = [];

  const client = {
    async query(text, values) {
      queries.push({ text, values: Array.from(values || []) });
      if (queryError) {
        const error = new Error('database error');
        error.code = 'ECONNREFUSED';
        throw error;
      }
      const result = results[queryIndex] || { rows: [] };
      queryIndex += 1;
      return result;
    },
    release() {},
  };

  return {
    pool: {
      async connect() {
        queryIndex = 0;
        return client;
      },
    },
    queries,
    setResults(items) {
      results.push(...items);
    },
  };
}

test('createSessionStore requires a pool', () => {
  assert.throws(() => createSessionStore(null), /pg Pool is required/);
  assert.throws(() => createSessionStore({}), /pg Pool is required/);
});

test('create inserts session with hashed tokens and parameterized queries', async () => {
  const fake = createFakePool();
  fake.setResults([{ rows: [{ id: 'user-1' }] }, { rows: [] }]);

  const store = createSessionStore(fake.pool);
  const session = {
    token: 'test-token',
    csrfToken: 'test-csrf',
    expiresAt: Date.now() + 3600000,
    user: {
      email: 'admin@example.test',
      role: 'owner',
      tenantId: 'bbbbbbbb-2222-4222-8222-bbbbbbbbbbbb',
    },
  };

  await store.create(session);

  assert.equal(fake.queries.length, 2);
  assert.ok(fake.queries[0].text.includes('SELECT id FROM users'));
  assert.deepEqual(fake.queries[0].values, [session.user.tenantId, session.user.email]);

  assert.ok(fake.queries[1].text.includes('INSERT INTO sessions'));
  assert.equal(fake.queries[1].values[0], session.user.tenantId);
  assert.equal(fake.queries[1].values[1], 'user-1');
  assert.ok(fake.queries[1].values[2].length === 64);
  assert.ok(fake.queries[1].values[3].length === 64);
  assert.ok(fake.queries[1].values[4].endsWith('Z'));
});

test('create throws when user is not found', async () => {
  const fake = createFakePool({ userRows: [] });
  fake.setResults([{ rows: [] }]);

  const store = createSessionStore(fake.pool);
  const session = {
    token: 'test-token',
    csrfToken: 'test-csrf',
    expiresAt: Date.now() + 3600000,
    user: {
      email: 'missing@example.test',
      role: 'owner',
      tenantId: 'bbbbbbbb-2222-4222-8222-bbbbbbbbbbbb',
    },
  };

  await assert.rejects(store.create(session), /User not found/);
});

test('create handles upsert on conflict', async () => {
  const fake = createFakePool();
  fake.setResults([{ rows: [{ id: 'user-1' }] }, { rows: [] }]);

  const store = createSessionStore(fake.pool);
  const session = {
    token: 'test-token',
    csrfToken: 'test-csrf',
    expiresAt: Date.now() + 3600000,
    user: {
      email: 'admin@example.test',
      role: 'owner',
      tenantId: 'bbbbbbbb-2222-4222-8222-bbbbbbbbbbbb',
    },
  };

  await store.create(session);
  await store.create(session);

  assert.equal(fake.queries.length, 4);
  assert.ok(fake.queries[3].text.includes('ON CONFLICT'));
});

test('get returns null for missing token', async () => {
  const fake = createFakePool();
  const store = createSessionStore(fake.pool);

  assert.equal(await store.get('missing'), null);
  assert.equal(await store.get(''), null);
});

test('get returns null when no rows match', async () => {
  const fake = createFakePool();
  fake.setResults([{ rows: [] }]);

  const store = createSessionStore(fake.pool);
  assert.equal(await store.get('test-token'), null);
});

test('get returns null for expired sessions', async () => {
  const fake = createFakePool();
  fake.setResults([
    { rows: [{ tenant_id: 't1', user_id: 'u1', expires_at: new Date(Date.now() - 1000).toISOString(), revoked_at: null, csrf_token_hash: 'hash' }] },
    { rows: [] },
  ]);

  const store = createSessionStore(fake.pool);
  assert.equal(await store.get('test-token'), null);
});

test('get returns null for revoked sessions', async () => {
  const fake = createFakePool();
  fake.setResults([
    { rows: [{ tenant_id: 't1', user_id: 'u1', expires_at: new Date(Date.now() + 3600000).toISOString(), revoked_at: new Date().toISOString(), csrf_token_hash: 'hash' }] },
  ]);

  const store = createSessionStore(fake.pool);
  assert.equal(await store.get('test-token'), null);
});

test('get returns session with user info and role lookup', async () => {
  const fake = createFakePool();
  fake.setResults([
    {
      rows: [{
        tenant_id: 'bbbbbbbb-2222-4222-8222-bbbbbbbbbbbb',
        user_id: 'user-1',
        expires_at: new Date(Date.now() + 3600000).toISOString(),
        revoked_at: null,
        csrf_token_hash: 'csrf-hash-value',
        email: 'admin@example.test',
      }],
    },
    { rows: [{ name: 'admin' }] },
  ]);

  const store = createSessionStore(fake.pool);
  const result = await store.get('test-token');

  assert.ok(result);
  assert.equal(result.token, 'test-token');
  assert.equal(result.csrfTokenHash, 'csrf-hash-value');
  assert.ok(result.expiresAt > Date.now());
  assert.deepEqual(result.user, {
    email: 'admin@example.test',
    role: 'admin',
    tenantId: 'bbbbbbbb-2222-4222-8222-bbbbbbbbbbbb',
  });
});

test('get defaults role to owner when no role is assigned', async () => {
  const fake = createFakePool();
  fake.setResults([
    {
      rows: [{
        tenant_id: 'bbbbbbbb-2222-4222-8222-bbbbbbbbbbbb',
        user_id: 'user-1',
        expires_at: new Date(Date.now() + 3600000).toISOString(),
        revoked_at: null,
        csrf_token_hash: 'csrf-hash-value',
        email: 'admin@example.test',
      }],
    },
    { rows: [] },
  ]);

  const store = createSessionStore(fake.pool);
  const result = await store.get('test-token');

  assert.ok(result);
  assert.equal(result.user.role, 'owner');
});

test('delete removes session by token hash', async () => {
  const fake = createFakePool();
  fake.setResults([{ rows: [] }]);

  const store = createSessionStore(fake.pool);
  await store.delete('test-token');

  assert.equal(fake.queries.length, 1);
  assert.ok(fake.queries[0].text.includes('DELETE FROM sessions'));
  assert.equal(fake.queries[0].values.length, 1);
  assert.ok(fake.queries[0].values[0].length === 64);
});

test('delete ignores empty token', async () => {
  const fake = createFakePool();
  const store = createSessionStore(fake.pool);

  await store.delete('');
  await store.delete(null);
  assert.equal(fake.queries.length, 0);
});

test('pruneExpired deletes expired sessions', async () => {
  const fake = createFakePool();
  fake.setResults([{ rows: [] }]);

  const store = createSessionStore(fake.pool);
  await store.pruneExpired();

  assert.equal(fake.queries.length, 1);
  assert.ok(fake.queries[0].text.includes('DELETE FROM sessions WHERE expires_at < now()'));
});

test('get handles connection errors gracefully', async () => {
  const fake = createFakePool({ queryError: true });
  const store = createSessionStore(fake.pool);

  assert.equal(await store.get('test-token'), null);
});

test('create handles connection errors gracefully', async () => {
  const fake = createFakePool({ queryError: true });
  const store = createSessionStore(fake.pool);

  const session = {
    token: 'test-token',
    csrfToken: 'test-csrf',
    expiresAt: Date.now() + 3600000,
    user: {
      email: 'admin@example.test',
      role: 'owner',
      tenantId: 'bbbbbbbb-2222-4222-8222-bbbbbbbbbbbb',
    },
  };

  await assert.rejects(store.create(session), /database error/);
});
