"use strict";

const assert = require("node:assert/strict");
const test = require("node:test");
const {
  PromptTuner,
  HumanApprovalGate,
} = require("../src/domain/prompt_tuner.js");

test("PromptTuner adjusts prompt and temperature based on engagement feedback", () => {
  const tuner = new PromptTuner();
  const lowEngage = tuner.tunePrompt(
    "Create a TikTok hook for mechanical keyboard",
    { engagementScore: 40 },
  );

  assert.equal(lowEngage.temperature, 0.85);
  assert.ok(lowEngage.tunedPrompt.includes("[Tuning Guidance]"));

  const highEngage = tuner.tunePrompt("Create product showcase for Shopee", {
    engagementScore: 92,
  });
  assert.equal(highEngage.temperature, 0.65);
});

test("HumanApprovalGate tracks pending items and handles approvals", () => {
  const gate = new HumanApprovalGate();
  const pending = gate.submitForApproval(
    "post-101",
    "tenant-a",
    "Draft post content",
    20,
  );

  assert.equal(pending.status, "PENDING_APPROVAL");

  const decided = gate.decide("post-101", "tenant-a", "APPROVE", "Lead Editor");
  assert.equal(decided.status, "APPROVED");
  assert.equal(decided.decidedBy, "Lead Editor");
});
