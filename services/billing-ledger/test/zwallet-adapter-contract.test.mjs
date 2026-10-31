import assert from "node:assert/strict";
import { createHash, createHmac } from "node:crypto";
import { resolve } from "node:path";
import { pathToFileURL } from "node:url";
import test from "node:test";

import { BillingLedger, createBillingLedgerServer } from "../server.mjs";

const adapterPath = process.env.ZWALLET_ADAPTER_PATH;

class ContractStore {
  durable = true;
  invoiceIntents = new Map();
  invoiceIntentFingerprints = new Map();
  creditsCalls = 0;

  async assertReady() {}

  async createInvoiceIntent(intent) {
    const key = JSON.stringify([intent.tenant_id, intent.idempotency_key]);
    const fingerprint = JSON.stringify(
      Object.fromEntries(
        Object.entries(intent)
          .filter(([field]) => !["intent_id", "created_at"].includes(field))
          .sort(([left], [right]) => left.localeCompare(right)),
      ),
    );
    const existing = this.invoiceIntents.get(key);
    if (existing) {
      if (this.invoiceIntentFingerprints.get(key) !== fingerprint) {
        const error = new Error("Idempotency key conflicts with an existing request");
        error.status = 409;
        error.publicMessage = error.message;
        throw error;
      }
      return structuredClone(existing);
    }
    this.invoiceIntents.set(key, structuredClone(intent));
    this.invoiceIntentFingerprints.set(key, fingerprint);
    return structuredClone(intent);
  }

  async recordUsage(record) {
    return { duplicate: false, record: structuredClone(record) };
  }

  async setCredits() {
    this.creditsCalls += 1;
    throw new Error("credit setter must remain disabled");
  }
}

function listen(server) {
  return new Promise((resolveListen, reject) => {
    server.once("error", reject);
    server.listen(0, "127.0.0.1", () => {
      const address = server.address();
      resolveListen(`http://127.0.0.1:${address.port}`);
    });
  });
}

function close(server) {
  if (!server || !server.listening) return Promise.resolve();
  return new Promise((resolveClose, reject) => {
    server.close((error) => (error ? reject(error) : resolveClose()));
  });
}

function assertionHeaders(body, secret, { tenantHeader, timestamp } = {}) {
  const input = JSON.parse(body);
  const issuedAt = timestamp ?? String(Math.floor(Date.now() / 1000));
  const bodyDigest = createHash("sha256").update(body, "utf8").digest("hex");
  const canonical = [
    input.tenant_id,
    issuedAt,
    "POST",
    "/api/invoice-intents",
    input.idempotency_key,
    bodyDigest,
  ].join("\n");
  const signature = createHmac("sha256", secret).update(canonical, "utf8").digest("hex");

  return {
    "Content-Type": "application/json",
    "X-Authenticated-Tenant": tenantHeader ?? input.tenant_id,
    "X-Tenant-Assertion-Timestamp": issuedAt,
    "X-Tenant-Assertion-Signature": signature,
  };
}

