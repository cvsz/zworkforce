/**
 * Tests for mention classification and sentiment normalization.
 * @see exec-planing.md Phase 5 — M07 Monitoring, Sentiment
 */

const { describe, it } = require("node:test");
const assert = require("node:assert/strict");

const {
  classifyMention,
  normalizeSentiment,
} = require("../src/domain/monitoring.js");

describe("classifyMention", () => {
  it("classifies a question correctly", () => {
    const r = classifyMention({
      text: "How do I get started with your product?",
    });
    assert.equal(r.category, "question");
    assert.ok(r.confidence > 0.5);
  });

  it("classifies a complaint correctly", () => {
    const r = classifyMention({
      text: "This is terrible, the product is broken and I want a refund!",
    });
    assert.equal(r.category, "complaint");
    assert.ok(r.confidence > 0.5);
  });

  it("classifies praise correctly", () => {
    const r = classifyMention({
      text: "Amazing product, I absolutely love it! Thank you!",
    });
    assert.equal(r.category, "praise");
    assert.ok(r.confidence > 0.5);
  });

  it("classifies a lead correctly", () => {
    const r = classifyMention({
      text: "How much does the enterprise plan cost? Interested in a demo.",
    });
    assert.equal(r.category, "lead");
    assert.ok(r.confidence > 0.5);
  });

  it("returns spam for empty text", () => {
    const r = classifyMention({ text: "" });
    assert.equal(r.category, "spam");
  });

  it("returns a confidence between 0 and 1", () => {
    const r = classifyMention({ text: "Great product!" });
    assert.ok(r.confidence >= 0 && r.confidence <= 1);
  });

  it("returns valid category string", () => {
    const valid = ["question", "complaint", "praise", "spam", "lead"];
    const r = classifyMention({ text: "hello world" });
    assert.ok(valid.includes(r.category));
  });
});

describe("normalizeSentiment", () => {
  it("returns 50 for null", () => {
    assert.equal(normalizeSentiment(null), 50);
  });

  it("returns 50 for undefined", () => {
    assert.equal(normalizeSentiment(undefined), 50);
  });

  it("returns integer 0-100 as-is", () => {
    assert.equal(normalizeSentiment(75), 75);
    assert.equal(normalizeSentiment(2), 2);
    assert.equal(normalizeSentiment(100), 100);
  });

  it("maps -1 to 0", () => {
    assert.equal(normalizeSentiment(-1), 0);
  });

  it("maps 1 to 100", () => {
    assert.equal(normalizeSentiment(1), 100);
  });

  it("maps 0.1 to 55", () => {
    assert.equal(normalizeSentiment(0.1), 55);
  });

  it("maps 0.5 to 75", () => {
    assert.equal(normalizeSentiment(0.5), 75);
  });
});
