import test from 'node:test';
import assert from 'node:assert/strict';
import { createRateLimitStore } from '../server/storage/postgres/rate-limit-store.js';

function createFakePool() {
  const queries = [];
  let queryIndex = 0;
  const rows = [];

  const client = {
    async query(text, values) {
      queries.push({ text, values: Array.from(values || []) });
      const result = rows[queryIndex] || { rows: [] };
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
    setRows(items) {
      rows.push(...items);
    },
  };
}

test('createRateLimitStore requires a pool', () => {
  assert.throws(() => createRateLimitStore(null), /pg Pool is required/);
  assert.throws(() => createRateLimitStore({}), /pg Pool is required/);
});

test('check allows requests under the limit with correct remaining count', async () => {
  const fake = createFakePool();
  fake.setRows([
    { rows: [] },
    { rows: [{ count: '0' }] },
    { rows: [] },
  ]);

  const store = createRateLimitStore(fake.pool);
  const result = await store.check('ip:/api/test', 60_000, 5);

  assert.equal(result.allowed, true);
  assert.equal(result.remaining, 4);
  assert.equal(result.retryAfter, 0);
  assert.equal(fake.queries.length, 3);
  assert.ok(fake.queries[0].text.includes('DELETE FROM rate_limit_records'));
  assert.ok(fake.queries[1].text.includes('SELECT count(*)'));
  assert.ok(fake.queries[2].text.includes('INSERT INTO rate_limit_records'));
});

test('check denies requests over the limit and computes retryAfter', async () => {
  const fake = createFakePool();
  const oldest = new Date(Date.now() - 30_000).toISOString();
  fake.setRows([
    { rows: [] },
    { rows: [{ count: '5' }] },
    { rows: [{ requested_at: oldest }] },
  ]);

  const store = createRateLimitStore(fake.pool);
  const result = await store.check('ip:/api/test', 60_000, 5);

  assert.equal(result.allowed, false);
  assert.equal(result.remaining, 0);
  assert.ok(result.retryAfter > 0);
  assert.equal(fake.queries.length, 3);
  assert.ok(fake.queries[2].text.includes('SELECT requested_at'));
});

test('check cleans up expired records for the key before counting', async () => {
  const fake = createFakePool();
  fake.setRows([{ rows: [{ count: '0' }] }]);

  const store = createRateLimitStore(fake.pool);
  await store.check('ip:/api/test', 60_000, 5);

  assert.ok(fake.queries[0].text.includes('DELETE FROM rate_limit_records WHERE key = $1'));
  assert.deepEqual(fake.queries[0].values[0], 'ip:/api/test');
});

test('check uses parameterized queries to prevent injection', async () => {
  const fake = createFakePool();
  fake.setRows([{ rows: [{ count: '0' }] }]);

  const store = createRateLimitStore(fake.pool);
  await store.check("'; DROP TABLE rate_limit_records; --", 60_000, 5);

  assert.ok(fake.queries[0].values[0].includes("'; DROP TABLE"));
  assert.ok(fake.queries[1].values[0].includes("'; DROP TABLE"));
});

test('check validates input arguments', async () => {
  const fake = createFakePool();
  const store = createRateLimitStore(fake.pool);

  await assert.rejects(() => store.check('', 60_000, 5), /key must be a non-empty string/);
  await assert.rejects(() => store.check('key', 0, 5), /windowMs must be a positive integer/);
  await assert.rejects(() => store.check('key', 60_000, 0), /max must be a positive integer/);
  assert.equal(fake.queries.length, 0);
});

test('startCleanup and stopCleanup manage the periodic cleanup timer', async () => {
  const fake = createFakePool();
  const store = createRateLimitStore(fake.pool, { cleanupIntervalMs: 50, retentionMs: 1000 });

  store.startCleanup();
  assert.ok(store.startCleanup.toString().length > 0); // sanity

  await new Promise((resolve) => setTimeout(resolve, 120));
  store.stopCleanup();

  assert.ok(fake.queries.length >= 1);
  assert.ok(fake.queries.some((q) => q.text.includes('DELETE FROM rate_limit_records WHERE requested_at < $1')));
});

test('cleanup is non-blocking on database errors', async () => {
  const fake = createFakePool();
  let queryCount = 0;
  const client = {
    async query() {
      queryCount += 1;
      if (queryCount === 1) {
        throw new Error('database error');
      }
      return { rows: [] };
    },
    release() {},
  };
  fake.pool.connect = async () => {
    queryCount = 0;
    return client;
  };

  const store = createRateLimitStore(fake.pool, { cleanupIntervalMs: 50, retentionMs: 1000 });
  store.startCleanup();

  await new Promise((resolve) => setTimeout(resolve, 120));
  store.stopCleanup();

  assert.ok(queryCount >= 1);
});
