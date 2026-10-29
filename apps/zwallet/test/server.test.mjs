import assert from "node:assert/strict";
import { createHash, createHmac } from "node:crypto";
import { createServer } from "node:http";
import test from "node:test";

import { createInvoiceIntent, createZWalletServer } from "../server.mjs";

const env = {
  Z_PLATFORM_BILLING_LEDGER_URL: "http://ledger",
  Z_PLATFORM_SERVICE_TOKEN: "service-token",
  Z_PLATFORM_BILLING_ADAPTER_ENABLE_MUTATIONS: "true",
  Z_PLATFORM_TENANT_ASSERTION_SECRET: "synthetic-tenant-assertion-secret-with-32-bytes-minimum",
};

function tenantAssertionHeaders(input, path, signingEnv = env, nowMs = Date.now(), rawBody = JSON.stringify(input)) {
  const timestamp = String(Math.floor(nowMs / 1000));
  const bodySha256 = createHash("sha256").update(rawBody).digest("hex");
  const canonical = [input.tenant_id, timestamp, "POST", path, input.idempotency_key, bodySha256].join("\n");
  return {
    "X-Authenticated-Tenant": input.tenant_id,
    "X-Tenant-Assertion-Timestamp": timestamp,
    "X-Tenant-Assertion-Signature": createHmac("sha256", signingEnv.Z_PLATFORM_TENANT_ASSERTION_SECRET).update(canonical).digest("hex"),
  };
}

function tenantAssertionRequestContext(input, path, signingEnv = env, nowMs = Date.now(), rawBody = JSON.stringify(input)) {
  return {
    method: "POST",
    headers: Object.fromEntries(Object.entries(tenantAssertionHeaders(input, path, signingEnv, nowMs, rawBody)).map(([name, value]) => [name.toLowerCase(), value])),
    bodySha256: createHash("sha256").update(rawBody).digest("hex"),
  };
}

test("accepts the documented LF-delimited tenant assertion vector", async (t) => {
  const timestamp = "1793232000";
  t.mock.method(Date, "now", () => Number(timestamp) * 1000);
  const input = { tenant_id: "tenant-1", idempotency_key: "invoice-vector", currency: "USD", amount_minor: 500 };
  const requestContext = {
    method: "POST",
    headers: {
      "x-authenticated-tenant": "tenant-1",
      "x-tenant-assertion-timestamp": timestamp,
      "x-tenant-assertion-signature": "d99bbd21ed948b397a8f3e1518001cfe44eaba885e048bf284ec700af924d877",
    },
    bodySha256: "9bce8ca807ffa54b0c617bc3d7f0ac0c9cf8ca4bfda4d2909fa746607e7c0fe1",
  };
  let calls = 0;
  const result = await createInvoiceIntent(input, env, async (_url, options) => {
    calls += 1;
    assert.equal(options.headers["X-Authenticated-Tenant"], "tenant-1");
    return Response.json({ intent_id: "intent-vector" }, { status: 201 });
  }, requestContext);
  assert.deepEqual(result, { intent_id: "intent-vector" });
  assert.equal(calls, 1);
});

