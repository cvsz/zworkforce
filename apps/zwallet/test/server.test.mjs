import assert from "node:assert/strict";
import test from "node:test";

import { createInvoiceIntent, createZWalletServer } from "../server.mjs";

const env = { Z_PLATFORM_BILLING_LEDGER_URL: "http://ledger", Z_PLATFORM_SERVICE_TOKEN: "service-token" };

async function request(server, path, options = {}) {
  await new Promise((resolve) => server.listen(0, "127.0.0.1", resolve));
  const { port } = server.address();
  try {
    return await fetch(`http://127.0.0.1:${port}${path}`, options);
  } finally {
    await new Promise((resolve, reject) => server.close((error) => error ? reject(error) : resolve()));
  }
}

test("health exposes no wallet or card authority", async () => {
  const response = await request(createZWalletServer({ env }), "/health");
  assert.deepEqual(await response.json(), { status: "ok", service: "zwallet-adapter", ledger_configured: true, wallet_authority: false, card_data: false });
});

test("invoice intents forward only audited billing fields", async () => {
  const calls = [];
  const result = await createInvoiceIntent({ tenant_id: "tenant-1", idempotency_key: "invoice-1", currency: "USD", amount_minor: 500 }, env, async (url, options) => {
    calls.push({ url, options });
    return Response.json({ intent_id: "intent-1" }, { status: 201 });
  });
  assert.deepEqual(result, { intent_id: "intent-1" });
  assert.equal(calls[0].url, "http://ledger/v1/invoice-intents");
  assert.equal(calls[0].options.headers.Authorization, "Bearer service-token");
});


test("maps ledger 503 to a generic retryable response without leaking or retrying", async () => {
  const calls = [];
  const response = await request(
    createZWalletServer({
      env,
      fetchImpl: async (url, options) => {
        calls.push({ url, options });
        return Response.json({ error: "private upstream diagnostics" }, {
          status: 503,
          headers: { "Retry-After": "30" },
        });
      },
    }),
    "/api/invoice-intents",
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ tenant_id: "tenant-1", idempotency_key: "invoice-503", currency: "USD", amount_minor: 500 }),
    },
  );

  assert.equal(response.status, 503);
  assert.deepEqual(await response.json(), { error: "Billing ledger unavailable" });
  assert.equal(response.headers.get("cache-control"), "no-store");
  assert.equal(response.headers.get("retry-after"), null);
  assert.equal(calls.length, 1);
});

test("maps transport failure to generic 503 and makes exactly one attempt", async () => {
  let calls = 0;
  const response = await request(
    createZWalletServer({
      env,
      fetchImpl: async () => {
        calls += 1;
        throw new Error("private socket and host details");
      },
    }),
    "/api/credits",
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ tenant_id: "tenant-1", idempotency_key: "credit-503", amount_minor: 100 }),
    },
  );

  assert.equal(response.status, 503);
  assert.deepEqual(await response.json(), { error: "Billing ledger unavailable" });
  assert.equal(response.headers.get("cache-control"), "no-store");
  assert.equal(response.headers.get("retry-after"), null);
  assert.equal(calls, 1);
});

test("missing billing configuration fails closed without calling upstream", async () => {
  let calls = 0;
  const response = await request(
    createZWalletServer({
      env: {},
      fetchImpl: async () => {
        calls += 1;
        return Response.json({});
      },
    }),
    "/api/invoice-intents",
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ tenant_id: "tenant-1", idempotency_key: "invoice-unconfigured", currency: "USD", amount_minor: 500 }),
    },
  );

  assert.equal(response.status, 503);
  assert.deepEqual(await response.json(), { error: "Billing ledger unavailable" });
  assert.equal(response.headers.get("cache-control"), "no-store");
  assert.equal(calls, 0);
});

