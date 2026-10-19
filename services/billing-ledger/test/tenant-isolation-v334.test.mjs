import assert from "node:assert/strict";
import test from "node:test";
import { BillingLedger } from "../server.mjs";

test("same usage idempotency key is tenant-scoped", async () => {
  const ledger = new BillingLedger({ now: () => "2026-10-20T00:00:00Z" });
  const usage = (tenant_id) => ({ tenant_id, usage_id: "usage-1", idempotency_key: "shared-key", model: "test", input_tokens: 1, output_tokens: 2 });
  assert.equal((await ledger.recordUsage(usage("tenant-A"))).duplicate, false);
  const result = await ledger.recordUsage(usage("tenant-B"));
  assert.equal(result.duplicate, false);
  assert.equal(result.record.tenant_id, "tenant-B");
});