async function request(server, path, options = {}) {
  const { omitTenantAssertion = false, ...fetchOptions } = options;
  if (!omitTenantAssertion && fetchOptions.method === "POST" && typeof fetchOptions.body === "string") {
    try {
      const input = JSON.parse(fetchOptions.body);
      if (input && typeof input === "object" && !Array.isArray(input) && typeof input.tenant_id === "string" && typeof input.idempotency_key === "string") {
        const headers = new Headers(fetchOptions.headers || {});
        for (const [name, value] of Object.entries(tenantAssertionHeaders(input, path, env, Date.now(), fetchOptions.body))) {
          if (!headers.has(name)) headers.set(name, value);
        }
        fetchOptions.headers = headers;
      }
    } catch {
      // Invalid and oversized payloads are rejected before upstream access.
    }
  }
  await new Promise((resolve) => server.listen(0, "127.0.0.1", resolve));
  const { port } = server.address();
  try {
    return await fetch(`http://127.0.0.1:${port}${path}`, fetchOptions);
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
  const input = { tenant_id: "tenant-1", idempotency_key: "invoice-1", currency: "USD", amount_minor: 500 };
  const result = await createInvoiceIntent(input, env, async (url, options) => {
    calls.push({ url, options });
    return Response.json({ intent_id: "intent-1" }, { status: 201 });
  }, tenantAssertionRequestContext(input, "/api/invoice-intents"));
  assert.deepEqual(result, { intent_id: "intent-1" });
  assert.equal(calls[0].url, "http://ledger/v1/invoice-intents");
  assert.equal(calls[0].options.headers.Authorization, "Bearer service-token");
  assert.equal(calls[0].options.headers["X-Authenticated-Tenant"], "tenant-1");
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

test("maps upstream authentication and timeout failures to generic 503 without retrying", async () => {
  for (const status of [401, 403, 408]) {
    let calls = 0;
    const response = await request(
      createZWalletServer({
        env,
        fetchImpl: async () => {
          calls += 1;
          return Response.json({ error: "private upstream diagnostics" }, { status });
        },
      }),
      "/api/invoice-intents",
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          tenant_id: "tenant-1",
          idempotency_key: `invoice-upstream-${status}`,
          currency: "USD",
          amount_minor: 500,
        }),
      },
    );

    assert.equal(response.status, 503);
    assert.deepEqual(await response.json(), { error: "Billing ledger unavailable" });
    assert.equal(response.headers.get("cache-control"), "no-store");
    assert.equal(response.headers.get("retry-after"), null);
    assert.equal(calls, 1);
  }
});

test("native fetch rejects ledger redirects without forwarding the financial request", async () => {
  let forwardedRequests = 0;
  const receiver = createServer((_request, response) => {
    forwardedRequests += 1;
    response.writeHead(200, { "Content-Type": "application/json" });
    response.end("{}");
  });
  const ledger = createServer((_request, response) => {
    const receiverUrl = `http://127.0.0.1:${receiver.address().port}/collect`;
    response.writeHead(302, { Location: receiverUrl });
    response.end();
  });

  await new Promise((resolve) => receiver.listen(0, "127.0.0.1", resolve));
  await new Promise((resolve) => ledger.listen(0, "127.0.0.1", resolve));
  try {
    const localEnv = {
      ...env,
      Z_PLATFORM_BILLING_LEDGER_URL: `http://127.0.0.1:${ledger.address().port}`,
    };
    const response = await request(
      createZWalletServer({ env: localEnv }),
      "/api/invoice-intents",
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ tenant_id: "tenant-1", idempotency_key: "invoice-redirect", currency: "USD", amount_minor: 500 }),
      },
    );

    assert.equal(response.status, 503);
    assert.deepEqual(await response.json(), { error: "Billing ledger unavailable" });
    assert.equal(response.headers.get("cache-control"), "no-store");
    assert.equal(forwardedRequests, 0);
  } finally {
    await Promise.all(
      [ledger, receiver].map(
        (server) =>
          new Promise((resolve, reject) =>
            server.close((error) => (error ? reject(error) : resolve())),
          ),
      ),
    );
  }
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
  const timeoutEnv = { ...env, Z_PLATFORM_BILLING_LEDGER_TIMEOUT_MS: "100" };
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

test("adapter rejects signing, card, KYC, MPC, and swap payloads at every nesting level", async () => {
  const forbiddenPayloads = [
    { wallet_signature: "nope" },
    { metadata: { card_number: "synthetic-card-number" } },
    { details: [{ WalletSignature: "synthetic-signature" }] },
    { envelope: { "kyc-payload": { document: "synthetic" } } },
    { items: [{ mpcShare: "synthetic-share" }] },
    { request: { swap_route: { provider: "synthetic" } } },
  ];
  let calls = 0;

  for (const forbiddenPayload of forbiddenPayloads) {
    await assert.rejects(
      createInvoiceIntent(
        {
          tenant_id: "tenant-1",
          idempotency_key: "invoice-forbidden",
          currency: "USD",
          amount_minor: 500,
          ...forbiddenPayload,
        },
        env,
        async () => {
          calls += 1;
          return Response.json({});
        },
      ),
      /is not accepted by the audited adapter/,
    );
  }

  assert.equal(calls, 0);
});