test("invalid JSON from a successful ledger response fails closed", async () => {
  const response = await request(
    createZWalletServer({
      env,
      fetchImpl: async () => new Response("private upstream payload", { status: 200 }),
    }),
    "/api/invoice-intents",
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ tenant_id: "tenant-1", idempotency_key: "invoice-invalid-json", currency: "USD", amount_minor: 500 }),
    },
  );

  assert.equal(response.status, 503);
  assert.deepEqual(await response.json(), { error: "Billing ledger unavailable" });
  assert.equal(response.headers.get("cache-control"), "no-store");
});

test("ledger client errors remain 400 without exposing upstream details", async () => {
  const response = await request(
    createZWalletServer({
      env,
      fetchImpl: async () => Response.json({ error: "private validation details" }, { status: 422 }),
    }),
    "/api/invoice-intents",
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ tenant_id: "tenant-1", idempotency_key: "invoice-invalid", currency: "USD", amount_minor: 500 }),
    },
  );

  assert.equal(response.status, 400);
  assert.deepEqual(await response.json(), { error: "Billing ledger rejected the request" });
  assert.equal(response.headers.get("cache-control"), "no-store");
});


test("ledger timeout maps to retryable 503 without retrying", async () => {
  let calls = 0;
  const timeoutEnv = { ...env, Z_PLATFORM_BILLING_LEDGER_TIMEOUT_MS: "25" };
  const response = await request(
    createZWalletServer({
      env: timeoutEnv,
      fetchImpl: async (_url, options) => {
        calls += 1;
        await new Promise((resolve, reject) => {
          const abort = () => reject(options.signal.reason);
          if (options.signal.aborted) abort();
          else options.signal.addEventListener("abort", abort, { once: true });
        });
      },
    }),
    "/api/invoice-intents",
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ tenant_id: "tenant-1", idempotency_key: "invoice-timeout", currency: "USD", amount_minor: 500 }),
    },
  );

  assert.equal(response.status, 503);
  assert.deepEqual(await response.json(), { error: "Billing ledger unavailable" });
  assert.equal(response.headers.get("cache-control"), "no-store");
  assert.equal(calls, 1);
});

test("invalid timeout configuration fails closed without calling upstream", async () => {
  let calls = 0;
  const response = await request(
    createZWalletServer({
      env: { ...env, Z_PLATFORM_BILLING_LEDGER_TIMEOUT_MS: "invalid" },
      fetchImpl: async () => {
        calls += 1;
        return Response.json({});
      },
    }),
    "/api/credits",
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ tenant_id: "tenant-1", idempotency_key: "credit-timeout-invalid", amount_minor: 100 }),
    },
  );

  assert.equal(response.status, 503);
  assert.equal(calls, 0);
});

test("non-object JSON is rejected before upstream access", async () => {
  let calls = 0;
  const response = await request(
    createZWalletServer({
      env,
      fetchImpl: async () => {
        calls += 1;
        return Response.json({});
      },
    }),
    "/api/invoice-intents",
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: "null",
    },
  );

  assert.equal(response.status, 400);
  assert.deepEqual(await response.json(), { error: "JSON body must be an object" });
  assert.equal(calls, 0);
});

test("oversized request bodies are rejected before upstream access", async () => {
  let calls = 0;
  const response = await request(
    createZWalletServer({
      env,
      fetchImpl: async () => {
        calls += 1;
        return Response.json({});
      },
    }),
    "/api/invoice-intents",
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ payload: "x".repeat(64 * 1024) }),
    },
  );

  assert.equal(response.status, 413);
  assert.deepEqual(await response.json(), { error: "Request body too large" });
  assert.equal(calls, 0);
});

test("direct adapter calls reject non-object input", async () => {
  let calls = 0;
  await assert.rejects(
    createInvoiceIntent(null, env, async () => {
      calls += 1;
      return Response.json({});
    }),
    /JSON body must be an object/,
  );
  assert.equal(calls, 0);
});

test("adapter rejects signing, card, KYC, MPC, and swap payloads", async () => {
  await assert.rejects(
    createInvoiceIntent({ tenant_id: "tenant-1", idempotency_key: "invoice-1", currency: "USD", amount_minor: 500, wallet_signature: "nope" }, env, async () => Response.json({})),
    /wallet_signature is not accepted/,
  );
});
