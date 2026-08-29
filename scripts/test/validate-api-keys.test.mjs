import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { mkdtemp, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";

const script = fileURLToPath(new URL("../validate-api-keys.mjs", import.meta.url));

async function run(contents, ...args) {
  const directory = await mkdtemp(join(tmpdir(), "z-platform-api-key-test-"));
  const file = join(directory, "API-KEY.txt");
  await writeFile(file, contents, { mode: 0o600 });
  return spawnSync(process.execPath, [script, "--file", file, ...args], {
    encoding: "utf8",
    env: { ...process.env, NO_COLOR: "1" },
  });
}

test("syntax-only mode finds populated API keys without exposing values", async () => {
  const secret = "super-secret-provider-key-123";
  const result = await run(`NVIDIA_NIM_API_KEY=${secret}\nEMPTY_API_KEY=\n`, "--syntax-only", "--json");

  assert.equal(result.status, 0, result.stderr);
  assert.doesNotMatch(result.stdout, new RegExp(secret));
  const output = JSON.parse(result.stdout);
  assert.equal(output.checked, 2);
  assert.equal(output.summary["syntax-valid"], 1);
  assert.equal(output.summary.empty, 1);
});

test("rejects duplicate variables", async () => {
  const result = await run("GROQ_API_KEY=first\nGROQ_API_KEY=second\n", "--syntax-only", "--json");

  assert.equal(result.status, 1);
  const output = JSON.parse(result.stdout);
  assert.equal(output.parseErrors.length, 1);
  assert.match(output.parseErrors[0].message, /Duplicate variable/);
});

test("strict mode fails unknown populated API keys", async () => {
  const result = await run("UNKNOWN_API_KEY=real-looking-value\n", "--syntax-only", "--strict", "--json");

  assert.equal(result.status, 1);
  const output = JSON.parse(result.stdout);
  assert.equal(output.results[0].status, "skipped");
});

test("placeholder values are not sent to the network", async () => {
  const result = await run("MISTRAL_API_KEY=replace-me\n", "--json");

  assert.equal(result.status, 0, result.stderr);
  const output = JSON.parse(result.stdout);
  assert.equal(output.results[0].status, "empty");
});