test("billing mutations are disabled unless the explicit admission gate is enabled", async () => {
  let calls = 0;
  const disabledEnv = { ...env, Z_PLATFORM_BILLING_ADAPTER_ENABLE_MUTATIONS: "false" };
  const response = await request(createZWalletServer({ env: disabledEnv, fetchImpl: async () => { calls += 1; return Response.json({ intent_id: "unexpected" }); } }), "/api/invoice-intents", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ tenant_id: "tenant-1", idempotency_key: "invoice-disabled", currency: "USD", amount_minor: 500 }) });
  assert.equal(response.status, 503);
  assert.deepEqual(await response.json(), { error: "Billing ledger unavailable" });
  assert.equal(response.headers.get("cache-control"), "no-store");
  assert.equal(calls, 0);
});

test("unsigned tenant claims are rejected before any ledger request", async () => {
  let calls = 0;
  const response = await request(createZWalletServer({ env, fetchImpl: async () => { calls += 1; return Response.json({ intent_id: "unexpected" }); } }), "/api/invoice-intents", { method: "POST", omitTenantAssertion: true, headers: { "Content-Type": "application/json" }, body: JSON.stringify({ tenant_id: "tenant-1", idempotency_key: "invoice-unsigned", currency: "USD", amount_minor: 500 }) });
  assert.equal(response.status, 403);
  assert.deepEqual(await response.json(), { error: "Tenant authorization failed" });
  assert.equal(calls, 0);
});

test("tenant assertions must match the payload tenant and exact route", async () => {
  const input = { tenant_id: "tenant-1", idempotency_key: "invoice-mismatch", currency: "USD", amount_minor: 500 };
  let calls = 0;
  const mismatched = await request(createZWalletServer({ env, fetchImpl: async () => { calls += 1; return Response.json({}); } }), "/api/invoice-intents", { method: "POST", omitTenantAssertion: true, headers: { "Content-Type": "application/json", ...tenantAssertionHeaders({ ...input, tenant_id: "tenant-2" }, "/api/invoice-intents") }, body: JSON.stringify(input) });
  assert.equal(mismatched.status, 403);
  const wrongRoute = await request(createZWalletServer({ env, fetchImpl: async () => { calls += 1; return Response.json({}); } }), "/api/invoice-intents", { method: "POST", omitTenantAssertion: true, headers: { "Content-Type": "application/json", ...tenantAssertionHeaders(input, "/api/credits") }, body: JSON.stringify(input) });
  assert.equal(wrongRoute.status, 403);
  assert.equal(calls, 0);
});

test("tenant admission rejects ASCII control characters in tenant IDs and idempotency keys", async () => {
  let upstreamCalls = 0;
  const cases = [
    {
      input: { tenant_id: "tenant-\u0001", idempotency_key: "invoice-control-tenant", currency: "USD", amount_minor: 500 },
      expected: /tenant_id is required/,
    },
    {
      input: { tenant_id: "tenant-1", idempotency_key: "invoice-\u007f", currency: "USD", amount_minor: 500 },
      expected: /idempotency_key is required/,
    },
  ];

  for (const { input, expected } of cases) {
    const context = tenantAssertionRequestContext(input, "/api/invoice-intents");
    await assert.rejects(
      createInvoiceIntent(input, env, async () => {
        upstreamCalls += 1;
        return Response.json({ intent_id: "unexpected" });
      }, context),
      expected,
    );
  }
  assert.equal(upstreamCalls, 0);
});

