import assert from "node:assert/strict";
import test from "node:test";

import { buildConfig } from "../generate-phase6-external-config.mjs";

const releaseSha = "a".repeat(40);
const evidence = {
  "observability.traces": { status: "verified", reviewer: "cvsz", reviewedAt: "2026-07-19T00:00:00Z", evidenceRef: "github-actions:run-1/trace-evidence" },
  "zchat.keyboard": { status: "verified", reviewer: "cvsz", reviewedAt: "2026-07-19T00:00:00Z", evidenceRef: "qa-report:keyboard-1", notes: "All interactive controls were completed using keyboard navigation." },
  "zchat.screen_reader": { status: "verified", reviewer: "cvsz", reviewedAt: "2026-07-19T00:00:00Z", evidenceRef: "qa-report:screen-reader-1", notes: "Headings, labels, messages, and live status updates were announced correctly." },
  "zchat.responsive": { status: "verified", reviewer: "cvsz", reviewedAt: "2026-07-19T00:00:00Z", evidenceRef: "qa-report:responsive-1", notes: "Target mobile, tablet, and desktop viewport workflows completed successfully." },
};

test("builds a release-bound config with real machine checks", () => {
  const config = buildConfig(releaseSha, evidence);
  assert.equal(config.releaseSha, releaseSha);
  assert.equal(config.checks.length, 14);
  assert.deepEqual(config.checks.filter((check) => check.mode === "attestation").map((check) => check.id), ["observability.traces"]);
  assert.deepEqual(config.checks.filter((check) => check.mode === "human").map((check) => check.id), ["zchat.keyboard", "zchat.screen_reader", "zchat.responsive"]);
  assert.equal(config.checks.find((check) => check.id === "backup.external_restore").command, "bash scripts/backup/external-supabase-restore.sh run");
  assert.equal(config.checks.find((check) => check.id === "ai.upload").command, "node scripts/verify-phase6-external.mjs upload");
});

test("rejects placeholder or incomplete human evidence", () => {
  assert.throws(() => buildConfig(releaseSha, { ...evidence, "zchat.keyboard": { ...evidence["zchat.keyboard"], evidenceRef: "pending:keyboard" } }), /real evidenceRef/);
  assert.throws(() => buildConfig("short", evidence), /full lowercase SHA/);
});
