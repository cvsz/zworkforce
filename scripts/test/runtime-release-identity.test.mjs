import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

const read = (path) => readFile(new URL(`../../${path}`, import.meta.url), "utf8");

test("production deployment injects and verifies an immutable runtime release identity", async () => {
  const workflow = await read(".github/workflows/deploy-production.yml");

  assert.match(workflow, /--from-literal=Z_PLATFORM_RELEASE_SHA="\$RELEASE_SHA"/);
  for (const service of ["phase6-api", "zc-api", "ai-gateway", "zchat"]) {
    assert.match(workflow, new RegExp(`\\[${service.replace("-", "\\-")}\\]`));
  }
  assert.match(workflow, /jq -er '\.release_sha'/);
  assert.match(workflow, /actual" != "\$RELEASE_SHA/);
});

test("every deployed API health contract exposes release_sha", async () => {
  const sources = await Promise.all([
    read("services/phase6-api/app.py"),
    read("services/zc/app/api/v1/routes.py"),
    read("services/ai-gateway/index.js"),
    read("apps/zchat/server.mjs"),
  ]);

  for (const source of sources) {
    assert.match(source, /release_sha/);
    assert.match(source, /Z_PLATFORM_RELEASE_SHA/);
  }
});
