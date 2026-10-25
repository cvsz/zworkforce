import assert from "node:assert/strict";
import test from "node:test";
import { request as httpRequest } from "node:http";
import { createBillingLedgerServer } from "../server.mjs";

const token = "local-test-token";
const env = { Z_PLATFORM_SERVICE_TOKEN: token };
const routes = ["/v1/usage", "/v1/credits", "/v1/invoice-intents"];

async function request(server, path, options = {}) {
  await new Promise((resolve) => server.listen(0, "127.0.0.1", resolve));
  try {
    const response = await fetch(`http://127.0.0.1:${server.address().port}${path}`, options);
    return {
      status: response.status,
      cacheControl: response.headers.get("cache-control"),
      body: await response.json(),
    };
  } finally {
    await new Promise((resolve, reject) => server.close((error) => error ? reject(error) : resolve()));
  }
}

for (const path of routes) {
  test(`authenticated ${path} returns 503 without invoking the ledger`, async () => {
    const ledger = new Proxy({}, { get() { throw new Error("Financial mutation executed"); } });
    const result = await request(createBillingLedgerServer({ env, ledger }), path, {
      method: "POST",
      headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json" },
      body: JSON.stringify({ tenant_id: "untrusted-tenant", amount_minor: 123 }),
    });
    assert.equal(result.status, 503);
    assert.equal(result.cacheControl, "no-store");
    assert.match(result.body.error, /disabled/);
  });

  test(`authenticated ${path} with query parameters remains contained`, async () => {
    const ledger = new Proxy({}, { get() { throw new Error("Financial mutation executed"); } });
    const result = await request(createBillingLedgerServer({ env, ledger }), `${path}?probe=1`, {
      method: "POST",
      headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json" },
      body: JSON.stringify({ tenant_id: "untrusted-tenant", amount_minor: 123 }),
    });
    assert.equal(result.status, 503);
    assert.equal(result.cacheControl, "no-store");
    assert.match(result.body.error, /disabled/);
  });

  test(`unauthenticated ${path} remains 401`, async () => {
    const result = await request(createBillingLedgerServer({ env }), path, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: "{}",
    });
    assert.equal(result.status, 401);
  });

  test(`malformed JSON at ${path} is not parsed while containment is active`, async () => {
    const ledger = new Proxy({}, { get() { throw new Error("Financial mutation executed"); } });
    const result = await request(createBillingLedgerServer({ env, ledger }), path, {
      method: "POST",
      headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json" },
      body: "{not-json",
    });
    assert.equal(result.status, 503);
  });
}

test("health remains available without a token", async () => {
  const result = await request(createBillingLedgerServer({ env }), "/health");
  assert.equal(result.status, 200);
  assert.equal(result.body.wallet_authority, false);
});

test("absolute-form request targets are rejected without invoking the ledger", async () => {
  const ledger = new Proxy({}, { get() { throw new Error("Financial mutation executed"); } });
  const server = createBillingLedgerServer({ env, ledger });
  await new Promise((resolve) => server.listen(0, "127.0.0.1", resolve));
  try {
    const body = JSON.stringify({ tenant_id: "untrusted-tenant", amount_minor: 123 });
    const result = await new Promise((resolve, reject) => {
      const req = httpRequest({
        hostname: "127.0.0.1",
        port: server.address().port,
        method: "POST",
        path: "http://evil.example/v1/usage",
        headers: {
          Authorization: `Bearer ${token}`,
          "Content-Type": "application/json",
          "Content-Length": Buffer.byteLength(body),
        },
      }, (response) => {
        let responseBody = "";
        response.setEncoding("utf8");
        response.on("data", (chunk) => { responseBody += chunk; });
        response.on("end", () => resolve({
          status: response.statusCode,
          cacheControl: response.headers["cache-control"],
          body: JSON.parse(responseBody),
        }));
      });
      req.on("error", reject);
      req.end(body);
    });
    assert.equal(result.status, 400);
    assert.equal(result.cacheControl, "no-store");
    assert.match(result.body.error, /invalid request target/i);
  } finally {
    await new Promise((resolve, reject) => server.close((error) => error ? reject(error) : resolve()));
  }
});
