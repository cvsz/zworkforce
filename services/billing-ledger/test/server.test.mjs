import assert from "node:assert/strict";
import test from "node:test";

import { BillingLedger, BillingLedgerError, createBillingLedgerServer } from "../server.mjs";

const env = { Z_PLATFORM_SERVICE_TOKEN: "service-token", NODE_ENV: "test" };

async function request(server, path, options = {}) {
  await new Promise((resolve) => server.listen(0, "127.0.0.1", resolve));
  const { port } = server.address();
  try {
    return await fetch(`http://127.0.0.1:${port}${path}`, options);
  } finally {
    await new Promise((resolve, reject) => server.close((error) => error ? reject(error) : resolve()));
  }
}

const headers = { Authorization: "Bearer service-token", "Content-Type": "application/json" };

test("records usage idempotently", async () => {
  const ledger = new BillingLedger({ now: () => "2026-07-14T00:00:00.000Z" });
  const input = { usage_id: "usage-1", idempotency_key: "idem-1", tenant_id: "tenant-1", model: "hf:test", input_tokens: 3, output_tokens: 4 };
  const first = await ledger.recordUsage(input);
  const second = await ledger.recordUsage({ ...input, output_tokens: 99 });
  assert.equal(first.duplicate, false);
  assert.equal(second.duplicate, true);
  assert.equal(second.record.output_tokens, 4);
});

test("creates credits and invoice intents without wallet authority", async () => {
  const ledger = new BillingLedger({ idGenerator: () => "intent-1", now: () => "2026-07-14T00:00:00.000Z" });
  assert.deepEqual(await ledger.setCredits({ tenant_id: "tenant-1", credits: 100 }), { tenant_id: "tenant-1", credits: 100 });
  assert.deepEqual(await ledger.createInvoiceIntent({ tenant_id: "tenant-1", idempotency_key: "invoice-1", currency: "usd", amount_minor: 500 }), {
    intent_id: "intent-1",
    idempotency_key: "invoice-1",
    tenant_id: "tenant-1",
    currency: "USD",
    amount_minor: 500,
    status: "requires_payment_processor",
    created_at: "2026-07-14T00:00:00.000Z",
  });
});

test("invoice idempotency is tenant-scoped and rejects payload conflicts", async () => {
  let nextId = 0;
  const ledger = new BillingLedger({
    idGenerator: () => `intent-${++nextId}`,
    now: () => "2026-07-14T00:00:00.000Z",
  });
  const input = { tenant_id: "tenant-1", idempotency_key: "shared-key", currency: "usd", amount_minor: 500 };
  const first = await ledger.createInvoiceIntent(input);
  const retry = await ledger.createInvoiceIntent({ ...input, currency: "USD" });
  assert.deepEqual(retry, first);

  await assert.rejects(
    ledger.createInvoiceIntent({ ...input, amount_minor: 501 }),
    (error) => error instanceof BillingLedgerError && error.status === 409,
  );

  const otherTenant = await ledger.createInvoiceIntent({ ...input, tenant_id: "tenant-2" });
  assert.equal(otherTenant.tenant_id, "tenant-2");
  assert.notEqual(otherTenant.intent_id, first.intent_id);
});

test("HTTP routes require service auth and expose no wallet/card authority", async () => {
  const health = await request(createBillingLedgerServer({ env }), "/health");
  assert.deepEqual(await health.json(), { status: "ok", service: "billing-ledger", wallet_authority: false, card_data: false });

  const unauthorized = await request(createBillingLedgerServer({ env }), "/v1/usage", { method: "POST", body: "{}" });
  assert.equal(unauthorized.status, 401);
});

test("blocks all HTTP billing mutations when the memory store is active outside explicit development/test mode", async () => {
  for (const nodeEnv of [undefined, "production"]) {
    const runtimeEnv = { ...env };
    if (nodeEnv === undefined) delete runtimeEnv.NODE_ENV;
    else runtimeEnv.NODE_ENV = nodeEnv;

    const ledger = new BillingLedger({ idGenerator: () => "blocked-intent" });
    const cases = [
      ["/v1/usage", { usage_id: "usage-blocked", idempotency_key: "usage-blocked", tenant_id: "tenant-1", model: "test" }],
      ["/v1/credits", { tenant_id: "tenant-1", credits: 100 }],
      ["/v1/invoice-intents", { tenant_id: "tenant-1", idempotency_key: "invoice-blocked", currency: "USD", amount_minor: 500 }],
    ];

    for (const [path, payload] of cases) {
      const response = await request(
        createBillingLedgerServer({ env: runtimeEnv, ledger }),
        path,
        { method: "POST", headers, body: JSON.stringify(payload) },
      );
      assert.equal(response.status, 503, `NODE_ENV=${nodeEnv ?? "unset"} ${path}`);
      assert.deepEqual(await response.json(), { error: "Durable billing store unavailable" });
    }

    assert.equal(ledger.store.records.size, 0);
    assert.equal(ledger.store.credits.size, 0);
    assert.equal(ledger.store.invoiceIntents.size, 0);
  }
});

test("liveness remains healthy while readiness fails closed for an ephemeral production store", async () => {
  const productionEnv = { ...env, NODE_ENV: "production" };
  const health = await request(createBillingLedgerServer({ env: productionEnv }), "/health");
  assert.equal(health.status, 200);
  assert.deepEqual(await health.json(), { status: "ok", service: "billing-ledger", wallet_authority: false, card_data: false });

  const productionReady = await request(createBillingLedgerServer({ env: productionEnv }), "/ready");
  assert.equal(productionReady.status, 503);
  assert.deepEqual(await productionReady.json(), {
    status: "not_ready",
    service: "billing-ledger",
    reason: "durable_store_required",
  });

  const unsetEnv = { ...env };
  delete unsetEnv.NODE_ENV;
  const unsetReady = await request(createBillingLedgerServer({ env: unsetEnv }), "/ready");
  assert.equal(unsetReady.status, 503);

  const testReady = await request(createBillingLedgerServer({ env }), "/ready");
  assert.equal(testReady.status, 200);
  assert.deepEqual(await testReady.json(), { status: "ready", service: "billing-ledger" });
});

test("HTTP usage endpoint returns duplicate on repeated idempotency key", async () => {
  const server = createBillingLedgerServer({ env, ledger: new BillingLedger({ now: () => "2026-07-14T00:00:00.000Z" }) });
  await new Promise((resolve) => server.listen(0, "127.0.0.1", resolve));
  const { port } = server.address();
  try {
    const payload = { usage_id: "usage-1", idempotency_key: "idem-1", tenant_id: "tenant-1", model: "hf:test" };
    const first = await fetch(`http://127.0.0.1:${port}/v1/usage`, { method: "POST", headers, body: JSON.stringify(payload) });
    const second = await fetch(`http://127.0.0.1:${port}/v1/usage`, { method: "POST", headers, body: JSON.stringify(payload) });
    assert.equal(first.status, 201);
    assert.equal(second.status, 200);
    assert.equal((await second.json()).duplicate, true);
  } finally {
    await new Promise((resolve, reject) => server.close((error) => error ? reject(error) : resolve()));
  }
});