test(
  "ZWallet signed tenant admission composes with Billing Ledger trusted-gateway authorization",
  { skip: adapterPath ? false : "Set ZWALLET_ADAPTER_PATH to the pinned adapter candidate for cross-service verification." },
  async (t) => {
    const { createZWalletServer } = await import(pathToFileURL(resolve(adapterPath)).href);
    const serviceToken = "synthetic-integration-service-token";
    const assertionSecret = "synthetic-integration-tenant-assertion-secret-32-bytes-minimum";
    const ledgerEnv = {
      NODE_ENV: "test",
      Z_PLATFORM_BILLING_LEDGER_SERVICE_TOKEN: serviceToken,
      Z_BILLING_LEDGER_ENABLE_MUTATIONS: "true",
      Z_BILLING_LEDGER_TENANT_AUTHZ_MODE: "trusted-gateway",
    };
    const store = new ContractStore();
    const ledger = new BillingLedger({
      store,
      idGenerator: (() => {
        let nextIntent = 0;
        return () => `intent-cross-service-${++nextIntent}`;
      })(),
      now: () => "2026-10-30T00:00:00.000Z",
    });
    const ledgerServer = createBillingLedgerServer({
      env: ledgerEnv,
      ledger,
      allowEphemeralStore: false,
    });

    let ledgerUrl;
    let adapterServer;
    try {
      ledgerUrl = await listen(ledgerServer);
      adapterServer = createZWalletServer({
        env: {
          NODE_ENV: "test",
          Z_PLATFORM_BILLING_LEDGER_URL: ledgerUrl,
          Z_PLATFORM_BILLING_LEDGER_SERVICE_TOKEN: serviceToken,
          Z_PLATFORM_BILLING_ADAPTER_ENABLE_MUTATIONS: "true",
          Z_PLATFORM_TENANT_ASSERTION_SECRET: assertionSecret,
        },
      });
      const adapterUrl = await listen(adapterServer);
      t.after(async () => {
        await Promise.all([close(adapterServer), close(ledgerServer)]);
      });

      const input = {
        tenant_id: "tenant-alpha",
        idempotency_key: "invoice-cross-service-1",
        currency: "USD",
        amount_minor: 500,
      };
      const body = JSON.stringify(input);

      const accepted = await fetch(`${adapterUrl}/api/invoice-intents`, {
        method: "POST",
        headers: assertionHeaders(body, assertionSecret),
        body,
      });
      assert.equal(accepted.status, 201);
      const acceptedPayload = await accepted.json();
      assert.equal(acceptedPayload.tenant_id, input.tenant_id);
      assert.equal(acceptedPayload.idempotency_key, input.idempotency_key);
      assert.equal(acceptedPayload.status, "requires_payment_processor");
      assert.equal(store.invoiceIntents.size, 1);

      const replay = await fetch(`${adapterUrl}/api/invoice-intents`, {
        method: "POST",
        headers: assertionHeaders(body, assertionSecret),
        body,
      });
      assert.equal(replay.status, 201);
      const replayPayload = await replay.json();
      assert.equal(replayPayload.intent_id, acceptedPayload.intent_id);
      assert.equal(store.invoiceIntents.size, 1, "same-key replay must not create a second intent");

      const conflictInput = { ...input, amount_minor: 501 };
      const conflictBody = JSON.stringify(conflictInput);
      const conflict = await fetch(`${adapterUrl}/api/invoice-intents`, {
        method: "POST",
        headers: assertionHeaders(conflictBody, assertionSecret),
        body: conflictBody,
      });
      assert.equal(conflict.status, 409);
      assert.deepEqual(await conflict.json(), {
        error: "Idempotency key conflicts with an existing request",
      });
      assert.equal(store.invoiceIntents.size, 1, "changed-payload replay must not create or overwrite an intent");

      const forgedTenant = await fetch(`${adapterUrl}/api/invoice-intents`, {
        method: "POST",
        headers: assertionHeaders(body, assertionSecret, { tenantHeader: "tenant-beta" }),
        body,
      });
      assert.equal(forgedTenant.status, 403);
      assert.equal(store.invoiceIntents.size, 1, "forged tenant headers must not reach the ledger");

      const tamperedBody = JSON.stringify({ ...input, amount_minor: 501 });
      const tampered = await fetch(`${adapterUrl}/api/invoice-intents`, {
        method: "POST",
        headers: assertionHeaders(body, assertionSecret),
        body: tamperedBody,
      });
      assert.equal(tampered.status, 403);
      assert.equal(store.invoiceIntents.size, 1, "body tampering must not reach the ledger");

      const missingAssertion = await fetch(`${adapterUrl}/api/invoice-intents`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ ...input, idempotency_key: "invoice-missing-assertion" }),
      });
      assert.equal(missingAssertion.status, 403);
      assert.equal(store.invoiceIntents.size, 1, "missing assertions must not reach the ledger");

      const unsupportedCurrencyInput = {
        ...input,
        idempotency_key: "invoice-unsupported-currency",
        currency: "ZZZ",
      };
      const unsupportedCurrencyBody = JSON.stringify(unsupportedCurrencyInput);
      const unsupportedCurrency = await fetch(`${adapterUrl}/api/invoice-intents`, {
        method: "POST",
        headers: assertionHeaders(unsupportedCurrencyBody, assertionSecret),
        body: unsupportedCurrencyBody,
      });
      assert.equal(unsupportedCurrency.status, 400);
      assert.deepEqual(await unsupportedCurrency.json(), {
        error: "Billing ledger rejected the request",
      });
      assert.equal(store.invoiceIntents.size, 1, "unsupported currency must not reach durable storage");

      const directMissingTenant = await fetch(`${ledgerUrl}/v1/invoice-intents`, {
        method: "POST",
        headers: {
          Authorization: `Bearer ${serviceToken}`,
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ ...input, idempotency_key: "invoice-direct-no-tenant" }),
      });
      assert.equal(directMissingTenant.status, 403);
      assert.equal(store.invoiceIntents.size, 1);

      const directMismatchedTenant = await fetch(`${ledgerUrl}/v1/invoice-intents`, {
        method: "POST",
        headers: {
          Authorization: `Bearer ${serviceToken}`,
          "Content-Type": "application/json",
          "X-Authenticated-Tenant": "tenant-beta",
        },
        body: JSON.stringify({ ...input, idempotency_key: "invoice-direct-mismatch" }),
      });
      assert.equal(directMismatchedTenant.status, 403);
      assert.equal(store.invoiceIntents.size, 1);

      const credits = await fetch(`${adapterUrl}/api/credits`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ tenant_id: "tenant-alpha", credits: 999 }),
      });
      assert.equal(credits.status, 503);
      assert.equal(credits.headers.get("cache-control"), "no-store");
      assert.equal(store.creditsCalls, 0);
      assert.equal(store.invoiceIntents.size, 1);
    } finally {
      await Promise.all([close(adapterServer), close(ledgerServer)]);
    }
  },
);
