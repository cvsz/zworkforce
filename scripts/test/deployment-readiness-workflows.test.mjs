import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { fileURLToPath } from "node:url";
import test from "node:test";

const workflows = await Promise.all([
  readFile(fileURLToPath(new URL("../../.github/workflows/validate-release-evidence.yml", import.meta.url)), "utf8"),
  readFile(fileURLToPath(new URL("../../.github/workflows/phase6-external-suite.yml", import.meta.url)), "utf8"),
  readFile(fileURLToPath(new URL("../../.github/workflows/external-staging-readiness.yml", import.meta.url)), "utf8"),
  readFile(fileURLToPath(new URL("../../.github/workflows/final-release-readiness.yml", import.meta.url)), "utf8"),
]);

for (const [name, workflow] of [
  ["phase6-external-suite", workflows[1]],
  ["external-staging-readiness", workflows[2]],
  ["final-release-readiness", workflows[3]],
]) {
  test(`${name} validates release SHA existence before checkout`, () => {
    const verifyIndex = workflow.indexOf("Verify release SHA exists in repository");
    const checkoutIndex = workflow.indexOf("actions/checkout@v7");
    assert.ok(verifyIndex >= 0);
    assert.ok(checkoutIndex > verifyIndex);
    assert.match(workflow, /https:\/\/api\.github\.com\/repos\/\$\{GITHUB_REPOSITORY\}\/commits\/\$\{RELEASE_SHA\}/);
    assert.match(workflow, /release_sha must reference a commit in \$\{GITHUB_REPOSITORY\}/);
  });
}

test("validate-release-evidence workflow validates the staging decision record contract", () => {
  assert.match(workflows[0], /validate-staging-decision-record\.mjs/);
  assert.match(workflows[0], /scripts\/staging-decision-record\.json/);
  assert.match(workflows[0], /Check staging-decision-record releaseSha/);
  assert.match(workflows[0], /validate-phase-6-operator-inputs\.mjs/);
  assert.match(workflows[0], /scripts\/phase-6-operator-inputs\.json/);
});

for (const [name, workflow] of [
  ["phase6-external-suite", workflows[1]],
  ["final-release-readiness", workflows[3]],
]) {
  test(`${name} captures sanitized browser evidence from the deployed release`, () => {
    assert.match(workflow, /capture-zchat-browser-evidence\.mjs/);
    assert.match(workflow, /phase6-browser-evidence-|final-browser-evidence-/);
    assert.match(workflow, /runtimeReleaseVerified/);
    assert.doesNotMatch(workflow, /BROWSER_BUNDLE_BASE64|BROWSER_HAR_BASE64/);
  });
}
