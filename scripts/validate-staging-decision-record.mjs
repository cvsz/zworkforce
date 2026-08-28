#!/usr/bin/env node
import { readFile } from "node:fs/promises";
import process from "node:process";

const FULL_SHA = /^[0-9a-f]{40}$/;
const PLACEHOLDER_PATTERNS = [
  /^pending:/i,
  /^replace_with/i,
  /example\.(com|org|net|invalid)/i,
  /localhost/i,
  /127\.0\.0\.1/i,
  /<[^>]+>/,
];

function isPlaceholder(value) {
  return PLACEHOLDER_PATTERNS.some((pattern) => pattern.test(value.trim()));
}

function requireString(errors, value, label) {
  if (typeof value !== "string" || value.trim() === "") {
    errors.push(`missing ${label}`);
    return false;
  }
  if (isPlaceholder(value)) {
    errors.push(`${label} uses a placeholder value`);
    return false;
  }
  return true;
}

function requireApprovedSection(errors, record, sectionName, keys) {
  const section = record?.[sectionName];
  if (!section || section.status !== "approved") {
    errors.push(`${sectionName}.status must be approved`);
    return;
  }
  for (const key of keys) {
    requireString(errors, section[key], `${sectionName}.${key}`);
  }
}

export function validateStagingDecisionRecord(record) {
  const errors = [];
  if (!record || record.schemaVersion !== "1.0.0") {
    errors.push("unsupported decision record schemaVersion");
    return errors;
  }

  if ("releaseSha" in record && record.releaseSha !== undefined && record.releaseSha !== null && record.releaseSha !== "") {
    if (!FULL_SHA.test(record.releaseSha)) {
      errors.push("releaseSha must be a 40-character lowercase commit SHA when provided");
    }
  }

  requireApprovedSection(errors, record, "identityProvider", ["providerClass", "claimMappingReference"]);
  requireApprovedSection(errors, record, "secretManager", ["providerClass"]);
  requireApprovedSection(errors, record, "managedDataServices", ["databaseClass", "queueClass", "objectStorageClass", "regionPolicy"]);
  requireApprovedSection(errors, record, "backup", ["targetClass", "retentionPolicyReference"]);
  requireApprovedSection(errors, record, "observability", ["platformClass", "alertRouteClass"]);
  requireApprovedSection(errors, record, "aiPolicy", ["allowlistReference", "quotaPolicyReference", "failoverPolicyReference", "dataGovernanceReference"]);
  requireApprovedSection(errors, record, "billing", ["currency", "jurisdiction", "merchantResponsibility", "paymentProcessorClass"]);

  return errors;
}

async function main() {
  const [recordPath] = process.argv.slice(2);
  if (!recordPath) {
    console.error("Usage: node scripts/validate-staging-decision-record.mjs <staging-decision-record.json>");
    process.exitCode = 2;
    return;
  }

  const record = JSON.parse(await readFile(recordPath, "utf8"));
  const errors = validateStagingDecisionRecord(record);
  if (errors.length) {
    for (const error of errors) console.error(`ERROR: ${error}`);
    process.exitCode = 1;
    return;
  }

  console.log("Staging decision record is structurally valid and operator-owned fields are approved.");
}

if (process.argv[1] && import.meta.url === new URL(`file://${process.argv[1]}`).href) {
  await main();
}
