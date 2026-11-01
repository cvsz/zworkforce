import assert from 'node:assert/strict';
import test from 'node:test';
import { generateKeyPairSync, sign } from 'node:crypto';
import { createPinnedJwksProvider } from '../pinned-jwks.mjs';
import { createFinancialTenantResolver } from '../tenant-identity.mjs';

const issuer = 'https://identity.example.test/realms/zeaz';
const jwksUrl = `${issuer}/protocol/openid-connect/certs`;
const jwk = { kid: 'key-1', kty: 'RSA', alg: 'RS256', use: 'sig', n: 'public-modulus', e: 'AQAB' };
const bytes = body => new TextEncoder().encode(body);
function response(value = { keys: [jwk] }, status = 200, type = 'application/json') {
  const body = bytes(JSON.stringify(value));
  return { status, headers: { get: name => name === 'content-type' ? type : null }, body: new ReadableStream({ start(c) { c.enqueue(body); c.close(); } }) };
}
function setup(overrides = {}) {
  let calls = 0;
  let clock = 100000;
  const options = {
    issuer, jwksUrl, now: () => clock,
    fetchFn: async (_url, _opts) => { calls++; return response(); },
    ...overrides,
  };
  const provider = createPinnedJwksProvider(options);
  return { provider, calls: () => calls, tick: ms => { clock += ms; } };
}

test('accepts only an operator-pinned HTTPS issuer and same-origin JWKS path', () => {
  for (const bad of [
    { jwksUrl: 'http://identity.example.test/realms/zeaz/certs' },
    { jwksUrl: 'https://attacker.example.test/certs' },
    { jwksUrl: `${issuer}/../other/certs` },
    { jwksUrl: `${jwksUrl}?token=secret` },
    { jwksUrl: `${jwksUrl}#fragment` },
    { issuer: 'http://identity.example.test/realms/zeaz' },
    { issuer: 'https://identity.example.test/realms/zeaz?bad=true' },
    { jwksUrl: 'https://user:pass@identity.example.test/realms/zeaz/certs' },
  ]) assert.throws(() => setup(bad), e => e.status === 503);
});

test('fetches with redirect denial, abort timeout and no credentials', async () => {
  let captured;
  const h = setup({ fetchFn: async (url, options) => { captured = { url, options }; return response(); } });
  assert.deepEqual(await h.provider(), { keys: [jwk] });
  assert.equal(captured.url, jwksUrl);
  assert.equal(captured.options.redirect, 'error');
  assert.equal(captured.options.credentials, 'omit');
  assert.equal(captured.options.method, 'GET');
  assert.ok(captured.options.signal instanceof AbortSignal);
});

test('uses bounded TTL and refreshes after expiration with new signing key', async () => {
  let key = 'old';
  let requests = 0;
  const h = setup({ ttlMs: 1000, fetchFn: async () => { requests++; return response({ keys: [{ ...jwk, kid: key }] }); } });
  assert.equal((await h.provider()).keys[0].kid, 'old');
  key = 'new';
  assert.equal((await h.provider()).keys[0].kid, 'old');
  assert.equal(requests, 1);
  h.tick(1000);
  assert.equal((await h.provider()).keys[0].kid, 'new');
  assert.equal(requests, 2);
});

test('never serves stale keys after network outage', async () => {
  let offline = false;
  const h = setup({ ttlMs: 1000, fetchFn: async () => { if (offline) throw new Error('offline'); return response(); } });
  await h.provider();
  h.tick(1001);
  offline = true;
  await assert.rejects(h.provider(), e => e.status === 503);
  await assert.rejects(h.provider(), e => e.status === 503);
});

test('coalesces simultaneous refresh requests', async () => {
  let calls = 0;
  const h = setup({ fetchFn: async () => { calls++; await new Promise(resolve => setTimeout(resolve, 5)); return response(); } });
  const all = await Promise.all(Array.from({ length: 12 }, () => h.provider()));
  assert.equal(calls, 1);
  assert.ok(all.every(v => v.keys[0].kid === 'key-1'));
});

