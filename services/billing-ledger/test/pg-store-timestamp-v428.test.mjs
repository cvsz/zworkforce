import assert from 'node:assert/strict';
import test from 'node:test';
import { PgFinancialStore } from '../pg-store.mjs';

const usage = Object.freeze({
  event_type: 'ai.usage.recorded.v1', event_version: 'v1',
  tenant_id: 'tenant-a', usage_id: 'usage-1', idempotency_key: 'request-1',
  subject_id: 'subject-1', model: 'test-model',
  input_tokens: 2, output_tokens: 3, recorded_at: '2026-10-24T12:00:00.000Z',
});
const invoice = Object.freeze({
  tenant_id: 'tenant-a', intent_id: '00000000-0000-4000-8000-000000000001',
  idempotency_key: 'invoice-1', amount_minor: 1200, currency: 'USD',
  status: 'requires_payment_processor', created_at: '2026-10-24T12:00:00.000Z',
});
function harness() {
  let connects = 0;
  const store = new PgFinancialStore({
    pool: { async connect() { connects++; throw new Error('synthetic connection acquired'); } },
    resolveTenant: async () => 'tenant-a',
    expectedLoginRole: 'zeaz_financial_app_test',
  });
  return { store, get connects() { return connects; } };
}

for (const timestamp of [
  '2026-02-30T12:00:00.000Z',
  '2026-02-29T12:00:00.000Z',
  '2026-10-24T12:00:00',
  '2026-10-24',
  '2026-10-24T12:00:00.123456Z',
  '2026-10-24T12:00:00+14:30',
  '2026-10-24T12:00:00-00:00',
  '2026-13-24T12:00:00.000Z',
]) {
  test(`rejects invalid usage and invoice timestamp before database access: ${timestamp}`, async () => {
    const h = harness();
    await assert.rejects(h.store.recordUsage({}, { ...usage, recorded_at: timestamp }),
      error => error.status === 400);
    await assert.rejects(h.store.createInvoiceIntent({}, { ...invoice, created_at: timestamp }),
      error => error.status === 400);
    assert.equal(h.connects, 0);
  });
}

for (const timestamp of [
  '2024-02-29T12:00:00Z',
  '2026-10-24T12:00:00.000Z',
  '2026-10-24T19:00:00+07:00',
  '2026-10-24T12:00:00.1Z',
]) {
  test(`preserves valid RFC3339 financial timestamps: ${timestamp}`, async () => {
    const h = harness();
    await assert.rejects(h.store.recordUsage({}, { ...usage, recorded_at: timestamp }),
      /synthetic connection acquired/);
    await assert.rejects(h.store.createInvoiceIntent({}, { ...invoice, created_at: timestamp }),
      /synthetic connection acquired/);
    assert.equal(h.connects, 2);
  });
}
