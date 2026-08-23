import assert from "node:assert/strict";
import test from "node:test";

const developmentPreviewMeta =
  /<meta(?=[^>]*\bname=["']codex-preview["'])(?=[^>]*\bcontent=["']development["'])[^>]*>/i;

async function loadWorker() {
  const workerUrl = new URL("../dist/server/index.js", import.meta.url);
  workerUrl.searchParams.set("test", `${process.pid}-${Date.now()}`);
  return (await import(workerUrl.href)).default;
}

async function fetchPage(worker, path) {
  return worker.fetch(
    new Request(`http://localhost${path}?test=${process.pid}-${Date.now()}`, {
      headers: { accept: "text/html" },
    }),
    {
      ASSETS: {
        fetch: async () => new Response("Not found", { status: 404 }),
      },
    },
    {
      waitUntil() {},
      passThroughOnException() {},
    },
  );
}

test("legacy routes redirect to English localized routes", async () => {
  const worker = await loadWorker();

  for (const [path, destination] of [["/", "/en"], ["/privacy", "/en/privacy"], ["/terms", "/en/terms"]]) {
    const response = await fetchPage(worker, path);
    assert.equal(response.status, 307, path);
    assert.equal(new URL(response.headers.get("location") ?? "").pathname, destination);
  }
});

test("localized home pages render language metadata and primary copy", async () => {
  const worker = await loadWorker();

  for (const page of [
    { path: "/en", lang: "en", title: "zTTShop — TikTok Shop API Client for PHP", cta: "Get the quick start" },
    { path: "/th", lang: "th", title: "zTTShop — PHP SDK สำหรับ TikTok Shop API", cta: "ดู quick start" },
  ]) {
    const response = await fetchPage(worker, page.path);
    const body = await response.text();

    assert.equal(response.status, 200, page.path);
    assert.match(response.headers.get("content-type") ?? "", /^text\/html\b/i);
    assert.match(body, new RegExp(`<html[^>]*lang=["']${page.lang}["']`, "i"));
    assert.match(body, developmentPreviewMeta);
    assert.match(body, new RegExp(page.title.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")));
    assert.match(body, new RegExp(page.cta.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")));
  }
});

test("localized legal pages render both languages and anchored sections", async () => {
  const worker = await loadWorker();

  for (const page of [
    { path: "/en/privacy", lang: "en", title: "Privacy Policy", anchor: "overview" },
    { path: "/th/privacy", lang: "th", title: "นโยบายความเป็นส่วนตัว", anchor: "overview" },
    { path: "/en/terms", lang: "en", title: "Terms of Use", anchor: "acceptance" },
    { path: "/th/terms", lang: "th", title: "ข้อกำหนดการใช้งาน", anchor: "acceptance" },
  ]) {
    const response = await fetchPage(worker, page.path);
    const body = await response.text();

    assert.equal(response.status, 200, page.path);
    assert.match(body, new RegExp(`<html[^>]*lang=["']${page.lang}["']`, "i"));
    assert.match(body, new RegExp(`<h1[^>]*>${page.title}`));
    assert.match(body, new RegExp(`id=["']${page.anchor}["']`));
    assert.match(body, developmentPreviewMeta);
  }
});
