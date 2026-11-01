import assert from "node:assert/strict";
import test from "node:test";
import { BillingLedger, BillingLedgerError, MemoryLedgerStore } from "../server.mjs";

const valid = {
  tenant_id: "tenant-a",
  idempotency_key: "invoice-1",
  intent_id: "intent-1",
  currency: "USD",
  amount_minor: 100,
  status: "requires_payment_processor",
};

const badRequest = (error) => error instanceof BillingLedgerError && error.status === 400;
const conflict = (error) => error instanceof BillingLedgerError && error.status === 409;

test("direct store rejects forged initial invoice states without reserving a key", async () => {
  for (const status of ["paid", "succeeded", "refunded", "canceled", "processing", "", null, false, 0]) {
    const store = new MemoryLedgerStore();
    await assert.rejects(store.createInvoiceIntent({ ...valid, status }), badRequest);
    assert.equal(store.invoiceIntents.size, 0);
    const accepted = await store.createInvoiceIntent(valid);
    assert.equal(accepted.status, "requires_payment_processor");
    assert.equal(store.invoiceIntents.size, 1);
  }
});

test("conflicting replay status still returns 409 and preserves original intent", async () => {
  const store = new MemoryLedgerStore();
  const original = await store.createInvoiceIntent(valid);
  for (const status of ["paid", "refunded", null]) {
    await assert.rejects(store.createInvoiceIntent({ ...valid, status }), conflict);
    assert.deepEqual(await store.createInvoiceIntent(valid), original);
    assert.equal(store.invoiceIntents.size, 1);
  }
});

test("legacy direct-store callers may omit status; ledger creates only pending intents", async () => {
  const store = new MemoryLedgerStore();
  const legacy = { ...valid };
  delete legacy.status;
  assert.deepEqual(await store.createInvoiceIntent(legacy), legacy);
  assert.equal(store.invoiceIntents.size, 1);

  const ledger = new BillingLedger({ idGenerator: () => "intent-2", now: () => "2026-10-23T00:00:00Z" });
  const intent = await ledger.createInvoiceIntent({
    tenant_id: "tenant-b", idempotency_key: "invoice-2", currency: "usd", amount_minor: "100",
  });
  assert.equal(intent.status, "requires_payment_processor");
  assert.equal(intent.amount_minor, 100);
});
