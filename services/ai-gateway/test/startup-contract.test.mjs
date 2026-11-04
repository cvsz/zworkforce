import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { test } from "node:test";

const packageJson = JSON.parse(await readFile(new URL("../package.json", import.meta.url), "utf8"));
const entrypoint = await readFile(new URL("../index.js", import.meta.url), "utf8");
const dockerfile = await readFile(new URL("../../../deploy/docker/ai-gateway.Dockerfile", import.meta.url), "utf8");
const containerWorkflow = await readFile(new URL("../../../packages/zarvis/.github/workflows/container-images.yml", import.meta.url), "utf8");

test("container start command resolves to the Gateway entrypoint", () => {
  assert.equal(packageJson.scripts.start, "node index.js");
  assert.equal(packageJson.main, "index.js");
  assert.match(dockerfile, /npm ci --omit=dev --no-audit/);
  assert.match(dockerfile, /package-lock\.json/);
  assert.match(containerWorkflow, /file:\s*deploy\/docker\/ai-gateway\.Dockerfile/);
  assert.match(dockerfile, /CMD \["npm", "start"\]/);
});

test("entrypoint uses the Node runtime fetch implementation", () => {
  assert.doesNotMatch(entrypoint, /from ['"]node-fetch['"]/);
  assert.doesNotMatch(JSON.stringify(packageJson.dependencies), /node-fetch/);
});

test("health and authentication failure contracts remain fail closed", () => {
  assert.match(entrypoint, /app\.get\(['"]\/health['"]/);
  assert.match(entrypoint, /Z_PLATFORM_RELEASE_SHA/);
  assert.match(entrypoint, /release_sha: releaseSha/);
  assert.match(entrypoint, /if \(!token \|\| token !== process\.env\.Z_PLATFORM_SERVICE_TOKEN\)/);
  assert.match(entrypoint, /status\(401\)\.json/);
  assert.match(entrypoint, /resolveTenantId\(req,\s*process\.env\)/);
  assert.match(entrypoint, /selectProviderKey\(redisClient,\s*provider,\s*req\.tenantId\)/);
  assert.match(entrypoint, /req\.headers\.authorization/);
  assert.match(entrypoint, /req\.headers\["x-tenant-assertion-signature"\]/);
  assert.match(entrypoint, /censor: ['"]\[REDACTED\]['"]/);
});
