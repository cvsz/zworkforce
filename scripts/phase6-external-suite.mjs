#!/usr/bin/env node
import { createHash } from "node:crypto";
import { mkdir, readFile, writeFile } from "node:fs/promises";
import { spawn } from "node:child_process";
import { withJsonBody } from "./probe-body.mjs";

const REQUIRED = [
  "observability.dashboard", "observability.traces", "observability.alert_delivery",
  "backup.external_restore", "ai.streaming", "ai.upload", "ai.multi_provider",
  "ai.failover", "browser.bundle_scan", "browser.har_scan", "zchat.keyboard",
  "zchat.screen_reader", "zchat.responsive", "zchat.session_provider",
];
const HUMAN = new Set(["zchat.keyboard", "zchat.screen_reader", "zchat.responsive"]);
const PLACEHOLDER = /^(pending:|replace_with)|<[^>]+>|example\.(com|org|net)|template|staging-.*-host/i;
const sha256 = (value) => createHash("sha256").update(value).digest("hex");

function assert(value, message) { if (!value) throw new Error(message); }
function safeRef(value, id) {
  assert(typeof value === "string" && value.trim(), `${id} requires evidenceRef`);
  assert(!PLACEHOLDER.test(value.trim()), `${id} uses placeholder evidenceRef`);
  return value.trim();
}

function allowedOrigins(value = process.env.STAGING_ALLOWED_ORIGINS) {
  assert(typeof value === "string" && value.trim(), "STAGING_ALLOWED_ORIGINS is required for HTTPS probes");
  return new Set(value.split(",").map((origin) => {
    const url = new URL(origin.trim());
    assert(url.protocol === "https:" && url.pathname === "/" && !url.search && !url.hash, "STAGING_ALLOWED_ORIGINS must contain HTTPS origins only");
    return url.origin;
  }));
}

async function runCommand(command, timeoutMs = 120000) {
  return await new Promise((resolve) => {
    const child = spawn("bash", ["-lc", command], { stdio: ["ignore", "pipe", "pipe"] });
    let stdout = "", stderr = "";
    const timer = setTimeout(() => child.kill("SIGKILL"), timeoutMs);
    child.stdout.on("data", (chunk) => { stdout += chunk; });
    child.stderr.on("data", (chunk) => { stderr += chunk; });
    child.on("close", (code, signal) => {
      clearTimeout(timer);
      resolve({ code: code ?? 1, signal, stdout: stdout.slice(-12000), stderr: stderr.slice(-12000) });
    });
  });
}

export async function httpProbe(
  check,
  token,
  origins = allowedOrigins(),
  accessClientId = process.env.STAGING_CF_ACCESS_CLIENT_ID,
  accessClientSecret = process.env.STAGING_CF_ACCESS_CLIENT_SECRET,
) {
  const url = new URL(check.url);
  assert(url.protocol === "https:", `${check.id} must use HTTPS`);
  assert(origins.has(url.origin), `${check.id} origin is not allowlisted`);
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), check.timeoutMs ?? 30000);
  try {
    const headers = { Accept: check.accept ?? "application/json, text/plain, */*", ...(check.headers ?? {}) };
    if (token && check.useBearerToken !== false) headers.Authorization = `Bearer ${token}`;
    if (accessClientId && accessClientSecret) {
      headers["CF-Access-Client-Id"] = accessClientId;
      headers["CF-Access-Client-Secret"] = accessClientSecret;
    }
    const request = withJsonBody(headers, check.body);
    const response = await fetch(url, {
      method: check.method ?? "GET", headers: request.headers,
      body: request.body,
      redirect: "error", signal: controller.signal,
    });
    const text = await response.text();
    const expected = check.expectedStatus ?? 200;
    const bodyOk = check.bodyIncludes ? text.includes(check.bodyIncludes) : true;
    return {
      id: check.id, mode: "probe", status: response.status === expected && bodyOk ? "verified" : "failed",
      observedStatus: response.status, expectedStatus: expected, bodyAssertion: check.bodyIncludes ?? null,
      endpointFingerprint: sha256(url.origin), checkedAt: new Date().toISOString(),
    };
  } catch (error) {
    return { id: check.id, mode: "probe", status: "failed", errorClass: error?.name ?? "Error", endpointFingerprint: sha256(url.origin), checkedAt: new Date().toISOString() };
  } finally { clearTimeout(timer); }
}

async function commandCheck(check) {
  assert(typeof check.command === "string" && check.command.trim(), `${check.id} requires command`);
  const result = await runCommand(check.command, check.timeoutMs);
  return {
    id: check.id, mode: "command", status: result.code === 0 ? "verified" : "failed",
    commandFingerprint: sha256(check.command), exitCode: result.code, signal: result.signal,
    stdoutDigest: sha256(result.stdout), stderrDigest: sha256(result.stderr), checkedAt: new Date().toISOString(),
  };
}

