import assert from "node:assert/strict";
import test from "node:test";
import { BillingLedger, BillingLedgerError, MemoryLedgerStore, createBillingLedgerServer } from "../server.mjs";

const valid = {
  tenant_id: "tenant-a", idempotency_key: "request-a",
  intent_id: "intent-a", currency: "USD", amount_minor: 100,
};
const invalid = [undefined, null, NaN, Infinity, -Infinity, 0, -1, 1.5,
  Number.MAX_SAFE_INTEGER + 1, "100", "NaN", "Infinity"];
const isBadRequest = (error) => error instanceof BillingLedgerError && error.status === 400;

test("direct invoice store rejects unsafe minor units without mutation", async () => {
  for (const amount_minor of invalid) {
    const store = new MemoryLedgerStore();
    await assert.rejects(store.createInvoiceIntent({ ...valid, amount_minor }), isBadRequest,
      `amount_minor=${String(amount_minor)}`);
    assert.equal(store.invoiceIntents.size, 0);
  }
});

test("direct invoice store validates malformed replays before returning stored intents", async () => {
  const store = new MemoryLedgerStore();
  const first = await store.createInvoiceIntent(valid);
  for (const amount_minor of invalid) {
    await assert.rejects(store.createInvoiceIntent({ ...valid, amount_minor }), isBadRequest);
  }
  assert.deepEqual(await store.createInvoiceIntent({ ...valid }), first);
  assert.equal(store.invoiceIntents.size, 1);
  assert.equal(store.invoiceIntents.values().next().value.amount_minor, 100);
});

test("ledger rejects unsafe invoice amounts and retains valid numeric string compatibility", async () => {
  const ledger = new BillingLedger({ idGenerator: () => "intent-a", now: () => "2026-10-23T00:00:00.000Z" });
  for (const amount_minor of [NaN, Infinity, -Infinity, 0, -1, 1.5, Number.MAX_SAFE_INTEGER + 1, "NaN", "Infinity", true, false, [100], {}, "0x10", "1e2", " 100 ", "+100", "100.0", "0100", "00100"]) {
    await assert.rejects(ledger.createInvoiceIntent({ ...valid, amount_minor }), isBadRequest);
  }
  assert.equal(ledger.store.invoiceIntents.size, 0);
  const accepted = await ledger.createInvoiceIntent({ ...valid, amount_minor: "100" });
  assert.equal(accepted.amount_minor, 100);
  assert.equal(ledger.store.invoiceIntents.size, 1);
});

test("direct invoice store accepts maximum safe integer and tenant-separated keys", async () => {
  const store = new MemoryLedgerStore();
  const first = await store.createInvoiceIntent({ ...valid, amount_minor: Number.MAX_SAFE_INTEGER });
  const second = await store.createInvoiceIntent({ ...valid, tenant_id: "tenant-b", amount_minor: 200 });
  assert.equal(first.amount_minor, Number.MAX_SAFE_INTEGER);
  assert.equal(second.tenant_id, "tenant-b");
  assert.equal(store.invoiceIntents.size, 2);
});

test("financial HTTP invoice mutation stays disabled", async () => {
  const server = createBillingLedgerServer({ env: { Z_PLATFORM_SERVICE_TOKEN: "test-only" } });
  await new Promise((resolve) => server.listen(0, "127.0.0.1", resolve));
  try {
    const response = await fetch(`http://127.0.0.1:${server.address().port}/v1/invoice-intents`, {
      method: "POST", headers: { Authorization: "Bearer test-only", "Content-Type": "application/json" },
      body: JSON.stringify(valid),
    });
    assert.equal(response.status, 503);
    assert.equal(response.headers.get("cache-control"), "no-store");
  } finally {
    await new Promise((resolve, reject) => server.close((error) => error ? reject(error) : resolve()));
  }
});
