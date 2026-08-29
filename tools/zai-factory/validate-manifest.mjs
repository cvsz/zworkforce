import { readdir, readFile } from "node:fs/promises";
import { join } from "node:path";

const root = new URL("./templates/", import.meta.url);

function fail(message) {
  throw new Error(message);
}

function validatePath(path) {
  if (typeof path !== "string" || !path || path.startsWith("/") || path.includes("..")) fail("template file path is unsafe");
}

export function validateTemplateManifest(manifest) {
  for (const field of ["id", "name", "version", "owner", "files"]) {
    if (!manifest[field]) fail(`template manifest missing ${field}`);
  }
  if (!Array.isArray(manifest.files) || manifest.files.length === 0) fail("template manifest requires files");
  for (const file of manifest.files) {
    validatePath(file.path);
    if (file.owner !== "generator") fail("generated files must declare generator ownership");
  }
  for (const pattern of manifest.prohibited || []) {
    if (/secret|token|password/i.test(pattern)) fail("prohibited patterns must not encode real secrets");
  }
  return manifest;
}

export async function loadTemplateManifests() {
  const dirs = await readdir(root, { withFileTypes: true });
  const manifests = [];
  for (const dir of dirs.filter((entry) => entry.isDirectory())) {
    const manifest = JSON.parse(await readFile(new URL(`${dir.name}/template.json`, root), "utf8"));
    manifests.push(validateTemplateManifest(manifest));
  }
  return manifests;
}

if (process.argv[1] === new URL(import.meta.url).pathname) {
  const manifests = await loadTemplateManifests();
  console.log(JSON.stringify({ templates: manifests.map((item) => item.id), count: manifests.length }));
}
