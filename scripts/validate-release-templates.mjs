#!/usr/bin/env node
import { readFile, readdir } from "node:fs/promises";
import { basename, join, resolve } from "node:path";
import process from "node:process";

const root = resolve(new URL("..", import.meta.url).pathname);
const templateDir = join(root, ".github", "release-templates");
const schemaDir = join(root, "schemas", "release");

const mappings = new Map([
  ["staging-inventory.yaml", ["StagingInventory", "staging-inventory.schema.json"]],
  ["external-verification.yaml", ["ExternalVerification", "external-verification.schema.json"]],
  ["staging-review.yaml", ["StagingReview", "staging-review.schema.json"]],
  ["operational-ownership.yaml", ["OperationalOwnership", "operational-ownership.schema.json"]],
  ["production-release-record.yaml", ["ProductionReleaseRecord", "production-release-record.schema.json"]],
]);

function fail(message) {
  console.error(`ERROR: ${message}`);
  process.exitCode = 1;
}

function scalar(text, key) {
  const match = text.match(new RegExp(`^\\s*${key}:\\s*(.+?)\\s*$`, "m"));
  return match?.[1] ?? null;
}

function assertNoFloatingImages(text, file) {
  const imageLines = text.split(/\r?\n/).filter((line) => /image/i.test(line) && /:/.test(line));
  for (const line of imageLines) {
    if (/\b(latest|main|master|stable|dev)\b/i.test(line) && !line.includes("<")) {
      fail(`${file}: floating image reference is forbidden: ${line.trim()}`);
    }
  }
}

async function main() {
  const files = (await readdir(templateDir)).filter((file) => file.endsWith(".yaml")).sort();
  for (const expected of mappings.keys()) {
    if (!files.includes(expected)) fail(`missing release template: ${expected}`);
  }

  for (const file of files) {
    const mapping = mappings.get(file);
    if (!mapping) {
      fail(`unmapped release template: ${file}`);
      continue;
    }
    const [expectedKind, schemaFile] = mapping;
    const text = await readFile(join(templateDir, file), "utf8");
    const schema = JSON.parse(await readFile(join(schemaDir, schemaFile), "utf8"));

    if (scalar(text, "apiVersion") !== "release.zeaz.dev/v1alpha1") {
      fail(`${file}: invalid or missing apiVersion`);
    }
    if (scalar(text, "kind") !== expectedKind) {
      fail(`${file}: expected kind ${expectedKind}`);
    }
    for (const section of ["metadata", "spec"]) {
      if (!new RegExp(`^${section}:\\s*$`, "m").test(text)) fail(`${file}: missing ${section}`);
    }
    if (schema.properties?.kind?.const !== expectedKind) {
      fail(`${schemaFile}: kind const does not match ${expectedKind}`);
    }
    if (schema.$schema !== "https://json-schema.org/draft/2020-12/schema") {
      fail(`${schemaFile}: must use JSON Schema draft 2020-12`);
    }
    assertNoFloatingImages(text, file);
  }

  const common = JSON.parse(await readFile(join(schemaDir, "common.schema.json"), "utf8"));
  for (const name of ["fullCommitSha", "sha256", "imageDigest", "timestamp"]) {
    if (!common.$defs?.[name]) fail(`common.schema.json: missing $defs.${name}`);
  }

  if (!process.exitCode) {
    console.log(`Validated ${mappings.size} release templates and ${mappings.size + 1} schemas.`);
  }
}

await main();
