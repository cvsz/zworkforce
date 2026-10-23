import assert from 'node:assert/strict';
import test from 'node:test';
import { BillingLedger, BillingLedgerError } from '../server.mjs';

const usage = (overrides = {}) => ({
  tenant_id: 'tenant-a', idempotency_key: 'request-a', usage_id: 'usage-a',
  model: 'test:model', input_tokens: 2, output_tokens: 3, ...overrides,
});
const badRequest = (error) => error instanceof BillingLedgerError && error.status === 400;

test('ledger rejects ambiguous token coercions before recording usage', async () => {
  const invalid = [true, false, [], [2], {}, '0x10', '1e2', ' 2 ', '+2', '02', '2.0', '', 'Infinity'];
  for (const field of ['input_tokens', 'output_tokens']) {
    for (const value of invalid) {
      const ledger = new BillingLedger();
      await assert.rejects(ledger.recordUsage(usage({ [field]: value })), badRequest, `${field}=${String(value)}`);
      assert.equal(ledger.store.records.size, 0);
      assert.equal(ledger.store.usageIdentity.size, 0);
    }
  }
});

test('ledger retains safe integer and canonical decimal string token compatibility', async () => {
  const ledger = new BillingLedger();
  const result = await ledger.recordUsage(usage({ input_tokens: '0', output_tokens: '42' }));
  assert.equal(result.record.input_tokens, 0);
  assert.equal(result.record.output_tokens, 42);
  const replay = await ledger.recordUsage(usage({ input_tokens: 0, output_tokens: 42 }));
  assert.equal(replay.duplicate, true);
  assert.equal(ledger.store.records.size, 1);
});

test('invalid token replay fails before idempotency lookup and preserves original record', async () => {
  const ledger = new BillingLedger();
  await ledger.recordUsage(usage());
  await assert.rejects(ledger.recordUsage(usage({ input_tokens: true })), badRequest);
  await assert.rejects(ledger.recordUsage(usage({ output_tokens: '3e0' })), badRequest);
  assert.equal(ledger.store.records.size, 1);
  assert.equal(ledger.store.usageIdentity.size, 1);
  assert.equal((await ledger.recordUsage(usage())).duplicate, true);
});

test('omitted and null token counts preserve legacy zero defaults', async () => {
  const ledger = new BillingLedger();
  const record = (await ledger.recordUsage(usage({ input_tokens: undefined, output_tokens: null }))).record;
  assert.equal(record.input_tokens, 0);
  assert.equal(record.output_tokens, 0);
});
