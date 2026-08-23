import assert from "node:assert/strict";
import { createServer } from "node:http";
import { once } from "node:events";
import { spawn } from "node:child_process";
import test from "node:test";

function startFixtureServer() {
  const server = createServer((request, response) => {
    const path = new URL(request.url ?? "/", "http://fixture.test").pathname;
    const titles = {
      "/en": "zTTShop — TikTok Shop API Client for PHP",
      "/th": "zTTShop — PHP SDK สำหรับ TikTok Shop API",
      "/en/privacy": "Privacy Policy — zTTShop",
      "/th/privacy": "นโยบายความเป็นส่วนตัว — zTTShop",
      "/en/terms": "Terms of Use — zTTShop",
      "/th/terms": "ข้อกำหนดการใช้งาน — zTTShop",
    };
    const status = path === "/" ? 307 : 200;
    const page = path === "/"
      ? "<meta http-equiv=\"refresh\" content=\"0;url=/en\">"
      : "<html lang=\"" + (path.startsWith("/th") ? "th" : "en") +
        "\"><head><title>" + (titles[path] ?? "zTTShop") +
        "</title></head><body>zTTShop</body></html>";

    response.writeHead(status, {
      ...(status === 200 ? { "content-type": "text/html; charset=utf-8" } : {}),
      ...(status === 307 ? { location: "/en" } : {}),
    });
    response.end(page);
  });

  server.listen(0, "127.0.0.1");
  return once(server, "listening").then(() => ({
    server,
    url: "http://127.0.0.1:" + server.address().port,
  }));
}

function runSmoke(url, extraEnv = {}) {
  return new Promise((resolve, reject) => {
    const child = spawn(process.execPath, ["scripts/live-smoke.mjs"], {
      cwd: new URL("..", import.meta.url),
      env: { ...process.env, ZTTSHOP_LIVE_URL: url, ...extraEnv },
      stdio: ["ignore", "pipe", "pipe"],
    });
    let output = "";
    child.stdout.on("data", (chunk) => { output += chunk; });
    child.stderr.on("data", (chunk) => { output += chunk; });
    child.on("error", reject);
    child.on("close", (code) => resolve({ code, output }));
  });
}

test("live smoke checks the localized public route matrix", async () => {
  const fixture = await startFixtureServer();

  try {
    const result = await runSmoke(fixture.url);

    assert.equal(result.code, 0, result.output);
    assert.match(result.output, /Live site smoke checks passed/);
  } finally {
    fixture.server.close();
  }
});

test("live smoke fails clearly when the target URL is missing", async () => {
  const result = await runSmoke("");

  assert.equal(result.code, 1);
  assert.match(result.output, /ZTTSHOP_LIVE_URL is required/);
});
