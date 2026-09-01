// Guards the deduped OAuth client: values resolve from env vars consistently across sources.
import { describe, it, expect } from "vitest";

describe("oauth client (env-var sourced)", () => {
  it("shared source resolves from env vars when set", async () => {
    process.env.ANTIGRAVITY_OAUTH_CLIENT_ID = "test-ag-id";
    process.env.ANTIGRAVITY_OAUTH_CLIENT_SECRET = "test-ag-secret";
    process.env.GOOGLE_OAUTH_CLIENT_ID = "test-google-id";
    process.env.GOOGLE_OAUTH_CLIENT_SECRET = "test-google-secret";
    const { ANTIGRAVITY_OAUTH_CLIENT, GOOGLE_OAUTH_CLIENT } = await import("../../open-sse/providers/shared.js");
    expect(ANTIGRAVITY_OAUTH_CLIENT.clientId).toBe(process.env.ANTIGRAVITY_OAUTH_CLIENT_ID);
    expect(ANTIGRAVITY_OAUTH_CLIENT.clientSecret).toBe(process.env.ANTIGRAVITY_OAUTH_CLIENT_SECRET);
    expect(GOOGLE_OAUTH_CLIENT.clientId).toBe(process.env.GOOGLE_OAUTH_CLIENT_ID);
    expect(GOOGLE_OAUTH_CLIENT.clientSecret).toBe(process.env.GOOGLE_OAUTH_CLIENT_SECRET);
  });

  it("registry transport resolves from env vars when set", async () => {
    process.env.ANTIGRAVITY_OAUTH_CLIENT_ID = "test-ag-id";
    process.env.ANTIGRAVITY_OAUTH_CLIENT_SECRET = "test-ag-secret";
    process.env.GOOGLE_OAUTH_CLIENT_ID = "test-google-id";
    process.env.GOOGLE_OAUTH_CLIENT_SECRET = "test-google-secret";
    const ag = (await import("../../open-sse/providers/registry/antigravity.js")).default;
    const gemini = (await import("../../open-sse/providers/registry/gemini.js")).default;
    const gc = (await import("../../open-sse/providers/registry/gemini-cli.js")).default;
    expect(ag.transport.clientId).toBe(process.env.ANTIGRAVITY_OAUTH_CLIENT_ID);
    expect(ag.transport.clientSecret).toBe(process.env.ANTIGRAVITY_OAUTH_CLIENT_SECRET);
    expect(gemini.transport.clientId).toBe(process.env.GOOGLE_OAUTH_CLIENT_ID);
    expect(gemini.transport.clientSecret).toBe(process.env.GOOGLE_OAUTH_CLIENT_SECRET);
    expect(gc.transport.clientId).toBe(process.env.GOOGLE_OAUTH_CLIENT_ID);
    expect(gc.transport.clientSecret).toBe(process.env.GOOGLE_OAUTH_CLIENT_SECRET);
  });

  // Guard: oauth.js must spread shared clients + derive from registry (PROVIDER_OAUTH).
  it("src oauth.js imports shared client + keeps full shape", async () => {
    const { readFileSync } = await import("node:fs");
    const { fileURLToPath } = await import("node:url");
    const { dirname, join } = await import("node:path");
    const here = dirname(fileURLToPath(import.meta.url));
    const src = readFileSync(join(here, "../../src/lib/oauth/constants/oauth.js"), "utf8");
    expect(src).toContain('import { ANTIGRAVITY_OAUTH_CLIENT, GOOGLE_OAUTH_CLIENT } from "open-sse/providers/shared.js"');
    expect(src).toContain("...ANTIGRAVITY_OAUTH_CLIENT");
    expect(src).toContain("...GOOGLE_OAUTH_CLIENT");
    expect(src).toContain('PROVIDER_OAUTH["antigravity"]');
    expect(src).toContain('PROVIDER_OAUTH["gemini-cli"]');
  });
});
