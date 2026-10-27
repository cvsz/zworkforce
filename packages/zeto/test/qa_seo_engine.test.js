"use strict";

const test = require("node:test");
const assert = require("node:assert/strict");
const { QaEngine } = require("../src/domain/qa_engine");
const { SeoEngine, PLATFORM_LIMITS } = require("../src/domain/seo_engine");

test("QaEngine scores compliant draft with high score", () => {
  const engine = new QaEngine();
  const draft = {
    text: "🚀 Transform your business with ZeaZ and zWorkforce AI automation!\n\nOur smart workflows save 20 hours a week. Click the link to get started today!\n#ZeaZ #zWorkforce",
  };

  const result = engine.scoreDraft(draft);
  assert.equal(result.passed, true);
  assert(result.score >= 90);
});

test("QaEngine flags weak draft and executes auto-remediation", () => {
  const engine = new QaEngine();
  const poorDraft = {
    text: "Buy this right now. It is a 100% guarantee miracle item.",
  };

  const evalBefore = engine.scoreDraft(poorDraft);
  assert.equal(evalBefore.passed, false);

  const remediation = engine.autoRemediate(poorDraft);
  assert.equal(remediation.remediated, true);
  assert.equal(remediation.text.includes("100% guarantee"), false);
  assert.equal(remediation.text.includes("proven solution"), true);
  assert(remediation.score > evalBefore.score);
});

test("SeoEngine calculates keyword density accurately", () => {
  const seo = new SeoEngine();
  const text =
    "AI automation with zWorkforce helps AI teams automate AI workflows";
  const density = seo.calculateKeywordDensity(text, "ai");
  assert(density > 0.2);
});

test("SeoEngine enforces platform limits and hashtag injection", () => {
  const seo = new SeoEngine();
  const baseText = "Check out our new summer fashion arrivals.";
  const optimized = seo.injectKeywordsAndHashtags(
    baseText,
    "tiktok",
    ["fashion", "linen"],
    ["#SummerVibes", "#OOTD"],
  );

  assert.equal(optimized.includes("#SummerVibes"), true);
  assert.equal(optimized.includes("#OOTD"), true);
  assert.equal((optimized.match(/fashion/gi) || []).length, 1);
  assert.equal(optimized.includes("linen"), true);

  const scoreResult = seo.scorePlatformSeo(optimized, "tiktok", ["fashion"]);
  assert.equal(scoreResult.hashtagCount, 2);
  assert(scoreResult.score >= 70);
});

test("SeoEngine does not exceed the platform text limit when adding keywords or hashtags", () => {
  const seo = new SeoEngine();
  const baseText = "x".repeat(PLATFORM_LIMITS.tiktok.maxLen);

  const optimized = seo.injectKeywordsAndHashtags(
    baseText,
    "tiktok",
    ["linen"],
    ["#OOTD"],
  );

  assert.equal(optimized, baseText);
  assert(optimized.length <= PLATFORM_LIMITS.tiktok.maxLen);
});
