import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

const stagingReadiness = await readFile(new URL("../../docs/operations/staging-readiness.md", import.meta.url), "utf8");
const evidenceMatrix = await readFile(new URL("../../docs/operations/phase-6-evidence-matrix.md", import.meta.url), "utf8");
const githubEnvironments = await readFile(new URL("../../docs/operations/github-environments.md", import.meta.url), "utf8");

test("current-head docs use immutable SHA annotations without claiming cross-release evidence", () => {
  assert.match(stagingReadiness, /Current remote-tracking `main` SHA: `[0-9a-f]{40}`/);
  assert.match(stagingReadiness, /Evidence rows below remain bound to their explicitly named earlier SHAs/);
  assert.match(evidenceMatrix, /Current remote-tracking `main` \(`[0-9a-f]{40}`\)/);
  assert.match(evidenceMatrix, /release-specific external evidence has not been refreshed for this SHA/);
});

test("operator environment docs cover the staged review fields", () => {
  for (const marker of [
    "STAGING_REVIEWER",
    "INCIDENT_OWNER",
    "ESCALATION_ROUTE",
    "WATCH_WINDOW",
    "PRODUCTION_REVIEWER",
    "PRODUCTION_APPROVER",
  ]) {
    assert.match(githubEnvironments, new RegExp(marker));
    assert.match(stagingReadiness, new RegExp(marker));
    assert.match(evidenceMatrix, new RegExp(marker));
  }
});
