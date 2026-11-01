import assert from 'node:assert/strict';
import test from 'node:test';
import { createFinancialTenantResolver } from '../tenant-identity.mjs';

test('invalid clock fails closed before any key or membership lookup', async () => {
  let keyCalls = 0;
  let membershipCalls = 0;
  const resolver = createFinancialTenantResolver({
    issuer: 'https://identity.example.test',
    audience: 'zeaz-financial',
    now: () => Number.NaN,
    getJwks: async () => { keyCalls++; return { keys: [] }; },
    lookupMembership: async () => { membershipCalls++; return { active: true, role: 'billing_writer' }; },
  });
  const token = ['eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCIsImtpZCI6ImtleS0xIn0', 'eyJpc3MiOiJodHRwczovL2lkZW50aXR5LmV4YW1wbGUudGVzdCJ9', 'ZmFrZXNpZ25hdHVyZQ'].join('.');
  await assert.rejects(resolver({ token }), error => error.status === 503);
  assert.equal(keyCalls, 0);
  assert.equal(membershipCalls, 0);
});
