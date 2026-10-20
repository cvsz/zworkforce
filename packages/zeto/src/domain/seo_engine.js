/**
 * seo_engine.js
 *
 * Multi-Platform SEO & Algorithm Keyword Density Optimization Engine.
 * Enforces per-platform hashtag policies, keyword density targets, and A/B score optimization.
 */

"use strict";

const PLATFORM_LIMITS = Object.freeze({
  shopee: {
    maxHashtags: 18,
    keywordDensityMin: 0.01,
    keywordDensityMax: 0.05,
    maxLen: 3000,
  },
  tiktok: {
    maxHashtags: 5,
    keywordDensityMin: 0.02,
    keywordDensityMax: 0.08,
    maxLen: 2200,
  },
  facebook: {
    maxHashtags: 8,
    keywordDensityMin: 0.01,
    keywordDensityMax: 0.04,
    maxLen: 5000,
  },
  instagram: {
    maxHashtags: 30,
    keywordDensityMin: 0.01,
    keywordDensityMax: 0.06,
    maxLen: 2200,
  },
  youtube: {
    maxHashtags: 15,
    keywordDensityMin: 0.015,
    keywordDensityMax: 0.05,
    maxLen: 5000,
  },
});

class SeoEngine {
  calculateKeywordDensity(text = "", keyword = "") {
    if (!text || !keyword) return 0;
    const words = text.toLowerCase().split(/\s+/).filter(Boolean);
    if (!words.length) return 0;
    const kwLower = keyword.toLowerCase();
    const count = words.filter((w) => w.includes(kwLower)).length;
    return count / words.length;
  }

  extractHashtags(text = "") {
    const matches = text.match(/#[a-zA-Z0-9_\p{L}]+/gu) || [];
    return matches.map((tag) => tag.toLowerCase());
  }

  scorePlatformSeo(text = "", platform = "facebook", targetKeywords = []) {
    const limits =
      PLATFORM_LIMITS[platform.toLowerCase()] || PLATFORM_LIMITS.facebook;
    const hashtags = this.extractHashtags(text);
    const feedback = [];

    // 1. Hashtag count validation
    let hashtagScore = 10;
    if (hashtags.length > limits.maxHashtags) {
      hashtagScore = 3;
      feedback.push(
        `Exceeds maximum recommended hashtags for ${platform} (${hashtags.length}/${limits.maxHashtags})`,
      );
    } else if (hashtags.length === 0) {
      hashtagScore = 5;
      feedback.push(`No hashtags detected for ${platform}`);
    }

    // 2. Keyword density validation
    let densityScore = 10;
    for (const kw of targetKeywords) {
      const density = this.calculateKeywordDensity(text, kw);
      if (density < limits.keywordDensityMin) {
        densityScore = Math.max(4, densityScore - 2);
        feedback.push(
          `Keyword '${kw}' density is low (${(density * 100).toFixed(1)}% vs min ${(limits.keywordDensityMin * 100).toFixed(1)}%)`,
        );
      } else if (density > limits.keywordDensityMax) {
        densityScore = Math.max(3, densityScore - 3);
        feedback.push(
          `Keyword '${kw}' density exceeds threshold (${(density * 100).toFixed(1)}% vs max ${(limits.keywordDensityMax * 100).toFixed(1)}%) - possible keyword stuffing`,
        );
      }
    }

    // Overall SEO score
    const totalScore = Math.round(hashtagScore * 0.4 + densityScore * 0.6) * 10;

    return {
      platform,
      score: totalScore,
      hashtagCount: hashtags.length,
      maxHashtagsAllowed: limits.maxHashtags,
      feedback,
    };
  }

  injectKeywordsAndHashtags(
    text = "",
    platform = "facebook",
    keywords = [],
    hashtags = [],
  ) {
    const limits =
      PLATFORM_LIMITS[platform.toLowerCase()] || PLATFORM_LIMITS.facebook;
    let result = typeof text === "string" ? text.trim() : "";
    const appendWithinLimit = (value, separator) => {
      const candidate = result ? `${result}${separator}${value}` : value;
      if (candidate.length > limits.maxLen) return false;
      result = candidate;
      return true;
    };

    // 1. Append missing target keywords without duplicating existing words or phrases.
    const containsKeyword = (value, keyword) => {
      const escaped = keyword
        .replace(/[.*+?^${}()|[\]\\]/g, "\\$&")
        .replace(/\s+/g, "\\s+");
      return new RegExp(
        `(^|[^\\p{L}\\p{N}_])${escaped}(?=$|[^\\p{L}\\p{N}_])`,
        "iu",
      ).test(value);
    };
    for (const rawKeyword of Array.isArray(keywords) ? keywords : []) {
      if (typeof rawKeyword !== "string") continue;
      const keyword = rawKeyword.trim().replace(/\s+/g, " ");
      if (!keyword || containsKeyword(result, keyword)) continue;
      appendWithinLimit(keyword, result ? "\n\n" : "");
    }

    // 2. Append valid missing target hashtags within the platform's count and text limits.
    const existingTags = new Set(this.extractHashtags(result));
    let addedTagCount = 0;
    for (const rawTag of Array.isArray(hashtags) ? hashtags : []) {
      if (typeof rawTag !== "string") continue;
      const tagName = rawTag.trim().replace(/^#+/, "");
      if (!tagName || !/^[\p{L}\p{N}_]+$/u.test(tagName)) continue;
      const formatted = `#${tagName}`;
      const normalized = formatted.toLowerCase();
      if (
        existingTags.has(normalized) ||
        existingTags.size >= limits.maxHashtags
      )
        continue;
      const separator = result ? (addedTagCount === 0 ? "\n\n" : " ") : "";
      if (appendWithinLimit(formatted, separator)) {
        existingTags.add(normalized);
        addedTagCount += 1;
      }
    }

    return result;
  }
}

module.exports = {
  SeoEngine,
  PLATFORM_LIMITS,
};
