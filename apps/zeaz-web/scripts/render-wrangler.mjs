import { readFile, writeFile } from "node:fs/promises";
const id = process.env.ZEAZ_WEB_D1_DATABASE_ID?.trim();
if (!id || !/^[0-9a-f-]{36}$/i.test(id)) throw new Error("ZEAZ_WEB_D1_DATABASE_ID must be a D1 UUID");
const template = await readFile(new URL("../wrangler.template.json", import.meta.url), "utf8");
const output = template.replaceAll("__D1_DATABASE_ID__", id);
JSON.parse(output);
await writeFile(new URL("../wrangler.generated.jsonc", import.meta.url), output);
