import assert from 'node:assert/strict';
import test from 'node:test';
import { BillingLedger, BillingLedgerError, MemoryLedgerStore } from '../server.mjs';

const record = (overrides = {}) => ({
  tenant_id: 'tenant-a', usage_id: 'usage-a', idempotency_key: 'request-a',
  model: 'test:model', input_tokens: 1, output_tokens: 2, ...overrides,
});
const invalid = [undefined, null, NaN, Infinity, -Infinity, -1, 1.5,
  Number.MAX_SAFE_INTEGER + 1, '1', 'NaN', 'Infinity'];
const badRequest = (error) => error instanceof BillingLedgerError && error.status === 400;

test('direct-store invalid token counts fail before any identity index mutation', async () => {
  for (const field of ['input_tokens', 'output_tokens']) {
    for (const value of invalid) {
      const store = new MemoryLedgerStore();
      await assert.rejects(store.recordUsage(record({ [field]: value })), badRequest,
        `${field}=${String(value)}`);
      assert.equal(store.records.size, 0);
      assert.equal(store.usageIdentity.size, 0);
    }
  }
});

test('invalid same-key direct-store replay fails instead of returning duplicate', async () => {
  const store = new MemoryLedgerStore();
  await store.recordUsage(record());
  await assert.rejects(store.recordUsage(record({ input_tokens: NaN })), badRequest);
  assert.equal(store.records.size, 1);
  assert.equal(store.usageIdentity.size, 1);
  assert.equal(store.records.values().next().value.input_tokens, 1);
});

test('valid direct-store zero and maximum-safe-integer counts preserve tenant-scoped replay', async () => {
  const store = new MemoryLedgerStore();
  const first = await store.recordUsage(record({ input_tokens: 0, output_tokens: Number.MAX_SAFE_INTEGER }));
  assert.equal(first.duplicate, false);
  const replay = await store.recordUsage(record({ input_tokens: 0, output_tokens: Number.MAX_SAFE_INTEGER }));
  assert.equal(replay.duplicate, true);
  assert.equal(store.records.size, 1);
  assert.equal(store.usageIdentity.size, 1);
});

test('ledger normalization still accepts safe numeric-string counts', async () => {
  const ledger = new BillingLedger();
  const result = await ledger.recordUsage(record({ input_tokens: '0', output_tokens: '12' }));
  assert.equal(result.record.input_tokens, 0);
  assert.equal(result.record.output_tokens, 12);
});
