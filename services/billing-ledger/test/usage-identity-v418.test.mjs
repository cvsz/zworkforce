import assert from 'node:assert/strict';
import test from 'node:test';
import { BillingLedger, BillingLedgerError, MemoryLedgerStore } from '../server.mjs';

const usage = (tenant_id, idempotency_key, usage_id) => ({
  tenant_id, idempotency_key, usage_id, model: 'test:model', input_tokens: 2, output_tokens: 3,
});
const isConflict = (error) => error instanceof BillingLedgerError && error.status === 409;

test('same tenant cannot admit a second idempotency key for one usage identity', async () => {
  const store = new MemoryLedgerStore();
  const ledger = new BillingLedger({ store });
  const first = await ledger.recordUsage(usage('tenant-a', 'key-1', 'usage-1'));
  assert.equal(first.duplicate, false);
  await assert.rejects(ledger.recordUsage(usage('tenant-a', 'key-2', 'usage-1')), isConflict);
  assert.equal(store.records.size, 1);
});

test('tenant scoped usage identity allows independent tenants to reuse usage ids', async () => {
  const ledger = new BillingLedger();
  assert.equal((await ledger.recordUsage(usage('tenant-a', 'key-1', 'shared'))).duplicate, false);
  assert.equal((await ledger.recordUsage(usage('tenant-b', 'key-2', 'shared'))).duplicate, false);
  assert.equal(ledger.store.records.size, 2);
});

test('legacy same-key replay is unchanged and does not reserve an ignored usage id', async () => {
  const ledger = new BillingLedger();
  await ledger.recordUsage(usage('tenant-a', 'key-1', 'usage-1'));
  const replay = await ledger.recordUsage(usage('tenant-a', 'key-1', 'ignored-usage-id'));
  assert.equal(replay.duplicate, true);
  assert.equal(replay.record.usage_id, 'usage-1');
  assert.equal((await ledger.recordUsage(usage('tenant-a', 'key-2', 'ignored-usage-id'))).duplicate, false);
  assert.equal(ledger.store.records.size, 2);
});

test('direct store API rejects missing tenant, idempotency or usage identity', async () => {
  const store = new MemoryLedgerStore();
  for (const bad of [null, {}, { tenant_id: 'a', idempotency_key: 'key' },
    { tenant_id: '', idempotency_key: 'key', usage_id: 'u' },
    { tenant_id: 'a', idempotency_key: ' ', usage_id: 'u' },
    { tenant_id: 'a', idempotency_key: 'key', usage_id: ' ' }]) {
    await assert.rejects(store.recordUsage(bad), (error) => error instanceof BillingLedgerError && error.status === 400);
  }
  assert.equal(store.records.size, 0);
});

test('duplicate usage conflict leaves original immutable and does not corrupt indexes', async () => {
  const store = new MemoryLedgerStore();
  const ledger = new BillingLedger({ store });
  const original = await ledger.recordUsage(usage('tenant-a', 'key-1', 'usage-1'));
  await assert.rejects(ledger.recordUsage(usage('tenant-a', 'key-2', 'usage-1')), isConflict);
  const replay = await ledger.recordUsage(usage('tenant-a', 'key-1', 'usage-1'));
  assert.equal(replay.duplicate, true);
  assert.deepEqual(replay.record, original.record);
  assert.equal(store.records.size, 1);
});

test('direct invoice store rejects missing tenant and request idempotency identity', async () => {
  const store = new MemoryLedgerStore();
  for (const bad of [null, {}, { tenant_id: 'tenant-a' },
    { tenant_id: '', idempotency_key: 'key' },
    { tenant_id: 'tenant-a', idempotency_key: ' ' }]) {
    await assert.rejects(store.createInvoiceIntent(bad),
      (error) => error instanceof BillingLedgerError && error.status === 400);
  }
  assert.equal(store.invoiceIntents.size, 0);
  const accepted = await store.createInvoiceIntent({ tenant_id: 'tenant-a', idempotency_key: 'key', intent_id: 'intent-a' });
  assert.equal(accepted.intent_id, 'intent-a');
  assert.equal(store.invoiceIntents.size, 1);
});
