/**
 * prompt_tuner.js
 *
 * Zeto Live Performance Feedback & Prompt Self-Tuning Engine.
 * Modifies temperature, persona intensity, and hashtag constraints based on engagement metrics.
 */

"use strict";

class PromptTuner {
  constructor() {
    this.defaultConfig = {
      temperature: 0.7,
      maxTokens: 1000,
      hashtagDensity: "moderate",
    };
  }

  tunePrompt(basePrompt, feedback = {}) {
    const engagementScore = Number(feedback.engagementScore || 50);
    const clickThroughRate = Number(feedback.ctr || 0.02);

    let adjustedTemp = this.defaultConfig.temperature;
    let styleGuidance = "";

    if (engagementScore < 60) {
      // Low engagement -> Boost hook punchiness and curiosity
      adjustedTemp = 0.85;
      styleGuidance =
        "Increase curiosity gap and open with an irresistible question hook.";
    } else if (engagementScore > 85) {
      // High performance -> Lock in structured clarity
      adjustedTemp = 0.65;
      styleGuidance =
        "Maintain authoritative, conversion-focused structure with clear CTA.";
    }

    let tunedPrompt = basePrompt.trim();
    if (styleGuidance) {
      tunedPrompt += `\n[Tuning Guidance]: ${styleGuidance}`;
    }

    return {
      tunedPrompt,
      temperature: adjustedTemp,
      engagementScore,
      clickThroughRate,
    };
  }
}

class HumanApprovalGate {
  constructor() {
    this.pendingReviews = new Map();
  }

  submitForApproval(contentId, tenantId, content, riskScore = 0) {
    if (!contentId || !tenantId)
      throw new Error("contentId and tenantId are required");

    const item = {
      contentId,
      tenantId,
      content,
      riskScore: Number(riskScore),
      status: riskScore > 50 ? "REQUIRES_ESCALATION" : "PENDING_APPROVAL",
      submittedAt: new Date().toISOString(),
    };

    this.pendingReviews.set(`${tenantId}:${contentId}`, item);
    return item;
  }

  decide(contentId, tenantId, decision, reviewer) {
    const key = `${tenantId}:${contentId}`;
    const item = this.pendingReviews.get(key);
    if (!item) return null;

    item.status = decision === "APPROVE" ? "APPROVED" : "REJECTED";
    item.decidedBy = reviewer || "Operator";
    item.decidedAt = new Date().toISOString();
    return item;
  }
}

module.exports = {
  PromptTuner,
  HumanApprovalGate,
};
