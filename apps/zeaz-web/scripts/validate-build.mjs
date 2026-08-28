import { readFile } from "node:fs/promises";
const source = await readFile(new URL("../src/index.js", import.meta.url), "utf8");
for (const marker of ["ZEAZ One", "data-lang=", "/api/early-access", "validateLeadPayload", "Privacy Policy", "นโยบายความเป็นส่วนตัว"]) {
  if (!source.includes(marker)) throw new Error(`Missing website marker: ${marker}`);
}
const config = JSON.parse(await readFile(new URL("../wrangler.template.json", import.meta.url), "utf8"));
if (config.name !== "zeaz-web" || config.d1_databases?.[0]?.binding !== "DB") throw new Error("Invalid Worker configuration");
console.log("ZEAZ web build validation passed");
