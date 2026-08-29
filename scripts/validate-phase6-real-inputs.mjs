#!/usr/bin/env node
import { readFile } from "node:fs/promises";
import net from "node:net";

const PLACEHOLDER = /(?:^|[\s:/._-])(pending|placeholder|replace(?:_|-)?with|todo|tbd|dummy|fake|sample|example|changeme|your[-_ ]|test[-_ ]?(?:url|endpoint|token)|staging\.example|example\.(?:com|org|net|invalid)|localhost|127\.0\.0\.1|0\.0\.0\.0)(?:$|[\s:/._-])/i;
const SHELL_PLACEHOLDER = /(?:^|\s)(?:true|false|echo\s+(?:ok|success)|exit\s+0|:)(?:\s|$)/i;

function fail(message) {
  throw new Error(message);
}

function required(value, name) {
  if (typeof value !== "string" || !value.trim()) fail(`${name} is required`);
  const normalized = value.trim();
  if (PLACEHOLDER.test(normalized)) fail(`${name} contains a placeholder or local-only value`);
  return normalized;
}

function realHttps(value, name) {
  const normalized = required(value, name);
  let url;
  try { url = new URL(normalized); } catch { fail(`${name} must be a valid URL`); }
  if (url.protocol !== "https:") fail(`${name} must use HTTPS`);
  if (!url.hostname.includes(".")) fail(`${name} must use a fully-qualified external hostname`);
  if (net.isIP(url.hostname)) fail(`${name} must not use a raw IP address`);
  if (url.username || url.password) fail(`${name} must not embed credentials`);
  return normalized;
}

function realCommand(value, name) {
  const normalized = required(value, name);
  if (normalized.length < 12) fail(`${name} is too short to represent a real operation`);
  if (SHELL_PLACEHOLDER.test(normalized)) fail(`${name} is a no-op or synthetic success command`);
  return normalized;
}

function validateConfig(config) {
  if (!/^[0-9a-f]{40}$/.test(config.releaseSha ?? "")) fail("config.releaseSha must be a full lowercase SHA");
  if (!Array.isArray(config.checks)) fail("config.checks must be an array");
  for (const check of config.checks) {
    required(check.id, "check.id");
    if (check.url) realHttps(check.url, `${check.id}.url`);
    if (check.command) realCommand(check.command, `${check.id}.command`);
    if (check.reviewer) required(check.reviewer, `${check.id}.reviewer`);
    if (check.evidenceRef) required(check.evidenceRef, `${check.id}.evidenceRef`);
    if (check.reviewedAt && Number.isNaN(Date.parse(check.reviewedAt))) fail(`${check.id}.reviewedAt must be an ISO timestamp`);
  }
}

async function main() {
  const [configPath] = process.argv.slice(2);
  if (!configPath) fail("usage: validate-phase6-real-inputs.mjs <config.json>");
  const config = JSON.parse(await readFile(configPath, "utf8"));
  validateConfig(config);

  realHttps(process.env.ALERT_TEST_URL, "ALERT_TEST_URL");
  realHttps(process.env.ALERT_DELIVERY_STATUS_URL, "ALERT_DELIVERY_STATUS_URL");
  realCommand(process.env.BACKUP_CREATE_COMMAND, "BACKUP_CREATE_COMMAND");
  realCommand(process.env.BACKUP_RESTORE_COMMAND, "BACKUP_RESTORE_COMMAND");
  realCommand(process.env.BACKUP_VERIFY_COMMAND, "BACKUP_VERIFY_COMMAND");
  realHttps(process.env.AI_UPLOAD_URL, "AI_UPLOAD_URL");
  realHttps(process.env.AI_FAILOVER_URL, "AI_FAILOVER_URL");

  const providers = required(process.env.AI_PROVIDER_ENDPOINTS, "AI_PROVIDER_ENDPOINTS")
    .split(",").map((value) => value.trim()).filter(Boolean);
  if (providers.length < 2) fail("AI_PROVIDER_ENDPOINTS requires at least two real providers");
  providers.forEach((value, index) => realHttps(value, `AI_PROVIDER_ENDPOINTS[${index}]`));
  if (new Set(providers.map((value) => new URL(value).origin)).size < 2) fail("AI_PROVIDER_ENDPOINTS must use at least two distinct provider origins");

  console.log(JSON.stringify({ result: "REAL_INPUTS_VALIDATED", providers: providers.length }));
}

main().catch((error) => {
  console.error(`phase6 real-input validation failed: ${error.message}`);
  process.exitCode = 1;
});
