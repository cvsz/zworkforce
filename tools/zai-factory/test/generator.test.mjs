import assert from "node:assert/strict";
import { mkdtemp, readFile, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import test from "node:test";

import { generateProject } from "../generator.mjs";
import { loadTemplateManifests } from "../validate-manifest.mjs";

test("template manifests declare owned safe generated files", async () => {
  const manifests = await loadTemplateManifests();
  assert.ok(manifests.some((manifest) => manifest.id === "node-service"));
  for (const manifest of manifests) {
    assert.ok(manifest.files.every((file) => file.owner === "generator"));
    assert.ok(manifest.prohibited.includes(".env"));
  }
});

test("generator writes reproducible project without secret-bearing files", async () => {
  const root = await mkdtemp(join(tmpdir(), "zai-factory-"));
  try {
    const manifest = (await loadTemplateManifests()).find((item) => item.id === "node-service");
    const result = await generateProject({ manifest, outputDir: root, values: { name: "demo-service" } });
    assert.deepEqual(result.files.map((file) => file.path).sort(), ["README.md", "package.json", "src/server.mjs"]);
    assert.match(await readFile(join(root, "README.md"), "utf8"), /No secrets/);
  } finally {
    await rm(root, { recursive: true, force: true });
  }
});
