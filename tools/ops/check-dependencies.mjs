import { readdir, readFile } from "node:fs/promises";
import { join } from "node:path";

const roots = ["apps", "services", "packages", "tools"];
const forbidden = new Set(["event-stream", "flatmap-stream"]);

async function packageFiles(root) {
  const out = [];
  async function walk(dir) {
    let entries = [];
    try { entries = await readdir(dir, { withFileTypes: true }); } catch { return; }
    for (const entry of entries) {
      if (entry.name === "node_modules" || entry.name.startsWith(".")) continue;
      const path = join(dir, entry.name);
      if (entry.isDirectory()) await walk(path);
      if (entry.isFile() && entry.name === "package.json") out.push(path);
    }
  }
  await walk(root);
  return out;
}

const files = (await Promise.all(roots.map(packageFiles))).flat();
const findings = [];
for (const file of files) {
  const pkg = JSON.parse(await readFile(file, "utf8"));
  for (const section of ["dependencies", "devDependencies", "optionalDependencies"]) {
    for (const name of Object.keys(pkg[section] || {})) {
      if (forbidden.has(name)) findings.push({ file, section, name });
    }
  }
}
if (findings.length) {
  console.error(JSON.stringify({ forbidden_dependencies: findings }, null, 2));
  process.exit(1);
}
console.log(JSON.stringify({ checked_package_files: files.length, forbidden_dependencies: 0 }));
