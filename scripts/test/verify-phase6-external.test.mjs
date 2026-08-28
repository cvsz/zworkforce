import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import test from "node:test";

import { verifyAlert, verifyUpload } from "../verify-phase6-external.mjs";

function withEnvironment(values, fn) {
  const previous = Object.fromEntries(Object.keys(values).map((name) => [name, process.env[name]]));
  Object.assign(process.env, values);
  return Promise.resolve().then(fn).finally(() => {
    for (const [name, value] of Object.entries(previous)) value === undefined ? delete process.env[name] : process.env[name] = value;
  });
}

test("verifies an alert using the same delivery marker", async () => {
  const originalFetch = global.fetch;
  let marker;
  global.fetch = async (url, init) => {
    if (init?.method === "POST") {
      marker = JSON.parse(init.body).marker;
      return Response.json({ marker, delivered: true, deliveredAt: 1 });
    }
    assert.equal(new URL(url).searchParams.get("marker"), marker);
    return Response.json({ marker, delivered: true, deliveredAt: 2 });
  };
  try {
    const result = await withEnvironment({ STAGING_BEARER_TOKEN: "token", ALERT_TEST_URL: "https://api6.zeaz.dev/alerts/test", ALERT_DELIVERY_STATUS_URL: "https://api6.zeaz.dev/alerts/status" }, verifyAlert);
    assert.equal(result.status, "verified");
    assert.equal(result.markerHash.length, 64);
  } finally { global.fetch = originalFetch; }
});

test("verifies upload integrity and external request evidence", async () => {
  const originalFetch = global.fetch;
  global.fetch = async (_url, init) => {
    const content = Buffer.from(await init.body.get("file").arrayBuffer());
    return Response.json({ status: "verified", provider: "nvidia", requestId: "request-1", size: content.length, sha256: createHash("sha256").update(content).digest("hex") });
  };
  try {
    const result = await withEnvironment({ STAGING_BEARER_TOKEN: "token", AI_UPLOAD_URL: "https://api6.zeaz.dev/ai/upload" }, verifyUpload);
    assert.equal(result.status, "verified");
    assert.equal(result.provider, "nvidia");
    assert.equal(result.requestIdHash.length, 64);
  } finally { global.fetch = originalFetch; }
});
