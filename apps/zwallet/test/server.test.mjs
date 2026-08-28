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

test("adapter rejects signing, card, KYC, MPC, and swap payloads", async () => {
  await assert.rejects(
    createInvoiceIntent({ tenant_id: "tenant-1", idempotency_key: "invoice-1", currency: "USD", amount_minor: 500, wallet_signature: "nope" }, env, async () => Response.json({})),
    /wallet_signature is not accepted/,
  );
});
