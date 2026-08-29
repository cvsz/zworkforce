import assert from "node:assert/strict";
import test from "node:test";

import { httpProbe } from "../phase6-external-suite.mjs";

test("phase6 probes send JSON bodies with the expected content type", async () => {
  const originalFetch = global.fetch;
  let observed;
  global.fetch = async (_url, init) => {
    observed = init;
    return new Response("ok", { status: 200 });
  };
  try {
    const result = await httpProbe({
      id: "ai.streaming",
      url: "https://staging.zeaz.dev/v1/chat/completions",
      method: "POST",
      body: { model: "approved-model", stream: true },
      expectedStatus: 200,
    }, "token", new Set(["https://staging.zeaz.dev"]));
    assert.equal(result.status, "verified");
    assert.equal(observed.headers.Authorization, "Bearer token");
    assert.equal(observed.headers["Content-Type"], "application/json");
    assert.equal(observed.body, JSON.stringify({ model: "approved-model", stream: true }));
  } finally {
    global.fetch = originalFetch;
  }
});

test("phase6 probes send Cloudflare Access headers without returning credentials in evidence", async () => {
  const originalFetch = global.fetch;
  let observed;
  global.fetch = async (_url, init) => {
    observed = init;
    return new Response("ok", { status: 200 });
  };
  try {
    const result = await httpProbe(
      {
        id: "observability.dashboard",
        url: "https://staging.zeaz.dev/health",
        expectedStatus: 200,
      },
      "bearer-token",
      new Set(["https://staging.zeaz.dev"]),
      "access-client-id",
      "access-client-secret",
    );
    assert.equal(result.status, "verified");
    assert.equal(observed.headers["CF-Access-Client-Id"], "access-client-id");
    assert.equal(observed.headers["CF-Access-Client-Secret"], "access-client-secret");
    assert.equal(JSON.stringify(result).includes("access-client-secret"), false);
  } finally {
    global.fetch = originalFetch;
  }
});
