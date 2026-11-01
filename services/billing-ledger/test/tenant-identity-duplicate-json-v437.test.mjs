import assert from 'node:assert/strict';
import test from 'node:test';
import { generateKeyPairSync, sign } from 'node:crypto';
import { createFinancialTenantResolver } from '../tenant-identity.mjs';

const { privateKey, publicKey } = generateKeyPairSync('rsa', { modulusLength: 2048 });
const jwk = { ...publicKey.export({ format: 'jwk' }), kid: 'key-1', alg: 'RS256', use: 'sig' };
const header = '{"alg":"RS256","typ":"JWT","kid":"key-1"}';
const claims = '{"iss":"https://identity.example.test","aud":"zeaz-financial","sub":"subject-a","tenant_id":"tenant-a","iat":1792799980,"nbf":1792799980,"exp":1792800600,"scope":"billing:write"}';
const signed = (rawHeader, rawClaims) => {
  const input = Buffer.from(rawHeader).toString('base64url') + '.' + Buffer.from(rawClaims).toString('base64url');
  return input + '.' + sign('RSA-SHA256', Buffer.from(input), privateKey).toString('base64url');
};

test('rejects signed duplicate header and claim names before JWKS and membership lookup', async () => {
  let keyCalls = 0;
  let membershipCalls = 0;
  const resolveTenant = createFinancialTenantResolver({
    issuer: 'https://identity.example.test', audience: 'zeaz-financial', now: () => 1792800000000,
    getJwks: async () => { keyCalls++; return { keys: [jwk] }; },
    lookupMembership: async () => { membershipCalls++; return { active: true, role: 'billing_writer' }; },
  });
  for (const [rawHeader, rawClaims] of [
    [header.replace('"kid":"key-1"', '"kid":"old","kid":"key-1"'), claims],
    [header, claims.replace('"tenant_id":"tenant-a"', '"tenant_id":"tenant-b","tenant_id":"tenant-a"')],
    [header, claims.replace('"aud":"zeaz-financial"', '"aud":"other-service","aud":"zeaz-financial"')],
    [header, claims.replace('"sub":"subject-a"', '"sub":"subject-b","sub":"subject-a"')],
    [header, claims.replace('"scope":"billing:write"', '"scope":"billing:read","scope":"billing:write"')],
    [header, claims.replace('"tenant_id":"tenant-a"', '"tenant\\u005fid":"tenant-b","tenant_id":"tenant-a"')],
  ]) {
    await assert.rejects(resolveTenant({ token: signed(rawHeader, rawClaims) }), error => error.status === 403);
  }
  assert.equal(keyCalls, 0);
  assert.equal(membershipCalls, 0);
});

test('still accepts a unique, correctly signed billing token with server-side membership', async () => {
  const calls = [];
  const resolveTenant = createFinancialTenantResolver({
    issuer: 'https://identity.example.test', audience: 'zeaz-financial', now: () => 1792800000000,
    getJwks: async () => ({ keys: [jwk] }),
    lookupMembership: async args => { calls.push(args); return { active: true, role: 'billing_writer' }; },
  });
  assert.equal(await resolveTenant({ token: signed(header, claims) }), 'tenant-a');
  assert.deepEqual(calls, [{ subject: 'subject-a', tenantId: 'tenant-a' }]);
});
