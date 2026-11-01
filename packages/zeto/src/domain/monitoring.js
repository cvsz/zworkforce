function analyzeMention(mention) {
  const body = String(mention.body || "");
  const normalized = body.toLowerCase();
  let classification = "question";
  if (/https?:\/\/|free crypto|buy now|click here/.test(normalized))
    classification = "spam";
  else if (
    /broken|refund|complaint|angry|terrible|doesn'?t work|not working/.test(
      normalized,
    )
  )
    classification = "complaint";
  else if (
    /our business|pricing|demo|hire|purchase|your team help/.test(normalized)
  )
    classification = "lead";
  else if (/\?|how |what |when |where |can i|could i/.test(normalized))
    classification = "question";
  else if (/amazing|thank|great|love|excellent|helpful/.test(normalized))
    classification = "praise";

  const positive = (
    normalized.match(/amazing|thank|great|love|excellent|helpful/g) || []
  ).length;
  const negative = (
    normalized.match(/broken|refund|angry|terrible|bad|failed|not working/g) ||
    []
  ).length;
  const sentiment = Math.max(
    0,
    Math.min(100, 50 + positive * 15 - negative * 20),
  );
  const result = { ...mention, classification, sentiment };
  if (classification === "complaint") {
    result.replyDraft =
      "We are sorry this happened. Please share the relevant details privately so our team can investigate promptly.";
    result.escalation = {
      severity: sentiment < 30 ? "critical" : "warning",
      slaMinutes: sentiment < 30 ? 30 : 120,
    };
  }
  if (classification === "lead") {
    result.escalation = { severity: "info", slaMinutes: 240, handoff: "sales" };
  }
  return result;
}

function evaluateAlerts(snapshot) {
  const rules = [
    [
      "volume_spike",
      snapshot.baselineVolume > 0 &&
        snapshot.volume >= snapshot.baselineVolume * 2,
      "warning",
    ],
    [
      "sentiment_deterioration",
      snapshot.baselineSentiment - snapshot.sentiment >= 20,
      "critical",
    ],
    [
      "viral_negative_content",
      snapshot.viralNegativeReach >= 10000,
      "critical",
    ],
    [
      "competitor_pricing_mention",
      snapshot.competitorPricingMentions > 0,
      "info",
    ],
    ["creator_influencer_mention", snapshot.influencerMentions > 0, "info"],
    ["overdue_critical_reply", snapshot.overdueCriticalReplies > 0, "critical"],
  ];
  return rules
    .filter(([, active]) => active)
    .map(([type, , severity]) => ({
      type,
      severity,
      dedupeKey: `${snapshot.brandId}:${type}:${snapshot.period}`,
      status: "open",
      evidence: snapshot,
    }));
}

/**
 * Classify a social mention into one of the canonical categories.
 *
 * Categories: question, complaint, praise, spam, lead
 *
 * This is a rule-based baseline classifier. A model-backed classifier
 * can be registered via the model router in production.
 *
 * @param {object} mention
 * @param {string} mention.text - Raw mention text
 * @param {string} [mention.authorFollowers] - Author follower count (hint)
 * @returns {{ category: string, confidence: number }}
 */
function classifyMention(mention) {
  const text = (mention?.text ?? "").toLowerCase();
  if (!text) return { category: "spam", confidence: 0.5 };

  const scores = {
    question: 0,
    complaint: 0,
    praise: 0,
    spam: 0,
    lead: 0,
  };

  // Question signals
  if (/[?]/.test(text)) scores.question += 2;
  if (
    /\b(how(?!\s+much)|what|when|where|why|can you|do you|is there)\b/.test(
      text,
    )
  )
    scores.question += 2;

  // Complaint signals
  if (
    /\b(broken|terrible|horrible|awful|hate|worst|scam|fraud|refund|problem|issue|bug|failed|disappoint)\b/.test(
      text,
    )
  )
    scores.complaint += 3;
  if (
    /\b(not working|doesn.t work|doesn.t work|won.t|can.t|cannot)\b/.test(text)
  )
    scores.complaint += 2;

  // Praise signals
  if (
    /\b(amazing|excellent|love|great|fantastic|awesome|perfect|brilliant|outstanding)\b/.test(
      text,
    )
  )
    scores.praise += 3;
  if (/\b(thank|thanks|good job|well done|impressed|recommend)\b/.test(text))
    scores.praise += 2;

  // Lead signals
  if (
    /\b(buy|purchase|price|cost|how much|quote|interested in|trial|demo|sign up|get started)\b/.test(
      text,
    )
  )
    scores.lead += 3;
  if (/\b(business|enterprise|team|company|organization)\b/.test(text))
    scores.lead += 1;

  // Spam signals
  if (
    /http[s]?:\/\//.test(text) &&
    scores.question === 0 &&
    scores.praise === 0
  )
    scores.spam += 2;
  if (/(.+)\1{3,}/.test(text)) scores.spam += 2; // repetitive text

  const top = Object.entries(scores).sort(([, a], [, b]) => b - a)[0];
  const totalSignal = Object.values(scores).reduce((a, b) => a + b, 0);
  const confidence =
    totalSignal > 0 ? Math.min(0.95, top[1] / totalSignal + 0.4) : 0.5;

  return { category: top[0], confidence: Math.round(confidence * 100) / 100 };
}

/**
 * Normalize a raw sentiment value to the 0-100 scale.
 *
 * Accepts:
 * - Already normalized 0-100 integer → returned as-is
 * - Float -1.0..1.0 (e.g. from ML models) → mapped to 0-100
 * - Undefined/null → 50 (neutral)
 *
 * @param {number|null|undefined} raw
 * @returns {number} Integer 0-100
 */
function normalizeSentiment(raw) {
  if (raw === null || raw === undefined) return 50;
  if (raw >= -1 && raw <= 1) return Math.round((raw + 1) * 50);
  if (raw >= 0 && raw <= 100) return Math.round(raw);
  // Clamp anything else
  return Math.max(0, Math.min(100, Math.round(raw)));
}

module.exports = {
  analyzeMention,
  evaluateAlerts,
  classifyMention,
  normalizeSentiment,
};
