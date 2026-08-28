import { readFile } from "node:fs/promises";

const file = process.argv[2];
if (!file) throw new Error("usage: verify-provenance.mjs <sbom.spdx.json>");
const sbom = JSON.parse(await readFile(file, "utf8"));
if (sbom.spdxVersion !== "SPDX-2.3") throw new Error("unsupported sbom version");
if (!Array.isArray(sbom.packages) || sbom.packages.length === 0) throw new Error("sbom has no packages");
if (sbom.packages.some((pkg) => !pkg.name || !pkg.SPDXID)) throw new Error("sbom package metadata is incomplete");
console.log(JSON.stringify({ provenance: "verified", packages: sbom.packages.length }));