test('does not let callers mutate cached key material', async () => {
  const h = setup();
  const first = await h.provider();
  first.keys[0].kid = 'attacker';
  first.keys.push({ kid: 'attacker' });
  assert.deepEqual(await h.provider(), { keys: [jwk] });
});

test('rejects oversized, malformed, duplicate, non-JSON and error responses', async () => {
  const badResponses = [
    response({ keys: [jwk] }, 302),
    response({ keys: [jwk] }, 200, 'text/html'),
    response({ keys: [jwk, jwk] }),
    response({ keys: [] }),
    response({ keys: [jwk], filler: 'a'.repeat(10000) }),
    { status: 200, headers: { get: () => 'application/json' }, body: new ReadableStream({ start(c) { c.enqueue(bytes('{invalid')); c.close(); } }) },
  ];
  for (const bad of badResponses) {
    const h = setup({ maxBytes: 4096, fetchFn: async () => bad });
    await assert.rejects(h.provider(), e => e.status === 503);
  }
});

test('cancels oversized response streams to bound resource consumption', async () => {
  let canceled = false;
  const oversized = {
    status: 200,
    headers: { get: () => 'application/json' },
    body: new ReadableStream({
      start(controller) { controller.enqueue(bytes('a'.repeat(5000))); },
      cancel() { canceled = true; },
    }),
  };
  const h = setup({ maxBytes: 4096, fetchFn: async () => oversized });
  await assert.rejects(h.provider(), e => e.status === 503);
  assert.equal(canceled, true);
});

test('fails closed on invalid clock, backwards clock and configuration bounds', async () => {
  let time = 100000;
  const h = setup({ now: () => time });
  await h.provider();
  time = 99999;
  await assert.rejects(h.provider(), e => e.status === 503);
  const invalid = setup({ now: () => Number.NaN });
  await assert.rejects(invalid.provider(), e => e.status === 503);
  for (const config of [{ ttlMs: 0 }, { ttlMs: 999999 }, { timeoutMs: 0 }, { maxBytes: 1 }]) {
    assert.throws(() => setup(config), e => e.status === 503);
  }
});

test('signed tenant resolution tracks pinned key rotation and authoritative membership revocation', async () => {
  const a = generateKeyPairSync('rsa', { modulusLength: 2048 });
  const b = generateKeyPairSync('rsa', { modulusLength: 2048 });
  const publicJwk = (pair, kid) => ({ ...pair.publicKey.export({ format: 'jwk' }), kid, alg: 'RS256', use: 'sig' });
  let current = 100000;
  let active = true;
  let currentKeys = [publicJwk(a, 'a')];
  const provider = createPinnedJwksProvider({
    issuer, jwksUrl, now: () => current, ttlMs: 1000,
    fetchFn: async () => response({ keys: currentKeys }),
  });
  const resolver = createFinancialTenantResolver({
    issuer, audience: 'zeaz-financial', getJwks: provider,
    now: () => current, lookupMembership: async ({ subject, tenantId }) => ({
      active: active && subject === 'subject-a' && tenantId === 'tenant-a', role: 'billing_writer',
    }),
  });
  function token(pair, kid, tenantId = 'tenant-a') {
    const encode = value => Buffer.from(JSON.stringify(value)).toString('base64url');
    const h = encode({ alg: 'RS256', typ: 'JWT', kid });
    const p = encode({ iss: issuer, aud: 'zeaz-financial', sub: 'subject-a', tenant_id: tenantId,
      iat: 90, nbf: 90, exp: 600, scope: 'billing:write' });
    const input = `${h}.${p}`;
    return `${input}.${sign('RSA-SHA256', Buffer.from(input), pair.privateKey).toString('base64url')}`;
  }
  assert.equal(await resolver({ token: token(a, 'a') }), 'tenant-a');
  await assert.rejects(resolver({ token: token(a, 'a', 'tenant-b') }), e => e.status === 403);
  active = false;
  await assert.rejects(resolver({ token: token(a, 'a') }), e => e.status === 403);
  active = true;
  currentKeys = [publicJwk(b, 'b')];
  current += 1000;
  await assert.rejects(resolver({ token: token(a, 'a') }), e => e.status === 403);
  assert.equal(await resolver({ token: token(b, 'b') }), 'tenant-a');
});
