import assert from "node:assert/strict";
import test from "node:test";
import { BillingLedger, BillingLedgerError } from "../server.mjs";

const base = {
  tenant_id: "tenant-a",
  usage_id: "usage-a",
  idempotency_key: "request-a",
  model: "test:model",
  input_tokens: 1,
  output_tokens: 2,
};

const invalid = [
  Number.NaN, Number.POSITIVE_INFINITY, Number.NEGATIVE_INFINITY,
  "NaN", "Infinity", 1.5, "1.5", Number.MAX_SAFE_INTEGER + 1,
  -1,
];

test("rejects invalid usage token counts before mutating the store", async () => {
  for (const field of ["input_tokens", "output_tokens"]) {
    for (const value of invalid) {
      const ledger = new BillingLedger({ now: () => "2026-10-23T00:00:00.000Z" });
      await assert.rejects(
        ledger.recordUsage({ ...base, [field]: value }),
        (error) => error instanceof BillingLedgerError && error.status === 400,
        `${field}=${String(value)}`,
      );
      assert.equal(ledger.store.records.size, 0);
      assert.equal(ledger.store.usageIdentity.size, 0);
    }
  }
});

test("accepts zero and safe integral usage counts without changing valid contracts", async () => {
  const ledger = new BillingLedger({ now: () => "2026-10-23T00:00:00.000Z" });
  const first = await ledger.recordUsage({
    ...base, input_tokens: "0", output_tokens: String(Number.MAX_SAFE_INTEGER),
  });
  assert.equal(first.duplicate, false);
  assert.equal(first.record.input_tokens, 0);
  assert.equal(first.record.output_tokens, Number.MAX_SAFE_INTEGER);
  const replay = await ledger.recordUsage({ ...base, input_tokens: 0, output_tokens: Number.MAX_SAFE_INTEGER });
  assert.equal(replay.duplicate, true);
  assert.equal(ledger.store.records.size, 1);
});

test("rejects invalid replay token counts before returning a duplicate", async () => {
  const ledger = new BillingLedger();
  await ledger.recordUsage(base);
  await assert.rejects(
    ledger.recordUsage({ ...base, output_tokens: Number.POSITIVE_INFINITY }),
    (error) => error instanceof BillingLedgerError && error.status === 400,
  );
  assert.equal(ledger.store.records.size, 1);
  assert.equal(ledger.store.usageIdentity.size, 1);
});
