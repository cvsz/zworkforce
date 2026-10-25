import assert from "node:assert/strict";
import test from "node:test";
import { BillingLedger, MemoryLedgerStore } from "../server.mjs";

const usage = (tenant_id, idempotency_key, usage_id, input_tokens = 1) => ({
  tenant_id, idempotency_key, usage_id, model: "test:model",
  input_tokens, output_tokens: 0,
});

test("usage idempotency keys are isolated by trusted ledger tenant field", async () => {
  const store = new MemoryLedgerStore();
  const ledger = new BillingLedger({ store });
  const a = await ledger.recordUsage(usage("tenant-a", "shared-key", "usage-a", 2));
  const b = await ledger.recordUsage(usage("tenant-b", "shared-key", "usage-b", 7));
  assert.equal(a.duplicate, false);
  assert.equal(b.duplicate, false);
  assert.equal(b.record.tenant_id, "tenant-b");
  assert.equal(b.record.input_tokens, 7);
  assert.equal(store.records.size, 2);
  const replay = await ledger.recordUsage(usage("tenant-a", "shared-key", "usage-a-replay", 99));
  assert.equal(replay.duplicate, true);
  assert.equal(replay.record.tenant_id, "tenant-a");
  assert.equal(replay.record.input_tokens, 2);
});

test("invoice intent replay is isolated by tenant and preserves same-tenant idempotency", async () => {
  let sequence = 0;
  const store = new MemoryLedgerStore();
  const ledger = new BillingLedger({ store, idGenerator: () => `intent-${++sequence}`, now: () => "2026-10-23T00:00:00.000Z" });
  const input = (tenant_id, amount_minor) => ({
    tenant_id, idempotency_key: "shared-invoice", currency: "USD", amount_minor,
  });
  const a = await ledger.createInvoiceIntent(input("tenant-a", 100));
  const b = await ledger.createInvoiceIntent(input("tenant-b", 900));
  const replay = await ledger.createInvoiceIntent(input("tenant-a", 500));
  assert.equal(a.tenant_id, "tenant-a");
  assert.equal(b.tenant_id, "tenant-b");
  assert.notEqual(a.intent_id, b.intent_id);
  assert.equal(b.amount_minor, 900);
  assert.deepEqual(replay, a);
  assert.equal(store.invoiceIntents.size, 2);
});

test("structured idempotency keys cannot collide on separators", async () => {
  const store = new MemoryLedgerStore();
  const ledger = new BillingLedger({ store });
  const a = await ledger.recordUsage(usage("tenant|a", "b|c", "usage-1"));
  const b = await ledger.recordUsage(usage("tenant", "a|b|c", "usage-2"));
  assert.equal(a.duplicate, false);
  assert.equal(b.duplicate, false);
  assert.equal(store.records.size, 2);
});

test("HTTP financial writes remain fail-closed after tenant-scoping change", async () => {
  const { createBillingLedgerServer } = await import("../server.mjs");
  const server = createBillingLedgerServer({ env: { Z_PLATFORM_SERVICE_TOKEN: "local-test-token" } });
  await new Promise((resolve) => server.listen(0, "127.0.0.1", resolve));
  try {
    const response = await fetch(`http://127.0.0.1:${server.address().port}/v1/usage`, {
      method: "POST",
      headers: { Authorization: "Bearer local-test-token", "Content-Type": "application/json" },
      body: JSON.stringify(usage("tenant-a", "shared-key", "usage-a")),
    });
    assert.equal(response.status, 503);
    assert.equal(response.headers.get("cache-control"), "no-store");
  } finally {
    await new Promise((resolve, reject) => server.close((error) => error ? reject(error) : resolve()));
  }
});
