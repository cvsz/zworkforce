import assert from "node:assert/strict";
import test from "node:test";
import { createBillingLedgerServer } from "../server.mjs";

const token = "synthetic-test-token";
const env = { Z_PLATFORM_SERVICE_TOKEN: token };

async function request(server, path, authorization) {
  await new Promise((resolve) => server.listen(0, "127.0.0.1", resolve));
  try {
    const headers = authorization === undefined ? {} : { Authorization: authorization };
    const response = await fetch(`http://127.0.0.1:${server.address().port}${path}`, {
      method: "POST", headers, body: "{}",
    });
    return { status: response.status, cacheControl: response.headers.get("cache-control") };
  } finally {
    await new Promise((resolve, reject) => server.close((error) => error ? reject(error) : resolve()));
  }
}

for (const authorization of [
  token,
  `Basic ${token}`,
  `Token ${token}`,
  `Bearer\t${token}`,
  `Bearer ${token} extra`,
  "Bearer",
]) {
  test(`rejects non-canonical Authorization header ${JSON.stringify(authorization)}`, async () => {
    const ledger = new Proxy({}, { get() { throw new Error("ledger must not be invoked"); } });
    const result = await request(createBillingLedgerServer({ env, ledger }), "/v1/usage", authorization);
    assert.equal(result.status, 401);
  });
}

for (const authorization of [`Bearer ${token}`, `bearer ${token}`, `Bearer  ${token}`]) {
  test(`valid Bearer scheme remains authenticated: ${JSON.stringify(authorization)}`, async () => {
    const ledger = new Proxy({}, { get() { throw new Error("ledger must not be invoked"); } });
    const result = await request(createBillingLedgerServer({ env, ledger }), "/v1/usage", authorization);
    assert.equal(result.status, 503);
    assert.equal(result.cacheControl, "no-store");
  });
}

test("missing service token fails closed", async () => {
  const result = await request(createBillingLedgerServer({ env: {} }), "/v1/usage", `Bearer ${token}`);
  assert.equal(result.status, 401);
});

test("missing Authorization header fails closed", async () => {
  const result = await request(createBillingLedgerServer({ env }), "/v1/usage", undefined);
  assert.equal(result.status, 401);
});
