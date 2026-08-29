import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

test("Cloudflare service-token policies use deterministic unique precedences", async () => {
  const source = await readFile("infrastructure/terraform/cloudflare/free-access.tf", "utf8");
  assert.match(source, /for index, token_id in var\.free_access_service_token_ids/);
  assert.match(source, /precedence\s*=\s*10 \+ index/);
  assert.match(source, /index == 0 \? .* service auth.* : .* service auth \$\{index \+ 1\}/);
});
