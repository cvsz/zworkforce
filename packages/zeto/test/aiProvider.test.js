/**
 * Tests for AI provider base class and registry.
 * @see exec-planing.md Phase 2 — ProMeta Prompt Compiler + M01-M05
 */

const { describe, it } = require("node:test");
const assert = require("node:assert/strict");
const { FakeAIProvider } = require("../src/providers/ai/aiProvider.js");
const {
  AIProviderRegistry,
  DuplicateProviderError,
  ProviderNotFoundError,
} = require("../src/providers/ai/aiProviderRegistry.js");

describe("FakeAIProvider", () => {
  it("returns generation result for image", async () => {
    const p = new FakeAIProvider({ types: ["image"] });
    const result = await p.generate({ type: "image", prompt: "sunset" });
    assert.equal(result.type, "image");
    assert.equal(result.providerId, "fake");
    assert.ok(result.metadata.promptHash);
    assert.ok(result.metadata.latencyMs >= 0);
  });

  it("throws when raiseOn is set", async () => {
    const p = new FakeAIProvider({ raiseOn: "backend down" });
    await assert.rejects(
      () => p.generate({ type: "text", prompt: "hi" }),
      /backend down/,
    );
  });

  it("reports healthy status", async () => {
    const status = await new FakeAIProvider({ healthy: true }).health();
    assert.equal(status.healthy, true);
    assert.equal(status.error, null);
  });

  it("reports unhealthy status without credentials", async () => {
    const status = await new FakeAIProvider({ healthy: false }).health();
    assert.equal(status.healthy, false);
    assert.ok(status.error);
    assert.ok(!status.error.includes("token"));
    assert.ok(!status.error.includes("key"));
  });

  it("capability locality is local", () => {
    assert.equal(new FakeAIProvider().capability.locality, "local");
  });
});

describe("AIProviderRegistry", () => {
  function makeRegistry(...providers) {
    const r = new AIProviderRegistry();
    for (const p of providers) r.register(p);
    return r;
  }

  it("registers and retrieves by id", () => {
    const p = new FakeAIProvider({ id: "myProvider" });
    const r = makeRegistry(p);
    assert.strictEqual(r.get("myProvider"), p);
  });

  it("throws DuplicateProviderError on collision", () => {
    const r = new AIProviderRegistry();
    r.register(new FakeAIProvider({ id: "dup" }));
    assert.throws(
      () => r.register(new FakeAIProvider({ id: "dup" })),
      DuplicateProviderError,
    );
  });

  it("throws ProviderNotFoundError for missing id", () => {
    const r = new AIProviderRegistry();
    assert.throws(() => r.get("missing"), ProviderNotFoundError);
  });

  it("findByType returns matching providers", () => {
    const img = new FakeAIProvider({ id: "img", types: ["image"] });
    const txt = new FakeAIProvider({ id: "txt", types: ["text"] });
    const both = new FakeAIProvider({ id: "both", types: ["image", "text"] });
    const r = makeRegistry(img, txt, both);
    const results = r.findByType("image");
    const ids = results.map((p) => p.capability.id).sort();
    assert.deepEqual(ids, ["both", "img"]);
  });

  it("list returns sorted ids", () => {
    const r = makeRegistry(
      new FakeAIProvider({ id: "z" }),
      new FakeAIProvider({ id: "a" }),
    );
    assert.deepEqual(r.list(), ["a", "z"]);
  });

  it("healthSummary never exposes credentials", async () => {
    const r = makeRegistry(
      new FakeAIProvider({ id: "h1", healthy: true }),
      new FakeAIProvider({ id: "h2", healthy: false }),
    );
    const summary = await r.healthSummary();
    const summaryStr = JSON.stringify(summary);
    assert.ok(!summaryStr.includes("token"));
    assert.ok(!summaryStr.includes("secret"));
    assert.ok(!summaryStr.includes("key"));
    assert.equal(summary.find((s) => s.providerId === "h1").healthy, true);
    assert.equal(summary.find((s) => s.providerId === "h2").healthy, false);
  });
});
