#!/usr/bin/env node
import { createHash } from "node:crypto";
import { mkdir, readFile, rm, writeFile } from "node:fs/promises";
import { chromium } from "@playwright/test";

const sha256 = (value) => createHash("sha256").update(value).digest("hex");

function assert(value, message) {
  if (!value) throw new Error(message);
}

function sanitizedUrl(value) {
  if (!value) return "";
  const url = new URL(value);
  assert(url.protocol === "https:", `browser evidence contains a non-HTTPS URL: ${url.origin}`);
  url.username = "";
  url.password = "";
  url.search = "";
  url.hash = "";
  return url.href;
}

export function sanitizeHar(har) {
  const entries = har?.log?.entries;
  assert(Array.isArray(entries) && entries.length > 0, "captured HAR has no entries");

  return {
    log: {
      version: "1.2",
      creator: { name: "z-platform-release-evidence", version: "1.0.0" },
      pages: Array.isArray(har.log.pages)
        ? har.log.pages.map((page) => ({
            startedDateTime: page.startedDateTime,
            id: page.id,
            title: "sanitized-page",
            pageTimings: page.pageTimings ?? {},
          }))
        : [],
      entries: entries.map((entry) => ({
        pageref: entry.pageref,
        startedDateTime: entry.startedDateTime,
        time: entry.time,
        request: {
          method: entry.request?.method,
          url: sanitizedUrl(entry.request?.url),
          httpVersion: entry.request?.httpVersion,
          headers: [],
          queryString: [],
          cookies: [],
          headersSize: entry.request?.headersSize ?? -1,
          bodySize: entry.request?.bodySize ?? -1,
        },
        response: {
          status: entry.response?.status,
          statusText: entry.response?.statusText,
          httpVersion: entry.response?.httpVersion,
          headers: [],
          cookies: [],
          content: {
            size: entry.response?.content?.size ?? 0,
            mimeType: entry.response?.content?.mimeType ?? "application/octet-stream",
          },
          redirectURL: "",
          headersSize: entry.response?.headersSize ?? -1,
          bodySize: entry.response?.bodySize ?? -1,
        },
        cache: {},
        timings: entry.timings ?? {},
      })),
    },
  };
}

export async function captureBrowserEvidence({
  releaseSha = process.env.RELEASE_SHA,
  baseUrl = process.env.ZCHAT_STAGING_URL,
  accessClientId = process.env.STAGING_CF_ACCESS_CLIENT_ID,
  accessClientSecret = process.env.STAGING_CF_ACCESS_CLIENT_SECRET,
  outputDir = "artifacts/browser",
} = {}) {
  assert(/^[0-9a-f]{40}$/.test(releaseSha ?? ""), "RELEASE_SHA must be a full lowercase SHA");
  const origin = new URL(baseUrl ?? "");
  assert(origin.protocol === "https:" && origin.pathname === "/" && !origin.search && !origin.hash,
    "ZCHAT_STAGING_URL must be an HTTPS origin");
  assert(Boolean(accessClientId) === Boolean(accessClientSecret),
    "Cloudflare Access service-token credentials must be provided as a pair");

  await mkdir(outputDir, { recursive: true, mode: 0o700 });
  const rawHarPath = `/tmp/zchat-browser-${process.pid}.har`;
  const headers = accessClientId
    ? { "CF-Access-Client-Id": accessClientId, "CF-Access-Client-Secret": accessClientSecret }
    : {};
  let browser;
  let context;
  try {
    browser = await chromium.launch({ headless: true });
    context = await browser.newContext({
      extraHTTPHeaders: headers,
      recordHar: { path: rawHarPath, content: "omit", mode: "full" },
      viewport: { width: 1440, height: 900 },
    });
    const page = await context.newPage();
    const navigation = await page.goto(origin.href, { waitUntil: "networkidle", timeout: 45_000 });
    assert(navigation?.status() === 200, `ZChat navigation returned HTTP ${navigation?.status() ?? "unknown"}`);
    await page.locator("main").waitFor({ state: "visible", timeout: 15_000 });

    const healthResponse = await context.request.get(new URL("/health/live", origin).href);
    assert(healthResponse.status() === 200, `ZChat liveness returned HTTP ${healthResponse.status()}`);
    const health = await healthResponse.json();
    assert(health.release_sha === releaseSha,
      `deployed ZChat release mismatch: expected ${releaseSha}, received ${health.release_sha ?? "missing"}`);

    const bundleResponse = await context.request.get(new URL("/app.js", origin).href);
    assert(bundleResponse.status() === 200, `ZChat bundle returned HTTP ${bundleResponse.status()}`);
    const bundle = await bundleResponse.body();
    assert(bundle.byteLength >= 1024, "deployed ZChat bundle is unexpectedly small");
    await writeFile(`${outputDir}/app.js`, bundle, { mode: 0o600 });
    await page.screenshot({ path: `${outputDir}/zchat.png`, fullPage: true });

    await context.close();
    context = undefined;
    const sanitizedHar = sanitizeHar(JSON.parse(await readFile(rawHarPath, "utf8")));
    const harText = `${JSON.stringify(sanitizedHar, null, 2)}\n`;
    await writeFile(`${outputDir}/session.har`, harText, { mode: 0o600 });
    const evidence = {
      schemaVersion: "1.0.0",
      releaseSha,
      capturedAt: new Date().toISOString(),
      origin: origin.origin,
      browser: "chromium",
      bundleSha256: sha256(bundle),
      harSha256: sha256(harText),
      harEntries: sanitizedHar.log.entries.length,
      runtimeReleaseVerified: true,
      result: "VERIFIED",
    };
    await writeFile(`${outputDir}/browser-evidence.json`, `${JSON.stringify(evidence, null, 2)}\n`, { mode: 0o600 });
    return evidence;
  } finally {
    if (context) await context.close().catch(() => {});
    if (browser) await browser.close().catch(() => {});
    await rm(rawHarPath, { force: true });
  }
}

async function main() {
  const evidence = await captureBrowserEvidence();
  console.log(JSON.stringify(evidence));
}

if (process.argv[1] && import.meta.url === new URL(`file://${process.argv[1]}`).href) {
  main().catch((error) => {
    console.error(`browser evidence capture failed: ${error.message}`);
    process.exitCode = 1;
  });
}
