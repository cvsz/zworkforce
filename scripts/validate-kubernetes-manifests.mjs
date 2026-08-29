import { execFileSync } from "node:child_process";

const args = process.argv.slice(2);
const overlay = args.includes("--overlay") ? args[args.indexOf("--overlay") + 1] : "infrastructure/kubernetes/overlays/production";
if (!overlay || overlay.startsWith("--")) throw new Error("--overlay requires a path");

const rendered = execFileSync("kubectl", ["kustomize", overlay], { encoding: "utf8" });
const images = [...rendered.matchAll(/^\s+image:\s+(\S+)/gm)].map((match) => match[1]);
if (images.length === 0) throw new Error("No workload images were rendered");

const invalid = images.filter((image) =>
  image.includes("REPLACE_WITH") ||
  image.endsWith(":latest") ||
  image.endsWith(":dev") ||
  !/@sha256:[a-f0-9]{64}$/.test(image),
);

if (invalid.length) {
  console.error(JSON.stringify({ overlay, invalid }, null, 2));
  process.exit(1);
}

console.log(`Validated ${images.length} immutable Kubernetes images in ${overlay}`);
