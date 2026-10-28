import assert from "node:assert/strict";
import test from "node:test";

import { BillingLedger, createBillingLedgerServer } from "../server.mjs";

const env = { NODE_ENV: "test", Z_PLATFORM_SERVICE_TOKEN: "service-token" };

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

test("records usage idempotently for the same tenant and payload", async () => {
  const ledger = new BillingLedger({ now: () => "2026-07-14T00:00:00.000Z" });
  const input = { usage_id: "usage-1", idempotency_key: "idem-1", tenant_id: "tenant-1", model: "hf:test", input_tokens: 3, output_tokens: 4 };
  const first = await ledger.recordUsage(input);
  const second = await ledger.recordUsage(input);
  assert.equal(first.duplicate, false);
  assert.equal(second.duplicate, true);
  assert.equal(second.record.output_tokens, 4);
});

test("scopes usage idempotency by tenant and rejects changed-payload replay", async () => {
  const ledger = new BillingLedger({ now: () => "2026-07-14T00:00:00.000Z" });
  const input = { usage_id: "usage-1", idempotency_key: "shared-key", tenant_id: "tenant-1", model: "hf:test", input_tokens: 3, output_tokens: 4 };
  const first = await ledger.recordUsage(input);
  const otherTenant = await ledger.recordUsage({ ...input, tenant_id: "tenant-2" });
  assert.equal(first.record.tenant_id, "tenant-1");
  assert.equal(otherTenant.record.tenant_id, "tenant-2");
  assert.equal(otherTenant.duplicate, false);

  const replay = await ledger.recordUsage({ ...input, recorded_at: "2026-07-15T00:00:00.000Z" });
  assert.equal(replay.duplicate, true);
  assert.equal(replay.record.recorded_at, "2026-07-14T00:00:00.000Z");
  await assert.rejects(
    ledger.recordUsage({ ...input, output_tokens: 99 }),
    (error) => error.status === 409,
  );
});

test("scopes invoice idempotency by tenant and rejects amount conflicts", async () => {
  let nextIntent = 0;
  const ledger = new BillingLedger({
    idGenerator: () => `intent-${++nextIntent}`,
    now: () => "2026-07-14T00:00:00.000Z",
  });
  const input = { tenant_id: "tenant-1", idempotency_key: "invoice-key", currency: "usd", amount_minor: 500 };
  const first = await ledger.createInvoiceIntent(input);
  const replay = await ledger.createInvoiceIntent(input);
  assert.equal(replay.intent_id, first.intent_id);

  const otherTenant = await ledger.createInvoiceIntent({ ...input, tenant_id: "tenant-2" });
  assert.notEqual(otherTenant.intent_id, first.intent_id);
  assert.equal(otherTenant.tenant_id, "tenant-2");

  await assert.rejects(
    ledger.createInvoiceIntent({ ...input, amount_minor: 700 }),
    (error) => error.status === 409,
  );
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

test("HTTP routes require service auth and expose no wallet/card authority", async () => {
  const health = await request(createBillingLedgerServer({ env }), "/health");
  assert.deepEqual(await health.json(), { status: "ok", service: "billing-ledger", wallet_authority: false, card_data: false });

  const unauthorized = await request(createBillingLedgerServer({ env }), "/v1/usage", { method: "POST", body: "{}" });
  assert.equal(unauthorized.status, 401);
});

test("memory-backed mutation routes fail closed when NODE_ENV is unset or production", async () => {
  const runtimes = [
    { name: "unset", env: { Z_PLATFORM_SERVICE_TOKEN: "service-token" } },
    { name: "production", env: { ...env, NODE_ENV: "production" } },
  ];
  const mutations = [
    {
      path: "/v1/usage",
      body: { usage_id: "usage-1", idempotency_key: "idem-1", tenant_id: "tenant-1", model: "test" },
    },
    { path: "/v1/credits", body: { tenant_id: "tenant-1", credits: 100 } },
    {
      path: "/v1/invoice-intents",
      body: { tenant_id: "tenant-1", idempotency_key: "invoice-1", currency: "USD", amount_minor: 100 },
    },
  ];

  for (const runtime of runtimes) {
    for (const mutation of mutations) {
      const ledger = new BillingLedger();
      const response = await request(
        createBillingLedgerServer({ env: runtime.env, ledger }),
        mutation.path,
        {
          method: "POST",
          headers,
          body: JSON.stringify(mutation.body),
        },
      );

      assert.equal(response.status, 503, `${runtime.name}: ${mutation.path}`);
      assert.deepEqual(await response.json(), {
        error: "Persistent billing storage is not configured",
      });
      assert.equal(ledger.store.records.size, 0);
      assert.equal(ledger.store.credits.size, 0);
      assert.equal(ledger.store.invoiceIntents.size, 0);
    }
  }
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


test("invalid JSON is a generic client error and is never cacheable", async () => {
  const response = await request(
    createBillingLedgerServer({ env, ledger: new BillingLedger() }),
    "/v1/usage",
    { method: "POST", headers, body: "{" },
  );

  assert.equal(response.status, 400);
  assert.deepEqual(await response.json(), { error: "Invalid JSON body" });
  assert.equal(response.headers.get("cache-control"), "no-store");
});

test("unexpected ledger exceptions are redacted and return HTTP 500", async () => {
  const sensitiveMessage = "database password=must-not-escape";
  const store = {
    async recordUsage() { throw new Error(sensitiveMessage); },
    async setCredits() { throw new Error(sensitiveMessage); },
    async createInvoiceIntent() { throw new Error(sensitiveMessage); },
  };
  const ledger = new BillingLedger({ store });
  const response = await request(
    createBillingLedgerServer({ env, ledger }),
    "/v1/usage",
    {
      method: "POST",
      headers,
      body: JSON.stringify({
        usage_id: "usage-internal-error",
        idempotency_key: "idem-internal-error",
        tenant_id: "tenant-test",
        model: "test",
      }),
    },
  );

  assert.equal(response.status, 500);
  const body = await response.json();
  assert.deepEqual(body, { error: "Internal server error" });
  assert.equal(response.headers.get("cache-control"), "no-store");
  assert.equal(JSON.stringify(body).includes(sensitiveMessage), false);
});
