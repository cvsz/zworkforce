import assert from "node:assert/strict";
import test from "node:test";
import { createBillingLedgerServer } from "../server.mjs";

const token = "local-test-token";
const env = { Z_PLATFORM_SERVICE_TOKEN: token };
const routes = ["/v1/usage", "/v1/credits", "/v1/invoice-intents"];

async function request(server, path, options = {}) {
  await new Promise((resolve) => server.listen(0, "127.0.0.1", resolve));
  try {
    const response = await fetch(`http://127.0.0.1:${server.address().port}${path}`, options);
    return { status: response.status, cacheControl: response.headers.get("cache-control"), body: await response.json() };
  } finally {
    await new Promise((resolve, reject) => server.close(error => error ? reject(error) : resolve()));
  }
}

for (const path of routes) {
  test(`authenticated ${path} returns 503 without calling ledger`, async () => {
    const ledger = new Proxy({}, { get() { throw new Error("Financial mutation executed"); } });
    const result = await request(createBillingLedgerServer({ env, ledger }), path, {
      method: "POST",
      headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json" },
      body: JSON.stringify({ tenant_id: "attacker-controlled", amount_minor: 123 }),
    });
    assert.equal(result.status, 503);
    assert.equal(result.cacheControl, "no-store");
    assert.match(result.body.error, /disabled/);
  });

  test(`authenticated ${path} rejects malformed JSON without parsing or mutation`, async () => {
    const ledger = new Proxy({}, { get() { throw new Error("Financial mutation executed"); } });
    const result = await request(createBillingLedgerServer({ env, ledger }), path, {
      method: "POST",
      headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json" },
      body: "{not-json",
    });
    assert.equal(result.status, 503);
  });

  test(`unauthenticated ${path} remains 401`, async () => {
    const result = await request(createBillingLedgerServer({ env }), path, {
      method: "POST", body: "{}",
    });
    assert.equal(result.status, 401);
  });
}

test("health remains available without a token", async () => {
  const result = await request(createBillingLedgerServer({ env }), "/health");
  assert.equal(result.status, 200);
  assert.equal(result.body.wallet_authority, false);
});

test("unrecognized authenticated route remains 404", async () => {
  const result = await request(createBillingLedgerServer({ env }), "/v1/unknown", {
    method: "POST", headers: { Authorization: `Bearer ${token}` }, body: "{}",
  });
  assert.equal(result.status, 404);
});
