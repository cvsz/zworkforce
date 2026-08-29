import test from "node:test";
import assert from "node:assert/strict";

import { collectEvidence, REQUIRED_CHECKS, validateManifest } from "./external-readiness.mjs";

const releaseSha = "a".repeat(40);

function manifest() {
  return {
    schemaVersion: "1.0.0",
    releaseSha,
    checks: REQUIRED_CHECKS.map((id) => ({
      id,
      mode: "attestation",
      status: "verified",
      reviewer: "staging-reviewer",
      reviewedAt: "2026-07-14T08:00:00Z",
      evidenceRef: `ticket:${id}`,
    })),
  };
}

test("accepts a complete immutable readiness manifest", () => {
  assert.doesNotThrow(() => validateManifest(manifest(), releaseSha));
});

test("rejects manifests for another release", () => {
  assert.throws(() => validateManifest(manifest(), "b".repeat(40)), /does not match/);
});

test("rejects missing checks", () => {
  const value = manifest();
  value.checks.pop();
  assert.throws(() => validateManifest(value, releaseSha), /missing readiness checks/);
});

test("rejects insecure probe URLs", () => {
  const value = manifest();
  value.checks[0] = { id: REQUIRED_CHECKS[0], mode: "probe", url: "http://staging.invalid/health" };
  assert.throws(() => validateManifest(value, releaseSha), /must use HTTPS/);
});

test("rejects invalid expected probe statuses", () => {
  const value = manifest();
  value.checks[0] = { id: REQUIRED_CHECKS[0], mode: "probe", url: "https://staging.zeaz.dev/health", expectedStatus: 0 };
  assert.throws(() => validateManifest(value, releaseSha), /invalid expectedStatus/);
});

test("rejects invalid or placeholder probe URLs", () => {
  const value = manifest();
  value.checks[0] = { id: REQUIRED_CHECKS[0], mode: "probe", url: "pending:dashboard" };
  assert.throws(() => validateManifest(value, releaseSha), /invalid URL|must use HTTPS|placeholder URL/);
});

test("rejects example placeholder probe URLs", () => {
  const value = manifest();
  value.checks[0] = { id: REQUIRED_CHECKS[0], mode: "probe", url: "https://staging.example.invalid/health" };
  assert.throws(() => validateManifest(value, releaseSha), /placeholder URL/);
});

test("rejects pending attestation evidence", () => {
  const value = manifest();
  value.checks[0].evidenceRef = "pending:external-verification";
  assert.throws(() => validateManifest(value, releaseSha), /placeholder evidenceRef/);
});

test("rejects replacement placeholders in attestation evidence", () => {
  const value = manifest();
  value.checks[0].evidenceRef = "REPLACE_WITH_NON_SECRET_EVIDENCE_REFERENCE";
  assert.throws(() => validateManifest(value, releaseSha), /placeholder evidenceRef/);
});

test("requires operator ownership before evidence is verified", async () => {
  const evidence = await collectEvidence(manifest(), { releaseSha });
  assert.equal(evidence.result, "FAILED");
  assert.match(evidence.operatorRecordError, /incident owner/);
});

test("produces verified evidence with complete operator record", async () => {
  const evidence = await collectEvidence(manifest(), {
    releaseSha,
    stagingReviewer: "reviewer",
    incidentOwner: "owner",
    escalationRoute: "pager-policy",
    watchWindow: "24h",
  });
  assert.equal(evidence.result, "VERIFIED");
  assert.equal(evidence.checks.length, REQUIRED_CHECKS.length);
});

test("sends JSON probe bodies with an explicit content type", async () => {
  const value = manifest();
  value.checks[0] = { id: REQUIRED_CHECKS[0], mode: "probe", url: "https://staging.zeaz.dev/health", body: { hello: "world" } };
  const originalFetch = global.fetch;
  let observed;
  global.fetch = async (_url, init) => {
    observed = init;
    return new Response("ok", { status: 200 });
  };
  try {
    const evidence = await collectEvidence(value, {
      releaseSha,
      stagingReviewer: "reviewer",
      incidentOwner: "owner",
      escalationRoute: "pager-policy",
      watchWindow: "24h",
      allowedOrigins: "https://staging.zeaz.dev",
    });
    assert.equal(evidence.result, "VERIFIED");
    assert.equal(observed.headers["Content-Type"], "application/json");
    assert.equal(observed.body, JSON.stringify({ hello: "world" }));
  } finally {
    global.fetch = originalFetch;
  }
});

test("sends Cloudflare Access service-token headers without exposing them in evidence", async () => {
  const value = manifest();
  value.checks[0] = { id: REQUIRED_CHECKS[0], mode: "probe", url: "https://staging.zeaz.dev/health" };
  const originalFetch = global.fetch;
  let observed;
  global.fetch = async (_url, init) => {
    observed = init;
    return new Response("ok", { status: 200 });
  };
  try {
    const evidence = await collectEvidence(value, {
      releaseSha,
      accessClientId: "client-id",
      accessClientSecret: "client-secret",
      stagingReviewer: "reviewer",
      incidentOwner: "owner",
      escalationRoute: "pager-policy",
      watchWindow: "24h",
      allowedOrigins: "https://staging.zeaz.dev",
    });
    assert.equal(evidence.result, "VERIFIED");
    assert.equal(observed.headers["CF-Access-Client-Id"], "client-id");
    assert.equal(observed.headers["CF-Access-Client-Secret"], "client-secret");
    assert.equal(JSON.stringify(evidence).includes("client-secret"), false);
  } finally {
    global.fetch = originalFetch;
  }
});