async function scanCheck(check) {
  assert(Array.isArray(check.paths) && check.paths.length, `${check.id} requires paths`);
  const forbidden = check.forbiddenPatterns ?? ["Bearer ", "api_key", "x-api-key", "Z_PLATFORM_SERVICE_TOKEN", "AI_GATEWAY_PROVIDER_TOKEN"];
  const files = [];
  for (const path of check.paths) files.push({ path, content: await readFile(path, "utf8") });
  const findings = [];
  for (const file of files) for (const pattern of forbidden) if (file.content.toLowerCase().includes(String(pattern).toLowerCase())) findings.push({ path: file.path, pattern });
  return { id: check.id, mode: "scan", status: findings.length ? "failed" : "verified", files: files.map((f) => ({ path: f.path, digest: sha256(f.content) })), findingCount: findings.length, checkedAt: new Date().toISOString() };
}

function humanCheck(check, reviewer) {
  assert(check.status === "verified", `${check.id} human QA must be explicitly verified`);
  assert(check.reviewer === reviewer, `${check.id} reviewer must match STAGING_REVIEWER`);
  assert(!Number.isNaN(Date.parse(check.reviewedAt)), `${check.id} has invalid reviewedAt`);
  safeRef(check.evidenceRef, check.id);
  assert(typeof check.notes === "string" && check.notes.trim().length >= 20, `${check.id} requires substantive notes`);
  return { id: check.id, mode: "human-attestation", status: "verified", reviewer: check.reviewer, reviewedAt: check.reviewedAt, evidenceRef: check.evidenceRef, notesDigest: sha256(check.notes) };
}

async function main() {
  const [configPath, outputDir = "phase6-external-evidence"] = process.argv.slice(2);
  assert(configPath, "usage: phase6-external-suite.mjs <config.json> [output-dir]");
  const config = JSON.parse(await readFile(configPath, "utf8"));
  const releaseSha = process.env.RELEASE_SHA ?? "";
  const reviewer = process.env.STAGING_REVIEWER ?? "";
  const accessClientId = process.env.STAGING_CF_ACCESS_CLIENT_ID ?? "";
  const accessClientSecret = process.env.STAGING_CF_ACCESS_CLIENT_SECRET ?? "";
  assert(/^[0-9a-f]{40}$/.test(releaseSha), "RELEASE_SHA must be a full lowercase SHA");
  assert(config.releaseSha === releaseSha, "config releaseSha does not match RELEASE_SHA");
  assert(reviewer, "STAGING_REVIEWER is required");
  assert(Boolean(accessClientId) === Boolean(accessClientSecret), "Cloudflare Access service-token credentials must be provided as a pair");
  assert(Array.isArray(config.checks), "checks must be an array");
  const ids = new Set(config.checks.map((check) => check.id));
  const missing = REQUIRED.filter((id) => !ids.has(id));
  assert(!missing.length, `missing checks: ${missing.join(", ")}`);

  const results = [];
  for (const check of config.checks) {
    assert(REQUIRED.includes(check.id), `unknown check ${check.id}`);
    if (HUMAN.has(check.id)) results.push(humanCheck(check, reviewer));
    else if (check.mode === "probe") results.push(await httpProbe(
      check,
      process.env.STAGING_BEARER_TOKEN,
      allowedOrigins(),
      accessClientId,
      accessClientSecret,
    ));
    else if (check.mode === "command") results.push(await commandCheck(check));
    else if (check.mode === "scan") results.push(await scanCheck(check));
    else if (check.mode === "attestation") {
      assert(check.status === "verified", `${check.id} must be verified`);
      assert(check.reviewer === reviewer, `${check.id} reviewer must match STAGING_REVIEWER`);
      safeRef(check.evidenceRef, check.id);
      results.push({ id: check.id, mode: "attestation", status: "verified", reviewer: check.reviewer, reviewedAt: check.reviewedAt, evidenceRef: check.evidenceRef });
    } else throw new Error(`unsupported mode for ${check.id}`);
  }

  const result = results.every((item) => item.status === "verified") ? "VERIFIED" : "FAILED";
  const evidence = { schemaVersion: "1.0.0", releaseSha, generatedAt: new Date().toISOString(), repository: process.env.GITHUB_REPOSITORY ?? "cvsz/z-platform", workflowRunId: process.env.GITHUB_RUN_ID ?? null, reviewer, checks: results, result };
  await mkdir(outputDir, { recursive: true });
  await writeFile(`${outputDir}/phase6-external-evidence.json`, `${JSON.stringify(evidence, null, 2)}\n`, { mode: 0o600 });
  console.log(JSON.stringify({ releaseSha, result, checks: results.length }));
  if (result !== "VERIFIED") process.exitCode = 1;
}

if (process.argv[1] && import.meta.url === new URL(`file://${process.argv[1]}`).href) {
  main().catch((error) => { console.error(`phase6 external suite failed: ${error.message}`); process.exitCode = 1; });
}
