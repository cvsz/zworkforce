import assert from 'node:assert/strict';
import test from 'node:test';
import { generateKeyPairSync, sign } from 'node:crypto';
import { createFinancialTenantResolver } from '../tenant-identity.mjs';

const { privateKey, publicKey } = generateKeyPairSync('rsa', { modulusLength: 2048 });
const jwk = { ...publicKey.export({ format: 'jwk' }), kid: 'key-1', alg: 'RS256', use: 'sig' };
const nowSeconds = 1792800000;
const validClaims = Object.freeze({
  iss: 'https://identity.example.test', aud: 'zeaz-financial', sub: 'subject-a',
  tenant_id: 'tenant-a', iat: nowSeconds - 20, nbf: nowSeconds - 20,
  exp: nowSeconds + 600, scope: 'billing:write',
});
const header = { alg: 'RS256', typ: 'JWT', kid: 'key-1' };
const encode = value => Buffer.from(JSON.stringify(value)).toString('base64url');
function jwt(claims = validClaims, protectedHeader = header, signer = privateKey) {
  const signingInput = encode(protectedHeader) + '.' + encode(claims);
  return signingInput + '.' + sign('RSA-SHA256', Buffer.from(signingInput), signer).toString('base64url');
}
function harness({ membership = { active: true, role: 'billing_writer' }, keys = [jwk], keyFailure = false, membershipFailure = false } = {}) {
  const calls = [];
  const resolver = createFinancialTenantResolver({
    issuer: validClaims.iss, audience: validClaims.aud, now: () => nowSeconds * 1000,
    getJwks: async () => { if (keyFailure) throw new Error('offline'); return { keys }; },
    lookupMembership: async params => {
      calls.push(params);
      if (membershipFailure) throw new Error('offline');
      return membership;
    },
  });
  return { resolver, calls };
}
async function rejects(token, options, expected = 403) {
  const h = harness(options);
  await assert.rejects(h.resolver({ token }), e => e.status === expected);
  return h;
}

