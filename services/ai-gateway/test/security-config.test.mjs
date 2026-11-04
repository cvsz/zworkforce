import assert from "node:assert/strict";
import test from "node:test";

import { corsConfig, rateLimitConfig, resolveTenantId } from "../security-config.mjs";

function corsAllowed(config, origin) {
  return new Promise((resolve, reject) => config.origin(origin, (error, allowed) => error ? reject(error) : resolve(allowed)));
}

test("rate limiting defaults safely and validates overrides", () => {
  assert.equal(rateLimitConfig({}).windowMs, 60_000);
  assert.equal(rateLimitConfig({}).limit, 60);
  assert.equal(rateLimitConfig({ AI_GATEWAY_RATE_LIMIT_MAX: "2" }).limit, 2);
  assert.throws(() => rateLimitConfig({ AI_GATEWAY_RATE_LIMIT_MAX: "0" }), /positive integer/);
});

test("rate limiting keyGenerator scopes quotas per authenticated tenant", () => {
  const cfg = rateLimitConfig({});
  assert.equal(cfg.keyGenerator({ headers: { "x-authenticated-tenant": "tenant-alpha" }, ip: "10.0.0.1" }), "tenant:tenant-alpha");
  assert.equal(cfg.keyGenerator({ headers: { "x-tenant-id": "tenant-beta" }, ip: "10.0.0.1" }), "tenant:tenant-beta");
  assert.equal(cfg.keyGenerator({ headers: {}, ip: "10.0.0.1" }), "10.0.0.1");
});

test("resolveTenantId enforces strict tenant requirement and rejects invalid identifiers", () => {
  assert.deepEqual(resolveTenantId({ headers: {} }, { AI_GATEWAY_REQUIRE_TENANT: "true" }), {
    ok: false,
    status: 403,
    code: "TENANT_REQUIRED",
    message: "Authenticated tenant identity is required",
  });
  assert.deepEqual(resolveTenantId({ headers: { "x-tenant-id": "../bad/tenant" } }, {}), {
    ok: false,
    status: 400,
    code: "INVALID_TENANT_ID",
    message: "Tenant identifier is invalid",
  });
  assert.deepEqual(resolveTenantId({ headers: { "x-authenticated-tenant": "acme_prod-1" } }, { AI_GATEWAY_REQUIRE_TENANT: "true" }), {
    ok: true,
    tenantId: "acme_prod-1",
    explicit: true,
  });
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
