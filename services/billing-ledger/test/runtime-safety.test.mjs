import assert from "node:assert/strict";
import test from "node:test";

import { BillingLedger, createBillingLedgerServer } from "../server.mjs";
import { PostgresLedgerStore } from "../postgres-store.mjs";

const serviceToken = "synthetic-service-token";
const headers = {
  Authorization: `Bearer ${serviceToken}`,
  "Content-Type": "application/json",
};
const enabledEnv = {
  NODE_ENV: "production",
  Z_PLATFORM_SERVICE_TOKEN: serviceToken,
  Z_BILLING_LEDGER_ENABLE_MUTATIONS: "true",
  Z_BILLING_LEDGER_TENANT_AUTHZ_MODE: "trusted-gateway",
};

async function request(server, path, options = {}) {
  await new Promise((resolve) => server.listen(0, "127.0.0.1", resolve));
  const { port } = server.address();
  try {
    return await fetch(`http://127.0.0.1:${port}${path}`, options);
  } finally {
    await new Promise((resolve, reject) => server.close((error) => error ? reject(error) : resolve()));
  }
}

function durableStore() {
  const calls = { usage: 0, invoices: 0, credits: 0 };
  return {
    durable: true,
    calls,
    async assertReady() { return true; },
    async recordUsage(record) {
      calls.usage += 1;
      return { duplicate: false, record };
    },
    async createInvoiceIntent(intent) {
      calls.invoices += 1;
      return intent;
    },
    async setCredits() {
      calls.credits += 1;
      return { tenant_id: "tenant-1", credits: 100 };
    },
  };
}

test("readiness distinguishes process liveness from durable database readiness", async () => {
  const notReady = await request(
    createBillingLedgerServer({ env: enabledEnv, ledger: new BillingLedger() }),
    "/ready",
  );
  assert.equal(notReady.status, 503);
  assert.deepEqual(await notReady.json(), {
    status: "not_ready",
    reason: "durable storage unavailable",
  });

  const readyStore = durableStore();
  const ready = await request(
    createBillingLedgerServer({ env: enabledEnv, ledger: new BillingLedger({ store: readyStore }) }),
    "/ready",
  );
  assert.equal(ready.status, 200);
  assert.deepEqual(await ready.json(), {
    status: "ready",
    service: "billing-ledger",
    persistence: "postgresql",
  });
});

test("durable mutations require a trusted tenant assertion that matches the payload", async () => {
  const store = durableStore();
  const server = createBillingLedgerServer({
    env: enabledEnv,
    ledger: new BillingLedger({ store }),
  });
  const body = {
    tenant_id: "tenant-1",
    usage_id: "synthetic-usage",
    idempotency_key: "synthetic-idempotency",
    model: "test:model",
    input_tokens: 1,
    output_tokens: 2,
  };

  const missingAssertion = await request(server, "/v1/usage", {
    method: "POST",
    headers,
    body: JSON.stringify(body),
  });
  assert.equal(missingAssertion.status, 403);
  assert.equal(store.calls.usage, 0);

  const mismatch = await request(server, "/v1/usage", {
    method: "POST",
    headers: { ...headers, "X-Authenticated-Tenant": "tenant-2" },
    body: JSON.stringify(body),
  });
  assert.equal(mismatch.status, 403);
  assert.equal(store.calls.usage, 0);

  const allowed = await request(server, "/v1/usage", {
    method: "POST",
    headers: { ...headers, "X-Authenticated-Tenant": "tenant-1" },
    body: JSON.stringify(body),
  });
  assert.equal(allowed.status, 201);
  assert.equal(store.calls.usage, 1);
});

test("durable credit setter remains disabled even when the generic write gate is enabled", async () => {
  const store = durableStore();
  const response = await request(
    createBillingLedgerServer({ env: enabledEnv, ledger: new BillingLedger({ store }) }),
    "/v1/credits",
    {
      method: "POST",
      headers: { ...headers, "X-Authenticated-Tenant": "tenant-1" },
      body: JSON.stringify({ tenant_id: "tenant-1", credits: 100 }),
    },
  );

  assert.equal(response.status, 503);
  assert.deepEqual(await response.json(), {
    error: "Credit mutations are disabled pending an append-only audited adjustment contract",
  });
  assert.equal(store.calls.credits, 0);
});

test("invoice intent validates currency and safe integer amounts before store calls", async () => {
  const store = durableStore();
  const ledger = new BillingLedger({ store, idGenerator: () => "synthetic-intent" });
  await assert.rejects(
    ledger.createInvoiceIntent({
      tenant_id: "tenant-1",
      idempotency_key: "bad-currency",
      currency: "USDD",
      amount_minor: 100,
    }),
    (error) => error.status === 400,
  );
  await assert.rejects(
    ledger.createInvoiceIntent({
      tenant_id: "tenant-1",
      idempotency_key: "unsafe-amount",
      currency: "USD",
      amount_minor: Number.MAX_SAFE_INTEGER + 1,
    }),
    (error) => error.status === 400,
  );
  await assert.rejects(
    ledger.createInvoiceIntent({
      tenant_id: "tenant-1",
      idempotency_key: "string-amount",
      currency: "USD",
      amount_minor: "100",
    }),
    (error) => error.status === 400,
  );
  assert.equal(store.calls.invoices, 0);
});

test("PostgreSQL readiness rechecks database connectivity instead of caching a stale success", async () => {
  let online = true;
  let probes = 0;
  const pool = {
    async query() {
      probes += 1;
      if (!online) throw new Error("synthetic database outage");
      return { rows: [{ version: 1 }] };
    },
  };
  const store = new PostgresLedgerStore({ pool });

  assert.equal(await store.assertReady(), true);
  online = false;
  await assert.rejects(store.assertReady(), (error) => error.status === 503);
  assert.equal(probes, 2);
});
