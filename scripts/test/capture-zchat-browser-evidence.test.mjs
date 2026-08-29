import assert from "node:assert/strict";
import test from "node:test";
import { sanitizeHar } from "../capture-zchat-browser-evidence.mjs";

test("sanitizeHar removes credentials, cookies, query strings, and response bodies", () => {
  const sensitiveMarker = "must-not-survive";
  const sanitized = sanitizeHar({
    log: {
      pages: [{
        startedDateTime: "2026-07-19T00:00:00Z",
        id: "page_1",
        title: `https://zchat-staging.zeaz.dev/?token=${sensitiveMarker}`,
        pageTimings: {},
      }],
      entries: [{
        pageref: "page_1",
        startedDateTime: "2026-07-19T00:00:00Z",
        time: 12,
        request: {
          method: "GET",
          url: `https://zchat-staging.zeaz.dev/api/models?token=${sensitiveMarker}`,
          headers: [{ name: "Authorization", value: `Bearer ${sensitiveMarker}` }],
          cookies: [{ name: "session", value: sensitiveMarker }],
          postData: { text: sensitiveMarker },
        },
        response: {
          status: 200,
          statusText: "OK",
          headers: [{ name: "Set-Cookie", value: sensitiveMarker }],
          cookies: [{ name: "session", value: sensitiveMarker }],
          content: { size: 10, mimeType: "application/json", text: sensitiveMarker },
          redirectURL: "",
        },
        timings: { wait: 12 },
      }],
    },
  });

  const serialized = JSON.stringify(sanitized);
  assert.equal(serialized.includes(sensitiveMarker), false);
  assert.equal(sanitized.log.entries[0].request.url, "https://zchat-staging.zeaz.dev/api/models");
  assert.deepEqual(sanitized.log.entries[0].request.headers, []);
  assert.deepEqual(sanitized.log.entries[0].response.headers, []);
  assert.equal("text" in sanitized.log.entries[0].response.content, false);
});

test("sanitizeHar rejects non-HTTPS traffic", () => {
  assert.throws(() => sanitizeHar({
    log: {
      entries: [{
        request: { url: "http://zchat-staging.zeaz.dev/" },
        response: { content: {} },
      }],
    },
  }), /non-HTTPS/);
});
