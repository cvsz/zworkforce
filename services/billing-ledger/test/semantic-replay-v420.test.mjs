import assert from "node:assert/strict";
import test from "node:test";
import { BillingLedger, BillingLedgerError, MemoryLedgerStore } from "../server.mjs";

const conflict = (error) => error instanceof BillingLedgerError && error.status === 409;
const usage = (overrides = {}) => ({
  tenant_id: "tenant-a", idempotency_key: "request-1", usage_id: "usage-1",
  model: "test:model", subject_id: "subject-1", input_tokens: 2,
  output_tokens: 3, ...overrides,
});
const invoice = (overrides = {}) => ({
  tenant_id: "tenant-a", idempotency_key: "invoice-1", currency: "USD",
  amount_minor: 500, ...overrides,
});

test("same-key usage replay accepts equal semantics but ignores recording timestamp", async () => {
  const ledger = new BillingLedger({ now: () => "2026-10-23T00:00:00Z" });
  const first = await ledger.recordUsage(usage());
  const replay = await ledger.recordUsage(usage({ recorded_at: "2026-10-24T00:00:00Z" }));
  assert.equal(first.duplicate, false);
  assert.equal(replay.duplicate, true);
  assert.deepEqual(replay.record, first.record);
  assert.equal(ledger.store.records.size, 1);
});

test("same-key usage replay rejects changed financial or identity semantics", async () => {
  for (const change of [
    { usage_id: "usage-2" }, { input_tokens: 4 }, { output_tokens: 5 },
    { model: "test:other" }, { subject_id: "subject-2" },
  ]) {
    const ledger = new BillingLedger();
    await ledger.recordUsage(usage());
    await assert.rejects(ledger.recordUsage(usage(change)), conflict);
    assert.equal(ledger.store.records.size, 1);
    assert.equal(ledger.store.usageIdentity.size, 1);
    assert.equal(ledger.store.records.values().next().value.usage_id, "usage-1");
  }
});

test("rejected replay does not reserve the rejected usage identity", async () => {
  const ledger = new BillingLedger();
  await ledger.recordUsage(usage());
  await assert.rejects(ledger.recordUsage(usage({ usage_id: "usage-2" })), conflict);
  const accepted = await ledger.recordUsage(usage({ idempotency_key: "request-2", usage_id: "usage-2" }));
  assert.equal(accepted.duplicate, false);
  assert.equal(ledger.store.records.size, 2);
});

test("direct-store replay cannot bypass semantic conflict checks", async () => {
  const store = new MemoryLedgerStore();
  await store.recordUsage(usage());
  await assert.rejects(store.recordUsage(usage({ input_tokens: 8 })), conflict);
  await assert.rejects(store.recordUsage(usage({ output_tokens: 8 })), conflict);
  assert.equal(store.records.size, 1);
});

test("same-key invoice replay ignores generated ID and timestamp", async () => {
  let sequence = 0;
  const ledger = new BillingLedger({ idGenerator: () => `intent-${++sequence}`, now: () => new Date().toISOString() });
  const first = await ledger.createInvoiceIntent(invoice());
  const replay = await ledger.createInvoiceIntent(invoice());
  assert.deepEqual(replay, first);
  assert.equal(ledger.store.invoiceIntents.size, 1);
});

test("invoice replay rejects amount, currency and status conflicts", async () => {
  for (const change of [{ amount_minor: 501 }, { currency: "EUR" }]) {
    const ledger = new BillingLedger();
    const first = await ledger.createInvoiceIntent(invoice());
    await assert.rejects(ledger.createInvoiceIntent(invoice(change)), conflict);
    assert.equal(ledger.store.invoiceIntents.size, 1);
    assert.equal(ledger.store.invoiceIntents.values().next().value.amount_minor, first.amount_minor);
  }
  const store = new MemoryLedgerStore();
  await store.createInvoiceIntent({ ...invoice(), intent_id: "one", status: "requires_payment_processor" });
  await assert.rejects(store.createInvoiceIntent({ ...invoice(), intent_id: "two", status: "paid" }), conflict);
});

test("duplicate result mutations do not alter stored financial records", async () => {
  const store = new MemoryLedgerStore();
  const first = await store.recordUsage(usage());
  first.record.input_tokens = 900;
  const replay = await store.recordUsage(usage());
  replay.record.input_tokens = 901;
  assert.equal((await store.recordUsage(usage())).record.input_tokens, 2);

  const invoiceFirst = await store.createInvoiceIntent({ ...invoice(), intent_id: "intent-1" });
  invoiceFirst.amount_minor = 900;
  const invoiceReplay = await store.createInvoiceIntent({ ...invoice(), intent_id: "intent-2" });
  invoiceReplay.amount_minor = 901;
  assert.equal((await store.createInvoiceIntent({ ...invoice(), intent_id: "intent-3" })).amount_minor, 500);
});

test("identical keys in distinct tenants remain independent", async () => {
  const ledger = new BillingLedger();
  await ledger.recordUsage(usage());
  await ledger.recordUsage(usage({ tenant_id: "tenant-b", input_tokens: 900 }));
  await ledger.createInvoiceIntent(invoice());
  await ledger.createInvoiceIntent(invoice({ tenant_id: "tenant-b", amount_minor: 1000 }));
  assert.equal(ledger.store.records.size, 2);
  assert.equal(ledger.store.invoiceIntents.size, 2);
});
