import assert from "node:assert/strict";
import { request as nodeRequest } from "node:http";
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

async function requestRawTarget(server, target, options = {}) {
  await new Promise((resolve) => server.listen(0, "127.0.0.1", resolve));
  const { port } = server.address();
  try {
    return await new Promise((resolve, reject) => {
      const outgoing = nodeRequest(
        {
          hostname: "127.0.0.1",
          port,
          method: options.method || "GET",
          path: target,
          headers: options.headers || {},
        },
        (incoming) => {
          const chunks = [];
          incoming.on("data", (chunk) => chunks.push(chunk));
          incoming.on("end", () => {
            const body = Buffer.concat(chunks).toString("utf8");
            resolve({
              status: incoming.statusCode,
              headers: incoming.headers,
              json: () => JSON.parse(body),
            });
          });
        },
      );
      outgoing.on("error", reject);
      if (options.body !== undefined) outgoing.write(options.body);
      outgoing.end();
    });
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

test("financial HTTP mutation routes fail closed before parsing or forwarding", async () => {
  let calls = 0;
  const paths = [
    "/api/invoice-intents?tenant_id=tenant-a",
    "/api/credits?tenant_id=tenant-b",
  ];

  for (const path of paths) {
    const response = await request(
      createZWalletServer({
        env,
        fetchImpl: async () => {
          calls += 1;
          return Response.json({});
        },
      }),
      path,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: "not-json",
      },
    );

    assert.equal(response.status, 503);
    assert.deepEqual(await response.json(), {
      error: "Financial mutations disabled pending tenant-bound authorization and durable idempotency",
    });
    assert.equal(response.headers.get("cache-control"), "no-store");
  }

  assert.equal(calls, 0);
});

test("adapter rejects absolute-form request targets before financial mutation routing", async () => {
  let calls = 0;
  const response = await requestRawTarget(
    createZWalletServer({
      env,
      fetchImpl: async () => {
        calls += 1;
        return Response.json({});
      },
    }),
    "http://attacker.example/api/credits",
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: "not-json",
    },
  );

  assert.equal(response.status, 400);
  assert.deepEqual(response.json(), { error: "Invalid request target" });
  assert.equal(response.headers["cache-control"], "no-store");
  assert.equal(calls, 0);
});