test('valid signed identity and authoritative active membership resolves tenant', async () => {
  const h = harness();
  assert.equal(await h.resolver({ token: jwt() }), 'tenant-a');
  assert.deepEqual(h.calls, [{ subject: 'subject-a', tenantId: 'tenant-a' }]);
});
test('rejects missing token and unverified decoded principal', async () => {
  const h = harness();
  await assert.rejects(h.resolver({ sub: 'subject-a', tenant_id: 'tenant-a' }), e => e.status === 403);
  assert.equal(h.calls.length, 0);
});
test('rejects altered payload and unknown signing key before membership', async () => {
  const good = jwt();
  const parts = good.split('.');
  parts[1] = encode({ ...validClaims, tenant_id: 'tenant-b' });
  const h = await rejects(parts.join('.'));
  assert.equal(h.calls.length, 0);
  await rejects(jwt(validClaims, { ...header, kid: 'unknown' }));
});
test('rejects alg none and embedded untrusted key', async () => {
  await rejects(jwt(validClaims, { ...header, alg: 'none' }));
  await rejects(jwt(validClaims, { ...header, jwk }));
});
test('rejects expired, future, and overlong JWT lifetimes', async () => {
  await rejects(jwt({ ...validClaims, exp: nowSeconds - 40 }));
  await rejects(jwt({ ...validClaims, nbf: nowSeconds + 120 }));
  await rejects(jwt({ ...validClaims, iat: nowSeconds + 120 }));
  await rejects(jwt({ ...validClaims, exp: nowSeconds + 4000 }));
});
test('rejects issuer, audience, and scope mismatches', async () => {
  await rejects(jwt({ ...validClaims, iss: 'https://attacker.example.test' }));
  await rejects(jwt({ ...validClaims, aud: 'different' }));
  await rejects(jwt({ ...validClaims, scope: 'billing:read' }));
});
test('rejects tenant and subject without stable identifiers', async () => {
  await rejects(jwt({ ...validClaims, tenant_id: '' }));
  await rejects(jwt({ ...validClaims, sub: ' subject-a ' }));
});
test('rejects inactive or wrong-role memberships', async () => {
  await rejects(jwt(), { membership: { active: false, role: 'billing_writer' } });
  await rejects(jwt(), { membership: { active: true, role: 'viewer' } });
});
test('ignores signed but untrusted role claim and requires server-side role', async () => {
  await rejects(jwt({ ...validClaims, role: 'admin' }), { membership: { active: true, role: 'viewer' } });
});
test('fails closed when trusted JWKS or membership service is unavailable', async () => {
  await rejects(jwt(), { keyFailure: true }, 503);
  await rejects(jwt(), { membershipFailure: true }, 503);
});
test('rejects duplicate kid and weak RSA key', async () => {
  await rejects(jwt(), { keys: [jwk, jwk] });
  const weak = generateKeyPairSync('rsa', { modulusLength: 1024 }).publicKey.export({ format: 'jwk' });
  await rejects(jwt(), { keys: [{ ...weak, kid: 'key-1', alg: 'RS256', use: 'sig' }] });
});
test('rejects wrong signing key and malformed compact tokens', async () => {
  const attacker = generateKeyPairSync('rsa', { modulusLength: 2048 });
  await rejects(jwt(validClaims, header, attacker.privateKey));
  await rejects('abc.def.ghi');
  await rejects(jwt() + '.extra');
});
test('configuration requires HTTPS issuer, membership and key providers', () => {
  assert.throws(() => createFinancialTenantResolver({ issuer: 'http://identity.test', audience: 'a', getJwks: async () => ({ keys: [jwk] }), lookupMembership: async () => true }), e => e.status === 503);
  assert.throws(() => createFinancialTenantResolver({ issuer: validClaims.iss, audience: validClaims.aud, getJwks: async () => ({ keys: [jwk] }) }), e => e.status === 503);
});
test('accepts audience arrays only when expected audience is present', async () => {
  const h = harness();
  assert.equal(await h.resolver({ token: jwt({ ...validClaims, aud: ['other-service', validClaims.aud] }) }), 'tenant-a');
  await rejects(jwt({ ...validClaims, aud: ['other-service'] }));
});
test('rejects expired tokens even within a former clock-skew grace window', async () => {
  await rejects(jwt({ ...validClaims, exp: nowSeconds - 1 }));
});
test('rejects not-before timestamps beyond expiration', async () => {
  await rejects(jwt({ ...validClaims, nbf: nowSeconds + 700 }));
});
test('PgFinancialStore refuses unauthorized token before database connection', async () => {
  const { PgFinancialStore } = await import('../pg-store.mjs');
  let connections = 0;
  const h = harness({ membership: { active: true, role: 'viewer' } });
  const store = new PgFinancialStore({
    pool: { connect: async () => { connections++; throw new Error('must not connect'); } },
    resolveTenant: h.resolver,
    expectedLoginRole: 'zeaz_financial_app_test',
  });
  const usage = {
    event_type: 'ai.usage.recorded.v1', event_version: 'v1', tenant_id: 'tenant-a',
    usage_id: 'usage-1', idempotency_key: 'key-1', subject_id: 'subject-a',
    model: 'test-model', input_tokens: 1, output_tokens: 2,
    recorded_at: '2026-10-24T00:00:00.000Z',
  };
  await assert.rejects(store.recordUsage({ token: jwt() }, usage), e => e.status === 403);
  assert.equal(connections, 0);
});
test('verified tenant is bound to PgFinancialStore transaction-local RLS context', async () => {
  const { PgFinancialStore } = await import('../pg-store.mjs');
  const queries = [];
  const usage = {
    event_type: 'ai.usage.recorded.v1', event_version: 'v1', tenant_id: 'tenant-a',
    usage_id: 'usage-1', idempotency_key: 'key-1', subject_id: 'subject-a',
    model: 'test-model', input_tokens: 1, output_tokens: 2,
    recorded_at: '2026-10-24T00:00:00.000Z',
  };
  const client = {
    async query(sql, params) {
      queries.push({ sql, params });
      if (sql.includes('FROM pg_roles')) return { rows: [{ login_role: 'zeaz_financial_app_test', rolsuper: false, rolbypassrls: false, rolcreaterole: false, rolcreatedb: false, rolreplication: false }] };
      if (sql.includes('SELECT current_user AS')) return { rows: [{ current_role: 'zeaz_financial_runtime' }] };
      if (sql.includes('INSERT INTO')) return { rows: [{ ...usage }] };
      return { rows: [] };
    },
    release() {},
  };
  const h = harness();
  const store = new PgFinancialStore({ pool: { connect: async () => client }, resolveTenant: h.resolver, expectedLoginRole: 'zeaz_financial_app_test' });
  const result = await store.recordUsage({ token: jwt() }, usage);
  assert.equal(result.duplicate, false);
  assert.deepEqual(queries.find(x => x.sql.includes("set_config('zeaz.tenant_id'"))?.params, ['tenant-a']);
  assert.equal(queries.at(-1).sql, 'COMMIT');
  assert.deepEqual(h.calls, [{ subject: 'subject-a', tenantId: 'tenant-a' }]);
});
