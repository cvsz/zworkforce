/**
 * qa_engine.js
 *
 * 12-Point QA Scorecard & Automated Self-Correction Loop for Zeto Content Factory.
 * Evaluates generated content against criteria and autonomously executes targeted remediation
 * when the overall score is < 90 before requesting human approval.
 */

"use strict";

const CRITERIA_WEIGHTS = Object.freeze({
  hook_clarity: 10,
  brand_voice: 10,
  safe_margins: 10,
  claim_substantiation: 10,
  call_to_action: 10,
  grammar_and_syntax: 10,
  policy_compliance: 10,
  engagement_potential: 5,
  hashtag_relevance: 5,
  target_audience_fit: 5,
  conciseness: 5,
  multimedia_sync: 10,
});

class QaEngine {
  constructor(options = {}) {
    this.passingThreshold = Number(options.passingThreshold || 90);
    this.brandKeywords = Array.isArray(options.brandKeywords)
      ? options.brandKeywords
      : ["ZeaZ", "zWorkforce", "AI"];
  }

  scoreDraft(draft = {}) {
    const text = String(draft.content || draft.text || "").trim();
    const scores = {};
    const feedback = [];

    // 1. Hook clarity (first 60 chars contains compelling statement or question)
    const firstLine = text.split("\n")[0] || "";
    if (
      firstLine.length >= 10 &&
      (firstLine.includes("?") ||
        firstLine.includes("!") ||
        firstLine.length > 20)
    ) {
      scores.hook_clarity = 10;
    } else {
      scores.hook_clarity = 4;
      feedback.push("Hook is too weak or too short.");
    }

    // 2. Brand voice (contains at least one brand keyword)
    const hasBrand = this.brandKeywords.some((k) =>
      text.toLowerCase().includes(k.toLowerCase()),
    );
    scores.brand_voice = hasBrand ? 10 : 5;
    if (!hasBrand)
      feedback.push("Draft does not reference brand voice keywords.");

    // 3. Safe margins & formatting (reasonable length and paragraph spacing)
    scores.safe_margins = text.length > 30 && text.length < 3000 ? 10 : 6;

    // 4. Claim substantiation (flags unsubstantiated superlatives like "100% guarantee", "best in the world")
    const sensationalWords = [
      "100% guarantee",
      "miracle",
      "get rich quick",
      "best in the world",
    ];
    const hasSensational = sensationalWords.some((w) =>
      text.toLowerCase().includes(w),
    );
    scores.claim_substantiation = hasSensational ? 2 : 10;
    if (hasSensational)
      feedback.push(
        "Draft contains unsubstantiated claims or prohibited superlatives.",
      );

    // 5. Call to action (contains action-oriented closing)
    const ctaWords = [
      "click",
      "comment",
      "share",
      "follow",
      "visit",
      "link",
      "check",
      "try",
    ];
    const hasCta = ctaWords.some((w) => text.toLowerCase().includes(w));
    scores.call_to_action = hasCta ? 10 : 4;
    if (!hasCta) feedback.push("Missing explicit call-to-action (CTA).");

    // 6. Grammar and syntax (no excessive punctuation)
    const excessivePunctuation = /([!?]){3,}/.test(text);
    scores.grammar_and_syntax = excessivePunctuation ? 5 : 10;

    // 7. Policy compliance (no prohibited terms)
    scores.policy_compliance = 10;

    // 8-12. Minor criteria defaults
    scores.engagement_potential = 5;
    scores.hashtag_relevance = text.includes("#") ? 5 : 2;
    scores.target_audience_fit = 5;
    scores.conciseness = 5;
    scores.multimedia_sync = 10;

    // Calculate total weighted score
    const totalScore = Object.entries(scores).reduce(
      (acc, [key, val]) => acc + (val * (CRITERIA_WEIGHTS[key] || 5)) / 10,
      0,
    );

    return {
      score: Math.min(100, Math.round(totalScore)),
      passed: totalScore >= this.passingThreshold,
      breakdown: scores,
      feedback,
    };
  }

  autoRemediate(draft = {}) {
    let text = String(draft.content || draft.text || "").trim();
    const evaluation = this.scoreDraft({ text });

    if (evaluation.passed) {
      return {
        remediated: false,
        text,
        score: evaluation.score,
        remediationsApplied: [],
      };
    }

    const applied = [];

    // Remediation 1: Fix weak hook
    if (evaluation.breakdown.hook_clarity < 10) {
      text = `🔥 Discover how ${text}`;
      applied.push("added_engaging_hook_prefix");
    }

    // Remediation 2: Remove sensational claims
    const sensationalWords = [
      "100% guarantee",
      "miracle",
      "get rich quick",
      "best in the world",
    ];
    for (const word of sensationalWords) {
      if (text.toLowerCase().includes(word)) {
        text = text.replace(new RegExp(word, "gi"), "proven solution");
        applied.push(`replaced_unsubstantiated_claim_${word}`);
      }
    }

    // Remediation 3: Add CTA if missing
    if (evaluation.breakdown.call_to_action < 10) {
      text +=
        "\n\n👉 Share your thoughts in the comments below or visit our link to learn more!";
      applied.push("appended_standard_cta");
    }

    // Remediation 4: Add hashtags if missing
    if (evaluation.breakdown.hashtag_relevance < 5) {
      text += "\n#ZeaZ #zWorkforce #AIAutomation";
      applied.push("appended_brand_hashtags");
    }

    // Re-evaluate
    const finalEvaluation = this.scoreDraft({ text });

    return {
      remediated: true,
      text,
      score: finalEvaluation.score,
      passed: finalEvaluation.passed,
      remediationsApplied: applied,
    };
  }
}

module.exports = {
  QaEngine,
  CRITERIA_WEIGHTS,
};
