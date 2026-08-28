import assert from 'node:assert/strict';
import test from 'node:test';
import { createLocalHealthAdapter, validateHealthUrl } from '../local-health-adapter.mjs';

test('health URL accepts only exact literal-loopback HTTP health endpoints', () => {
  assert.equal(validateHealthUrl('http://127.0.0.1:8098/healthz'), 'http://127.0.0.1:8098/healthz');
  assert.equal(validateHealthUrl('http://[::1]:8098/healthz'), 'http://[::1]:8098/healthz');
  for (const value of [
    'http://localhost:8098/healthz',
    'https://127.0.0.1:8098/healthz',
    'http://10.0.0.5:8098/healthz',
    'http://example.com/healthz',
    'http://127.0.0.1:8098/admin',
    'http://user:pass@127.0.0.1:8098/healthz',
    'http://127.0.0.1:8098/healthz?next=http://example.com',
    'http://127.0.0.1:8098/healthz#fragment',
  ]) {
    assert.throws(() => validateHealthUrl(value));
  }
});

test('adapter uses GET, redirect error, timeout signal, and allowlisted target only', async () => {
  const calls = [];
  const adapter = createLocalHealthAdapter({
    targets: { local: 'http://127.0.0.1:8098/healthz' },
    timeoutMs: 500,
    fetchImpl: async (url, options) => {
      calls.push({ url, options });
      return new Response(JSON.stringify({ status: 'ok', local_only: true }), {
        status: 200,
        headers: { 'content-type': 'application/json' },
      });
    },
  });
  const signal = await adapter.evaluate({ target: 'local' }, '2026-08-06T03:00:00.000Z');
  assert.equal(signal.status, 'healthy');
  assert.equal(signal.proposed_action, null);
  assert.equal(calls.length, 1);
  assert.equal(calls[0].options.method, 'GET');
  assert.equal(calls[0].options.redirect, 'error');
  assert.ok(calls[0].options.signal instanceof AbortSignal);
  await assert.rejects(adapter.evaluate({ target: 'unknown' }, '2026-08-06T03:00:00.000Z'), /not allowlisted/);
});

test('network failure becomes a bounded unhealthy signal rather than leaking errors', async () => {
  const adapter = createLocalHealthAdapter({
    targets: { local: 'http://127.0.0.1:65534/healthz' },
    fetchImpl: async () => { throw new Error('secret internal network detail'); },
  });
  const signal = await adapter.evaluate({ target: 'local' }, '2026-08-06T03:00:00.000Z');
  assert.equal(signal.status, 'unhealthy');
  assert.equal(signal.evidence.reachable, false);
  assert.equal(JSON.stringify(signal).includes('secret internal network detail'), false);
  assert.equal(signal.proposed_action.capability, 'sandbox.preference.set');
});
