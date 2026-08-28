import { readdir, readFile, mkdir, writeFile } from "node:fs/promises";
const partsDir = new URL("../src.parts/", import.meta.url);
const files = (await readdir(partsDir)).filter((name) => /^part-\d+\.txt$/.test(name)).sort();
if (files.length < 5) throw new Error("Expected at least five ZEAZ Worker source parts");
const source = (await Promise.all(files.map((name) => readFile(new URL(name, partsDir), "utf8")))).join("");
await mkdir(new URL("../src/", import.meta.url), { recursive: true });
await writeFile(new URL("../src/index.js", import.meta.url), source);
console.log(`Assembled ZEAZ Worker source from ${files.length} parts (${source.length} characters)`);
