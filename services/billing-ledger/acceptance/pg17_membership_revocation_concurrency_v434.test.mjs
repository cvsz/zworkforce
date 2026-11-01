// Disposable-only PostgreSQL 17 concurrency acceptance. No customer DSNs.
import assert from 'node:assert/strict';
import test from 'node:test';
import pg from 'pg';

for (const [name, expected] of Object.entries({
  Z_FINANCIAL_PG17_REAL_DRIVER: 'true',
  PGHOST: '127.0.0.1',
  PGDATABASE: 'zeaz_financial_acceptance',
  PG_REVOKER_USER: 'zeaz_financial_membership_revoker_app_test',
})) {
  if (process.env[name] !== expected) throw new Error(`Disposable revoker admission refused: ${name}`);
}
if (!process.env.PG_REVOKER_TEST_PASSWORD) throw new Error('Disposable revoker credential missing');

const pool = new pg.Pool({
  host: '127.0.0.1', port: Number(process.env.PGPORT || 5432),
  database: 'zeaz_financial_acceptance',
  user: 'zeaz_financial_membership_revoker_app_test',
  password: process.env.PG_REVOKER_TEST_PASSWORD,
  max: 4, connectionTimeoutMillis: 5000, idleTimeoutMillis: 2000,
  statement_timeout: 5000, query_timeout: 7000,
  application_name: 'zeaz_financial_disposable_revocation_v434',
});
const revoke = (requestId, subject, tenant, reason) =>
  pool.query(
    'SELECT zeaz_financial.revoke_billing_membership($1,$2,$3,$4) AS changed',
    [requestId, subject, tenant, reason],
  ).then(result => result.rows[0].changed);

try {
  await test('PG17: concurrent same-key revocation creates exactly one new mutation', async () => {
    const outcomes = await Promise.all([
      revoke('v434-concurrent-same-identity', 'subject-e', 'tenant-e', 'Concurrent same-key revocation'),
      revoke('v434-concurrent-same-identity', 'subject-e', 'tenant-e', 'Concurrent same-key revocation'),
    ]);
    assert.deepEqual(outcomes.sort(), [false, true]);
  });
  await test('PG17: distinct concurrent keys cannot double-revoke the same membership', async () => {
    const results = await Promise.allSettled([
      revoke('v434-concurrent-distinct-a', 'subject-f', 'tenant-f', 'Concurrent different-key revocation'),
      revoke('v434-concurrent-distinct-b', 'subject-f', 'tenant-f', 'Concurrent different-key revocation'),
    ]);
    assert.equal(results.filter(x => x.status === 'fulfilled' && x.value === true).length, 1);
    assert.equal(results.filter(x => x.status === 'rejected' && x.reason?.code === 'P0002').length, 1);
  });
} finally {
  await pool.end();
}
