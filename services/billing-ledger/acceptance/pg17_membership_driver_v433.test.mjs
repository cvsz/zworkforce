// Disposable PostgreSQL 17 membership acceptance; never use customer DSNs.
import assert from 'node:assert/strict';
import test from 'node:test';
import { generateKeyPairSync, sign } from 'node:crypto';
import pg from 'pg';
import { createPgMembershipLookup } from '../pg-membership.mjs';
import { createFinancialTenantResolver } from '../tenant-identity.mjs';

for (const [name, value] of Object.entries({
  Z_FINANCIAL_PG17_REAL_DRIVER: 'true',
  PGHOST: '127.0.0.1', PGDATABASE: 'zeaz_financial_acceptance',
  PG_MEMBERSHIP_USER: 'zeaz_financial_membership_app_test',
})) if (process.env[name] !== value) throw new Error(`Disposable membership admission refused: ${name}`);
if (!process.env.PG_MEMBERSHIP_TEST_PASSWORD) throw new Error('Disposable membership credential missing');

const pool = new pg.Pool({ host: '127.0.0.1', port: Number(process.env.PGPORT || 5432),
  database: 'zeaz_financial_acceptance', user: 'zeaz_financial_membership_app_test',
  password: process.env.PG_MEMBERSHIP_TEST_PASSWORD, max: 2,
  connectionTimeoutMillis: 5000, idleTimeoutMillis: 2000,
  statement_timeout: 5000, query_timeout: 7000,
  application_name: 'zeaz_financial_disposable_membership_v433' });
const lookupMembership = createPgMembershipLookup({ pool,
  expectedLoginRole: 'zeaz_financial_membership_app_test' });
const issuer = 'https://identity.example.test';
const audience = 'zeaz-financial';
const nowSeconds = 1792800000;
const keys = generateKeyPairSync('rsa', { modulusLength: 2048 });
const jwk = { ...keys.publicKey.export({ format: 'jwk' }), kid: 'test-only', alg: 'RS256', use: 'sig' };
const resolver = createFinancialTenantResolver({ issuer, audience,
  now: () => nowSeconds * 1000, getJwks: async () => ({ keys: [jwk] }), lookupMembership });
const encode = obj => Buffer.from(JSON.stringify(obj)).toString('base64url');
function jwt(subject, tenantId, overrides = {}) {
  const input = `${encode({ alg: 'RS256', typ: 'JWT', kid: 'test-only' })}.${encode({
    iss: issuer, aud: audience, sub: subject, tenant_id: tenantId,
    iat: nowSeconds - 60, nbf: nowSeconds - 60, exp: nowSeconds + 600,
    scope: 'billing:write', ...overrides,
  })}`;
  return `${input}.${sign('RSA-SHA256', Buffer.from(input), keys.privateKey).toString('base64url')}`;
}
try {
  await test('PG17: verified JWT + dedicated membership reader enforces current role and revocation', async () => {
    assert.equal(await resolver({ token: jwt('subject-c', 'tenant-c') }), 'tenant-c');
    await assert.rejects(resolver({ token: jwt('subject-c', 'tenant-d') }), e => e.status === 403);
    await assert.rejects(resolver({ token: jwt('subject-a', 'tenant-a') }), e => e.status === 403);
    await assert.rejects(resolver({ token: jwt('subject-c', 'tenant-z') }), e => e.status === 403);
    await assert.rejects(resolver({ token: jwt('subject-c', 'tenant-c', { scope: 'billing:read' }) }), e => e.status === 403);
    const privileges = await pool.query(`SELECT
      has_table_privilege(current_user, 'zeaz_financial.tenant_memberships', 'SELECT') AS can_read_membership_table,
      has_table_privilege(current_user, 'zeaz_financial.usage_events', 'SELECT') AS can_read_ledger`);
    assert.deepEqual(privileges.rows[0], { can_read_membership_table: false, can_read_ledger: false });
  });
} finally { await pool.end(); }
