import assert from "node:assert/strict";
import test from "node:test";

import { corsConfig, rateLimitConfig } from "../security-config.mjs";

function corsAllowed(config, origin) {
  return new Promise((resolve, reject) => config.origin(origin, (error, allowed) => error ? reject(error) : resolve(allowed)));
}

test("rate limiting defaults safely and validates overrides", () => {
  assert.equal(rateLimitConfig({}).windowMs, 60_000);
  assert.equal(rateLimitConfig({}).limit, 60);
  assert.equal(rateLimitConfig({ AI_GATEWAY_RATE_LIMIT_MAX: "2" }).limit, 2);
  assert.throws(() => rateLimitConfig({ AI_GATEWAY_RATE_LIMIT_MAX: "0" }), /positive integer/);
});

test("CORS denies browser origins by default and allows exact configured origins", async () => {
  assert.equal(await corsAllowed(corsConfig(""), undefined), true);
  assert.equal(await corsAllowed(corsConfig(""), "https://attacker.example"), false);
  assert.equal(await corsAllowed(corsConfig("https://chat.example"), "https://chat.example"), true);
  assert.equal(await corsAllowed(corsConfig("https://chat.example"), "https://attacker.example"), false);
});

test("CORS rejects unsafe configuration", () => {
  assert.throws(() => corsConfig("*"), /wildcard/);
  assert.throws(() => corsConfig("https://user:pass@example.com"), /without credentials or paths/);
  assert.throws(() => corsConfig("https://example.com/path"), /without credentials or paths/);
});
