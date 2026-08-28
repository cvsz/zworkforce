import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { fileURLToPath } from "node:url";
import test from "node:test";

const ciWorkflowPath = fileURLToPath(new URL("../../.github/workflows/ci.yml", import.meta.url));
const validateWorkflowPath = fileURLToPath(new URL("../../.github/workflows/validate.yml", import.meta.url));

const [ciWorkflow, validateWorkflow] = await Promise.all([
  readFile(ciWorkflowPath, "utf8"),
  readFile(validateWorkflowPath, "utf8"),
]);

for (const [name, workflow, checkoutMajor] of [
  ["ci", ciWorkflow, 7],
  ["validate", validateWorkflow, 7],
]) {
  test(`${name} workflow installs pnpm before running package-manager commands`, () => {
    assert.match(workflow, new RegExp(`uses:\\s*actions/checkout@v${checkoutMajor}`));
    assert.match(workflow, /uses:\s*actions\/setup-node@v7/);
    assert.match(workflow, /uses:\s*pnpm\/action-setup@[0-9a-f]{40}\s*# v6\.0\.10/);
    assert.match(workflow, /version:\s*11\.4\.0/);
    assert.match(workflow, /node-version:\s*24/);
    assert.match(workflow, /package-manager-cache:\s*false/);
    assert.match(workflow, /run:\s*pnpm install --ignore-scripts/);
  });
}
