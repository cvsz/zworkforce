#!/usr/bin/env node
import { readFile, writeFile } from "node:fs/promises";

function assert(value, message) { if (!value) throw new Error(message); }
function attestation(id, evidence, human = false) {
  const item = evidence[id];
  assert(item && item.status === "verified", `${id} requires a verified attestation`);
  assert(typeof item.reviewer === "string" && item.reviewer, `${id} requires reviewer`);
  assert(!Number.isNaN(Date.parse(item.reviewedAt)), `${id} requires reviewedAt`);
  assert(typeof item.evidenceRef === "string" && !item.evidenceRef.startsWith("pending:"), `${id} requires a real evidenceRef`);
  const result = { id, mode: human ? "human" : "attestation", status: "verified", reviewer: item.reviewer, reviewedAt: item.reviewedAt, evidenceRef: item.evidenceRef };
  if (human) {
    assert(typeof item.notes === "string" && item.notes.trim().length >= 20, `${id} requires substantive notes`);
    result.notes = item.notes;
  }
  return result;
}

export function buildConfig(releaseSha, evidence, baseUrl = "https://api6.zeaz.dev") {
  assert(/^[0-9a-f]{40}$/.test(releaseSha), "release SHA must be a full lowercase SHA");
  const base = new URL(baseUrl);
  assert(base.protocol === "https:" && base.pathname === "/", "base URL must be an HTTPS origin");
  const url = (path) => new URL(path, base).href;
  return {
    schemaVersion: "1.0.0",
    releaseSha,
    checks: [
      { id: "observability.dashboard", mode: "probe", url: "https://grafana.zeaz.dev/api/health", expectedStatus: 200 },
      attestation("observability.traces", evidence),
      { id: "observability.alert_delivery", mode: "command", command: "node scripts/verify-phase6-external.mjs alert" },
      { id: "backup.external_restore", mode: "command", command: "bash scripts/backup/external-supabase-restore.sh run", timeoutMs: 300000 },
      { id: "ai.streaming", mode: "probe", url: url("/ai/stream"), expectedStatus: 200, bodyIncludes: '\"status\": \"verified\"' },
      { id: "ai.upload", mode: "command", command: "node scripts/verify-phase6-external.mjs upload" },
      { id: "ai.multi_provider", mode: "probe", url: url("/ai/providers/verify"), method: "POST", body: { prompt: "Reply with verified." }, expectedStatus: 200, bodyIncludes: '"status":"verified"' },
      { id: "ai.failover", mode: "probe", url: url("/ai/failover"), method: "POST", body: { prompt: "Reply with verified.", forcePrimaryFailure: true }, expectedStatus: 200, bodyIncludes: '"failover":true' },
      { id: "browser.bundle_scan", mode: "scan", paths: ["artifacts/browser/app.js"] },
      { id: "browser.har_scan", mode: "scan", paths: ["artifacts/browser/session.har"] },
      attestation("zchat.keyboard", evidence, true),
      attestation("zchat.screen_reader", evidence, true),
      attestation("zchat.responsive", evidence, true),
      { id: "zchat.session_provider", mode: "probe", url: url("/session/health"), expectedStatus: 200, bodyIncludes: '"persisted":true' },
    ],
  };
}

async function main() {
  const [releaseSha, evidencePath, outputPath = "phase6-external-suite.json"] = process.argv.slice(2);
  assert(releaseSha && evidencePath, "usage: generate-phase6-external-config.mjs <release-sha> <attestations.json> [output.json]");
  const evidence = JSON.parse(await readFile(evidencePath, "utf8"));
  await writeFile(outputPath, `${JSON.stringify(buildConfig(releaseSha, evidence), null, 2)}\n`, { mode: 0o600 });
  console.log(JSON.stringify({ releaseSha, outputPath, checks: 14 }));
}

if (process.argv[1] && import.meta.url === new URL(`file://${process.argv[1]}`).href) {
  main().catch((error) => { console.error(`phase6 config generation failed: ${error.message}`); process.exitCode = 1; });
}
