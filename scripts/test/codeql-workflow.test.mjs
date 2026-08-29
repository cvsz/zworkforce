import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { fileURLToPath } from "node:url";
import test from "node:test";

const workflowPath = fileURLToPath(new URL("../../.github/workflows/codeql.yml", import.meta.url));
const configPath = fileURLToPath(new URL("../../.github/codeql/codeql-config.yml", import.meta.url));

const workflow = await readFile(workflowPath, "utf8");
const config = await readFile(configPath, "utf8");

test("CodeQL workflow uses GitHub-hosted capacity", () => {
  assert.match(workflow, /runs-on:\s*ubuntu-latest/);
});

test("CodeQL workflow loads the repository config file", () => {
  assert.match(workflow, /config-file:\s*\.\/\.github\/codeql\/codeql-config\.yml/);
});

test("CodeQL workflow provisions language toolchains before init", () => {
  const initIndex = workflow.indexOf("github/codeql-action/init@v4");
  const pnpmSetupIndex = workflow.indexOf("pnpm/action-setup@");
  assert.ok(initIndex > 0);
  assert.ok(workflow.indexOf("actions/setup-node@v7") < initIndex);
  assert.ok(pnpmSetupIndex > 0 && pnpmSetupIndex < initIndex);
  assert.ok(workflow.indexOf("actions/setup-go@v7") < initIndex);
  assert.ok(workflow.indexOf("actions/setup-python@v7") < initIndex);
  assert.match(workflow, /actions\/setup-node@v7/);
  assert.match(workflow, /node-version:\s*24/);
  assert.match(workflow, /pnpm\/action-setup@[0-9a-f]{40}\s*# v6\.0\.10/);
  assert.match(workflow, /pnpm install --ignore-scripts --frozen-lockfile/);
  assert.match(workflow, /actions\/setup-go@v7/);
  assert.match(workflow, /go-version-file:\s*tools\/zctl\/go\.mod/);
  assert.match(workflow, /actions\/setup-python@v7/);
  assert.match(workflow, /python-version:\s*"3\.11"/);
});

test("CodeQL config enables the security-and-quality suite", () => {
  assert.match(config, /uses:\s*security-and-quality/);
});
