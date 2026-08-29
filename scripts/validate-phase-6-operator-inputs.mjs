#!/usr/bin/env node
import { readFile } from "node:fs/promises";
import process from "node:process";

const EXPECTED_ITEMS = [
  {
    id: "external-identity-provider-production-claim-mapping",
    issueItem: "External identity provider and production claim mapping",
    recordOwner: "Identity / Cloudflare",
  },
  {
    id: "production-secret-manager-selection",
    issueItem: "Production secret-manager selection",
    recordOwner: "Infrastructure / secrets",
  },
  {
    id: "managed-production-data-services-region-retention-observability-backup",
    issueItem: "Managed production data services, region, retention authority, observability platform, and external backup target",
    recordOwner: "Platform / operations",
  },
  {
    id: "billing-currency-jurisdiction-tax-merchant-payment-processor",
    issueItem: "Billing currency, jurisdiction, tax treatment, merchant responsibilities, and payment processor",
    recordOwner: "Finance / legal",
  },
  {
    id: "staging-reviewer-production-approver-incident-owner-escalation-route-watch-window",
    issueItem: "Staging reviewer, production approver, incident owner, escalation route, and watch window",
    recordOwner: "Release / incident ownership",
  },
];

const PLACEHOLDER_PATTERNS = [/^pending:/i, /^replace_with/i, /<[^>]+>/, /example\.(com|org|net|invalid)/i];

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

export function validatePhase6OperatorInputs(record) {
  const errors = [];
  if (!record || record.schemaVersion !== "1.0.0") {
    errors.push("unsupported operator-inputs schemaVersion");
    return errors;
  }

  if (!Array.isArray(record.items)) {
    errors.push("operator-inputs items must be an array");
    return errors;
  }

  if (record.items.length !== EXPECTED_ITEMS.length) {
    errors.push(`expected ${EXPECTED_ITEMS.length} operator-input records`);
  }

  const seen = new Set();
  record.items.forEach((item, index) => {
    const expected = EXPECTED_ITEMS[index];
    if (!item || typeof item !== "object") {
      errors.push(`item ${index + 1} must be an object`);
      return;
    }
    if (item.id !== expected.id) errors.push(`item ${index + 1} id must be ${expected.id}`);
    if (seen.has(item.id)) errors.push(`duplicate item id: ${item.id}`);
    seen.add(item.id);
    if (item.issueItem !== expected.issueItem) errors.push(`item ${item.id} issueItem must be ${expected.issueItem}`);
    if (item.status !== "PENDING_OPERATOR") errors.push(`item ${item.id} status must be PENDING_OPERATOR`);
    if (item.recordOwner !== expected.recordOwner) errors.push(`item ${item.id} recordOwner must be ${expected.recordOwner}`);
    if (!Array.isArray(item.canonicalTargets) || item.canonicalTargets.length === 0) {
      errors.push(`item ${item.id} requires canonicalTargets`);
    } else {
      for (const target of item.canonicalTargets) {
        requireString(errors, target, `${item.id}.canonicalTargets`);
      }
    }
  });

  return errors;
}

async function main() {
  const [recordPath] = process.argv.slice(2);
  if (!recordPath) {
    console.error("Usage: node scripts/validate-phase-6-operator-inputs.mjs <phase-6-operator-inputs.json>");
    process.exitCode = 2;
    return;
  }

  const record = JSON.parse(await readFile(recordPath, "utf8"));
  const errors = validatePhase6OperatorInputs(record);
  if (errors.length) {
    for (const error of errors) console.error(`ERROR: ${error}`);
    process.exitCode = 1;
    return;
  }

  console.log("Phase 6 operator input register is structurally valid and remains explicitly pending operator input.");
}

if (process.argv[1] && import.meta.url === new URL(`file://${process.argv[1]}`).href) {
  await main();
}
