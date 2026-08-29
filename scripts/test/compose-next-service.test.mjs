import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

const compose = await readFile(new URL("../../compose.yml", import.meta.url), "utf8");
const dockerfile = await readFile(new URL("../../deploy/docker/next-service.Dockerfile", import.meta.url), "utf8");

test("agent-control-panel uses a dedicated Next.js Dockerfile in compose", () => {
  assert.match(compose, /agent-control-panel:/);
  assert.match(compose, /dockerfile:\s*deploy\/docker\/next-service\.Dockerfile/);
  assert.match(compose, /SERVICE_PATH:\s*apps\/agent-control-panel/);
});

test("next service image installs, builds, and prunes dependencies before start", () => {
  assert.match(dockerfile, /npm install --include=dev --legacy-peer-deps --no-audit --no-fund/);
  assert.match(dockerfile, /npm run build/);
  assert.match(dockerfile, /npm prune --omit=dev --legacy-peer-deps/);
  assert.match(dockerfile, /NEXT_TELEMETRY_DISABLED=1/);
});
