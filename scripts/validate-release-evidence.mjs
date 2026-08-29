#!/usr/bin/env node
import { readFile } from "node:fs/promises";
import process from "node:process";

const FULL_SHA = /^[0-9a-f]{40}$/;

export function releaseCommitShas(text) {
  const values = new Map();
  for (const key of ["commitSha", "approvedCommitSha", "observedCommitSha"]) {
    const match = text.match(new RegExp(`^\\s*${key}:\\s*([^#\\s]+)\\s*$`, "m"));
    values.set(key, match?.[1] ?? null);
  }
  return values;
}

export function validateReleaseEvidence(text, expectedSha) {
  if (!FULL_SHA.test(expectedSha)) {
    return [`expected commit SHA must be 40 lowercase hexadecimal characters: ${expectedSha}`];
  }

  const errors = [];
  for (const [field, value] of releaseCommitShas(text)) {
    if (!value) {
      errors.push(`missing ${field}`);
    } else if (!FULL_SHA.test(value)) {
      errors.push(`${field} must be a 40-character lowercase commit SHA`);
    } else if (value !== expectedSha) {
      errors.push(`${field} (${value}) does not match release candidate ${expectedSha}`);
    }
  }
  return errors;
}

async function main() {
  const [recordPath, expectedSha] = process.argv.slice(2);
  if (!recordPath || !expectedSha) {
    console.error("Usage: node scripts/validate-release-evidence.mjs <release-record.yaml> <expected-commit-sha>");
    process.exitCode = 2;
    return;
  }

  const text = await readFile(recordPath, "utf8");
  const errors = validateReleaseEvidence(text, expectedSha);
  if (errors.length) {
    for (const error of errors) console.error(`ERROR: ${error}`);
    process.exitCode = 1;
    return;
  }
  console.log(`Release evidence is bound to immutable commit ${expectedSha}.`);
}

if (process.argv[1] && import.meta.url === new URL(`file://${process.argv[1]}`).href) {
  await main();
}
