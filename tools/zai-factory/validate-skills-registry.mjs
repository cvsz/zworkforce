import { readFile } from "node:fs/promises";

const path = process.argv[2] || new URL("./skills-registry.json", import.meta.url);
const registry = JSON.parse(await readFile(path, "utf8"));
if (registry.version !== 1 || !Array.isArray(registry.curated_skills)) {
  throw new Error("Invalid skill registry format");
}
const ids = new Set();
const paths = new Set();
for (const skill of registry.curated_skills) {
  if (!/^[a-z0-9-]+$/.test(skill.id || "")) throw new Error("Invalid skill id");
  if (ids.has(skill.id)) throw new Error("Duplicate skill id: " + skill.id);
  if (!skill.source_path?.endsWith("/SKILL.md")) throw new Error("Invalid source skill path");
  if (paths.has(skill.source_path)) throw new Error("Duplicate source path: " + skill.source_path);
  ids.add(skill.id);
  paths.add(skill.source_path);
}
if (typeof registry.import_policy !== "string" || !registry.import_policy.trim()) {
  throw new Error("Import policy is required");
}
console.log("Validated " + ids.size + " curated skills");
