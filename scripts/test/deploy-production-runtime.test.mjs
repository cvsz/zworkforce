import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

const workflow = await readFile(".github/workflows/deploy-production.yml", "utf8");
const attributes = await readFile(".gitattributes", "utf8");

test("shell scripts are always checked out with LF line endings", () => {
  assert.match(attributes, /^\*\.sh text eol=lf$/m);
  assert.match(attributes, /^\*\.bash text eol=lf$/m);
});

test("production deploy repairs stale self-hosted CRLF files before executing the GHCR helper", () => {
  const repairIndex = workflow.indexOf("Repair and verify shell helper checkout");
  const resolveIndex = workflow.indexOf("Resolve GHCR credential pair");
  assert.ok(repairIndex >= 0);
  assert.ok(resolveIndex > repairIndex);
  assert.match(workflow, /git -c core\.autocrlf=false checkout-index --force/);
  assert.match(workflow, /git hash-object --no-filters/);
  assert.match(workflow, /git rev-parse "HEAD:\$helper"/);
  assert.match(workflow, /bash -n "\$helper"/);
});

test("production deploy requires distinct Phase 6 runtime provider JSON secrets", () => {
  assert.match(workflow, /PHASE6_AI_PROVIDER_ENDPOINTS_JSON: \$\{\{ secrets\.PHASE6_AI_PROVIDER_ENDPOINTS_JSON \}\}/);
  assert.match(workflow, /PHASE6_AI_PROVIDER_KEYS_JSON: \$\{\{ secrets\.PHASE6_AI_PROVIDER_KEYS_JSON \}\}/);
  assert.match(workflow, /AI endpoint and key provider names must match exactly/);
  assert.match(workflow, /AI providers must use distinct origins/);
  assert.match(workflow, /typeof provider\.model !== "string"/);
  assert.doesNotMatch(workflow, /AI_PROVIDER_ENDPOINTS="\$\{AI_PROVIDER_ENDPOINTS:-\{\}\}"/);
});
