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

const invoiceBody = {
  tenant_id: "tenant-1",
  idempotency_key: "invoice-1",
  currency: "USD",
  amount_minor: 500,
};

test("health exposes no wallet or card authority", async () => {
  const response = await request(createZWalletServer({ env }), "/health");
  assert.deepEqual(await response.json(), {
    status: "ok",
    service: "zwallet-adapter",
    ledger_configured: true,
    wallet_authority: false,
    card_data: false,
  });
});

test("health does not treat blank ledger configuration as configured", async () => {
  const response = await request(
    createZWalletServer({ env: { Z_PLATFORM_BILLING_LEDGER_URL: "   ", Z_PLATFORM_SERVICE_TOKEN: "  " } }),
    "/health",
  );
  assert.deepEqual(await response.json(), {
    status: "ok",
    service: "zwallet-adapter",
    ledger_configured: false,
    wallet_authority: false,
    card_data: false,
  });
});

test("invoice intents forward only audited billing fields", async () => {
  const calls = [];
  const result = await createInvoiceIntent(invoiceBody, env, async (url, options) => {
    calls.push({ url, options });
    return Response.json({ intent_id: "intent-1" }, { status: 201 });
  });
  assert.deepEqual(result, { intent_id: "intent-1" });
  assert.equal(calls.length, 1);
  assert.equal(calls[0].url, "http://ledger/v1/invoice-intents");
  assert.equal(calls[0].options.headers.Authorization, "Bearer service-token");
});

test("adapter rejects signing, card, KYC, MPC, and swap payloads", async () => {
  await assert.rejects(
    createInvoiceIntent({ ...invoiceBody, wallet_signature: "nope" }, env, async () => Response.json({})),
    /wallet_signature is not accepted/,
  );
});

test("downstream failures return generic no-store 503 and are never retried", async (t) => {
  const failures = [
    {
      name: "downstream HTTP 503",
      fetchImpl: async () => new Response(JSON.stringify({ error: "internal provider detail" }), { status: 503 }),
    },
    {
      name: "transport failure",
      fetchImpl: async () => {
        throw new Error("private host 10.0.0.4 token=must-not-leak");
      },
    },
    {
      name: "invalid JSON from successful response",
      fetchImpl: async () => new Response("{invalid-json", { status: 200 }),
    },
    {
      name: "non-object JSON from successful response",
      fetchImpl: async () => Response.json(["unexpected"], { status: 200 }),
    },
  ];

  for (const failure of failures) {
    await t.test(failure.name, async () => {
      let attempts = 0;
      const fetchImpl = async (...args) => {
        attempts += 1;
        return failure.fetchImpl(...args);
      };
      const response = await request(
        createZWalletServer({ env, fetchImpl }),
        "/api/invoice-intents",
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(invoiceBody),
        },
      );

      assert.equal(response.status, 503);
      assert.equal(response.headers.get("cache-control"), "no-store");
      assert.equal(response.headers.get("retry-after"), null);
      assert.deepEqual(await response.json(), { error: "Billing service unavailable" });
      assert.equal(attempts, 1, "financial mutations must not be automatically retried");
    });
  }
});

test("missing ledger configuration fails closed without making a request", async () => {
  let attempts = 0;
  const response = await request(
    createZWalletServer({
      env: {},
      fetchImpl: async () => {
        attempts += 1;
        return Response.json({ intent_id: "must-not-exist" }, { status: 201 });
      },
    }),
    "/api/invoice-intents",
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(invoiceBody),
    },
  );

  assert.equal(response.status, 503);
  assert.equal(response.headers.get("cache-control"), "no-store");
  assert.deepEqual(await response.json(), { error: "Billing service unavailable" });
  assert.equal(attempts, 0);
});
