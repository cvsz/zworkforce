import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { fileURLToPath } from "node:url";
import test from "node:test";

const workflowPaths = {
  "readiness-tooling": fileURLToPath(new URL("../../.github/workflows/readiness-tooling.yml", import.meta.url)),
  zctl: fileURLToPath(new URL("../../.github/workflows/zctl.yml", import.meta.url)),
};

for (const [name, path] of Object.entries(workflowPaths)) {
  test(`${name} runs its unprivileged validation on GitHub-hosted capacity`, async () => {
    const workflow = await readFile(path, "utf8");

    assert.match(workflow, /runs-on:\s*ubuntu-latest/);
    assert.doesNotMatch(workflow, /runs-on:\s*self-hosted/);
  });
}
