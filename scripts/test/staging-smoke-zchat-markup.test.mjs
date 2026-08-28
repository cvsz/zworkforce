import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

const html = await readFile(new URL("../../apps/zchat/public/index.html", import.meta.url), "utf8");
const css = await readFile(new URL("../../apps/zchat/public/styles.css", import.meta.url), "utf8");

test("zchat smoke markup exposes the semantic main region", () => {
  assert.match(html, /<html lang="en">/);
  assert.match(html, /<main\b/);
  assert.match(html, /role="status"/);
  assert.match(html, /aria-live="polite"/);
  assert.match(html, /<label for="model">/);
  assert.match(html, /<label for="prompt">/);
});

test("zchat smoke markup retains the responsive breakpoint used by deployed checks", () => {
  assert.match(css, /@media\s*\(max-width:\s*720px\)/);
});
