#!/usr/bin/env node

import { createHash } from "node:crypto";
import { readFile, writeFile } from "node:fs/promises";
import { withJsonBody } from "./probe-body.mjs";

export const REQUIRED_CHECKS = [
  "observability.dashboard",
  "observability.traces",
  "observability.alert_delivery",
  "backup.external_restore",
  "ai.streaming",
  "ai.upload",
  "ai.multi_provider",
  "ai.failover",
  "browser.bundle_scan",
  "browser.har_scan",
  "zchat.keyboard",
  "zchat.screen_reader",
  "zchat.responsive",
  "zchat.session_provider",
];

const SHA_RE = /^[0-9a-f]{40}$/;
const SAFE_STATUS = new Set(["verified", "failed"]);
const PLACEHOLDER_PATTERNS = [
  /^pending:/i,
  /^replace_with/i,
  /example\.(com|org|net|invalid)/i,
  /localhost/i,
  /127\.0\.0\.1/i,
  /0\.0\.0\.0/i,
  /<[^>]+>/,
  /staging-observability-host/i,
  /staging\.example\.invalid/i,
];

function isPlaceholderEvidence(value) {
  return PLACEHOLDER_PATTERNS.some((pattern) => pattern.test(value.trim()));
}

function allowedOrigins(value = process.env.STAGING_ALLOWED_ORIGINS) {
  if (typeof value !== "string" || !value.trim()) throw new Error("STAGING_ALLOWED_ORIGINS is required for HTTPS probes");
  return new Set(value.split(",").map((origin) => {
    const parsed = new URL(origin.trim());
    if (parsed.protocol !== "https:" || parsed.pathname !== "/" || parsed.search || parsed.hash) throw new Error("STAGING_ALLOWED_ORIGINS must contain HTTPS origins only");
    return parsed.origin;
  }));
}

function assertAllowedOrigin(url, origins) {
  if (!origins.has(url.origin)) throw new Error(`probe origin is not allowlisted: ${url.origin}`);
  return url;
}

export function validateManifest(manifest, releaseSha) {
  if (!SHA_RE.test(releaseSha)) throw new Error("release SHA must be a full 40-character lowercase Git SHA");
  if (!manifest || manifest.schemaVersion !== "1.0.0") throw new Error("unsupported readiness manifest schema");
  if (manifest.releaseSha !== releaseSha) throw new Error("manifest releaseSha does not match checked-out release");
  if (!Array.isArray(manifest.checks)) throw new Error("manifest checks must be an array");

  const ids = new Set();
  for (const check of manifest.checks) {
    if (!check || typeof check.id !== "string" || ids.has(check.id)) throw new Error("check IDs must be unique strings");
    ids.add(check.id);
    if (!REQUIRED_CHECKS.includes(check.id)) throw new Error(`unknown readiness check: ${check.id}`);
    if (!["probe", "attestation"].includes(check.mode)) throw new Error(`invalid mode for ${check.id}`);
    if (check.mode === "probe") {
      let url;
      try {
        url = new URL(check.url);
      } catch {
        throw new Error(`probe ${check.id} has invalid URL`);
      }
      if (url.protocol !== "https:") throw new Error(`probe ${check.id} must use HTTPS`);
      if (isPlaceholderEvidence(check.url)) throw new Error(`probe ${check.id} uses placeholder URL`);
      if ("expectedStatus" in check && (!Number.isInteger(check.expectedStatus) || check.expectedStatus < 200 || check.expectedStatus > 599)) {
        throw new Error(`invalid expectedStatus for ${check.id}`);
      }
    } else {
      if (check.status !== "verified") throw new Error(`attestation ${check.id} must be explicitly verified`);
      for (const field of ["reviewer", "reviewedAt", "evidenceRef"]) {
        if (typeof check[field] !== "string" || check[field].trim() === "") throw new Error(`attestation ${check.id} requires ${field}`);
      }
      if (Number.isNaN(Date.parse(check.reviewedAt))) throw new Error(`attestation ${check.id} has invalid reviewedAt`);
      if (isPlaceholderEvidence(check.evidenceRef)) throw new Error(`attestation ${check.id} uses placeholder evidenceRef`);
    }
  }
  const missing = REQUIRED_CHECKS.filter((id) => !ids.has(id));
  if (missing.length) throw new Error(`missing readiness checks: ${missing.join(", ")}`);
}

function hash(value) {
  return createHash("sha256").update(value).digest("hex");
}

