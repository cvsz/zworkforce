import assert from "node:assert/strict";
import test from "node:test";
import { BillingLedger, BillingLedgerError, MemoryLedgerStore, createBillingLedgerServer } from "../server.mjs";

function denied(error) {
  return error instanceof BillingLedgerError && error.status === 503 &&
    error.message === "Credit writes require independent approval";
}

test("direct MemoryLedgerStore credit writes fail closed without mutating existing state", async () => {
  const store = new MemoryLedgerStore();
  store.credits.set("tenant-a", 5);
  for (const value of [0, 1, 100, -1, "100", true, null, Number.NaN]) {
    await assert.rejects(store.setCredits("tenant-a", value), denied);
    assert.equal(store.credits.get("tenant-a"), 5);
  }
  assert.equal(store.credits.size, 1);
});

test("BillingLedger does not delegate credit writes to an injected store", async () => {
  let calls = 0;
  const store = { setCredits: async () => { calls++; throw new Error("must not be called"); } };
  const ledger = new BillingLedger({ store });
  await assert.rejects(ledger.setCredits({ tenant_id: "tenant-a", credits: 100 }), denied);
  await assert.rejects(ledger.setCredits(null), denied);
  assert.equal(calls, 0);
});

test("HTTP credit route returns authenticated 503 and never reaches injected store", async () => {
  const token = "test-credit-token";
  const env = { Z_PLATFORM_SERVICE_TOKEN: token };
  const ledger = new BillingLedger({ store: new Proxy({}, { get() { throw new Error("unexpected store access"); } }) });
  const server = createBillingLedgerServer({ env, ledger });
  await new Promise(resolve => server.listen(0, "127.0.0.1", resolve));
  try {
    const url = `http://127.0.0.1:${server.address().port}/v1/credits`;
    const response = await fetch(url, {
      method: "POST", headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json" },
      body: JSON.stringify({ tenant_id: "tenant-a", credits: 100 }),
    });
    assert.equal(response.status, 503);
    assert.equal(response.headers.get("cache-control"), "no-store");
    assert.match((await response.json()).error, /disabled/);
  } finally {
    await new Promise((resolve, reject) => server.close(error => error ? reject(error) : resolve()));
  }
});