test("stale and tampered tenant assertions are rejected", async () => {
  const input = { tenant_id: "tenant-1", idempotency_key: "invoice-stale", currency: "USD", amount_minor: 500 };
  let calls = 0;
  const stale = tenantAssertionHeaders(input, "/api/invoice-intents", env, Date.now() - 120000);
  const staleResponse = await request(createZWalletServer({ env, fetchImpl: async () => { calls += 1; return Response.json({}); } }), "/api/invoice-intents", { method: "POST", omitTenantAssertion: true, headers: { "Content-Type": "application/json", ...stale }, body: JSON.stringify(input) });
  assert.equal(staleResponse.status, 403);
  const tampered = tenantAssertionHeaders(input, "/api/invoice-intents");
  tampered["X-Tenant-Assertion-Signature"] = "0".repeat(64);
  const tamperedResponse = await request(createZWalletServer({ env, fetchImpl: async () => { calls += 1; return Response.json({}); } }), "/api/invoice-intents", { method: "POST", omitTenantAssertion: true, headers: { "Content-Type": "application/json", ...tampered }, body: JSON.stringify(input) });
  assert.equal(tamperedResponse.status, 403);
  assert.equal(calls, 0);
});

test("tenant assertion rejects a changed body even when tenant, path, timestamp and idempotency key are unchanged", async () => {
  let upstreamCalls = 0;
  const original = { tenant_id: "tenant-1", idempotency_key: "invoice-body-bound", currency: "USD", amount_minor: 500 };
  const originalBody = JSON.stringify(original);
  const signedHeaders = tenantAssertionHeaders(original, "/api/invoice-intents", env, Date.now(), originalBody);
  const changed = { ...original, amount_minor: 5000 };
  const response = await request(
    createZWalletServer({ env, fetchImpl: async () => {
      upstreamCalls += 1;
      return Response.json({ intent_id: "should-not-exist" }, { status: 201 });
    } }),
    "/api/invoice-intents",
    {
      method: "POST",
      headers: { "Content-Type": "application/json", ...signedHeaders },
      body: JSON.stringify(changed),
      omitTenantAssertion: true,
    },
  );
  assert.equal(response.status, 403);
  assert.deepEqual(await response.json(), { error: "Tenant authorization failed" });
  assert.equal(upstreamCalls, 0);
});

test("tenant assertion binds HTTP method and idempotency key", async () => {
  let upstreamCalls = 0;
  const input = { tenant_id: "tenant-1", idempotency_key: "invoice-bound-key", currency: "USD", amount_minor: 500 };
  const context = tenantAssertionRequestContext(input, "/api/invoice-intents");
  const fetchImpl = async () => {
    upstreamCalls += 1;
    return Response.json({ intent_id: "unexpected" }, { status: 201 });
  };

  await assert.rejects(
    createInvoiceIntent(input, env, fetchImpl, { ...context, method: "PUT" }),
    /Tenant authorization failed/,
  );
  await assert.rejects(
    createInvoiceIntent({ ...input, idempotency_key: "invoice-substituted-key" }, env, fetchImpl, context),
    /Tenant authorization failed/,
  );
  assert.equal(upstreamCalls, 0);
});

test("missing or weak tenant assertion secret fails closed", async () => {
  for (const secret of [undefined, "weak"]) {
    let calls = 0;
    const misconfiguredEnv = { ...env, Z_PLATFORM_TENANT_ASSERTION_SECRET: secret };
    const response = await request(createZWalletServer({ env: misconfiguredEnv, fetchImpl: async () => { calls += 1; return Response.json({ intent_id: "unexpected" }); } }), "/api/invoice-intents", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ tenant_id: "tenant-1", idempotency_key: "invoice-weak-secret-" + String(secret), currency: "USD", amount_minor: 500 }) });
    assert.equal(response.status, 503);
    assert.deepEqual(await response.json(), { error: "Billing ledger unavailable" });
    assert.equal(calls, 0);
  }
});