async function runProbe(check, token, accessClientId, accessClientSecret, origins) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), check.timeoutMs ?? 15000);
  try {
    const headers = { Accept: "application/json, text/plain, */*" };
    if (token) headers.Authorization = `Bearer ${token}`;
    if (accessClientId && accessClientSecret) {
      headers["CF-Access-Client-Id"] = accessClientId;
      headers["CF-Access-Client-Secret"] = accessClientSecret;
    }
    const request = withJsonBody(headers, check.body);
    const safeUrl = assertAllowedOrigin(new URL(check.url), origins);
    const response = await fetch(safeUrl.href, {
      method: check.method ?? "GET",
      headers: request.headers,
      body: request.body,
      signal: controller.signal,
      redirect: "error",
    });
    const expected = check.expectedStatus ?? 200;
    return {
      id: check.id,
      mode: "probe",
      status: response.status === expected ? "verified" : "failed",
      observedStatus: response.status,
      expectedStatus: expected,
      endpointFingerprint: hash(safeUrl.origin),
      checkedAt: new Date().toISOString(),
    };
  } catch (error) {
    return {
      id: check.id,
      mode: "probe",
      status: "failed",
      errorClass: error?.name ?? "Error",
      endpointFingerprint: hash(new URL(check.url).origin),
      checkedAt: new Date().toISOString(),
    };
  } finally {
    clearTimeout(timer);
  }
}

function sanitizeAttestation(check) {
  return {
    id: check.id,
    mode: "attestation",
    status: check.status,
    reviewer: check.reviewer,
    reviewedAt: check.reviewedAt,
    evidenceRef: check.evidenceRef,
  };
}

export async function collectEvidence(manifest, options = {}) {
  validateManifest(manifest, options.releaseSha);
  const checks = [];
  for (const check of manifest.checks) {
    checks.push(
      check.mode === "probe"
        ? await runProbe(check, options.token, options.accessClientId, options.accessClientSecret, options.origins ?? allowedOrigins(options.allowedOrigins))
        : sanitizeAttestation(check),
    );
  }
  const complete = checks.every((check) => SAFE_STATUS.has(check.status) && check.status === "verified");
  const evidence = {
    schemaVersion: "1.0.0",
    releaseSha: options.releaseSha,
    generatedAt: new Date().toISOString(),
    repository: options.repository ?? "cvsz/z-platform",
    workflowRunId: options.workflowRunId ?? null,
    operatorRecord: {
      stagingReviewer: options.stagingReviewer ?? "",
      incidentOwner: options.incidentOwner ?? "",
      escalationRoute: options.escalationRoute ?? "",
      watchWindow: options.watchWindow ?? "",
    },
    decisionRecord: options.decisionRecord ?? {},
    checks,
    result: complete ? "VERIFIED" : "FAILED",
  };
  if (Object.values(evidence.operatorRecord).some((value) => typeof value !== "string" || value.trim() === "")) {
    evidence.result = "FAILED";
    evidence.operatorRecordError = "staging reviewer, incident owner, escalation route, and watch window are required";
  }
  return evidence;
}

async function main() {
  const [manifestPath, outputPath = "external-staging-evidence.json"] = process.argv.slice(2);
  if (!manifestPath) throw new Error("usage: node scripts/external-readiness.mjs <manifest.json> [output.json]");
  const manifest = JSON.parse(await readFile(manifestPath, "utf8"));
  const releaseSha = process.env.RELEASE_SHA ?? "";
  const decisionRecord = JSON.parse(process.env.DECISION_RECORD_JSON ?? "{}");
  const evidence = await collectEvidence(manifest, {
    releaseSha,
    token: process.env.STAGING_BEARER_TOKEN,
    accessClientId: process.env.STAGING_CF_ACCESS_CLIENT_ID,
    accessClientSecret: process.env.STAGING_CF_ACCESS_CLIENT_SECRET,
    allowedOrigins: process.env.STAGING_ALLOWED_ORIGINS,
    repository: process.env.GITHUB_REPOSITORY,
    workflowRunId: process.env.GITHUB_RUN_ID,
    stagingReviewer: process.env.STAGING_REVIEWER,
    incidentOwner: process.env.INCIDENT_OWNER,
    escalationRoute: process.env.ESCALATION_ROUTE,
    watchWindow: process.env.WATCH_WINDOW,
    decisionRecord,
  });
  await writeFile(outputPath, `${JSON.stringify(evidence, null, 2)}\n`, { mode: 0o600 });
  console.log(JSON.stringify({ releaseSha: evidence.releaseSha, result: evidence.result, checks: evidence.checks.length }));
  if (evidence.result !== "VERIFIED") process.exitCode = 1;
}

if (import.meta.url === `file://${process.argv[1]}`) {
  main().catch((error) => {
    console.error(`external readiness failed: ${error.message}`);
    process.exitCode = 1;
  });
}
