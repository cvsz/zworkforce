/**
 * Base AI provider interface for Zeto generation plane (M02-M05).
 *
 * Provider credentials NEVER leave this module to the browser.
 * Each provider must be registered in the model router.
 * @module zeto/providers/ai/aiProvider
 */

"use strict";

/**
 * @typedef {Object} AIGenerationRequest
 * @property {string} type - "image"|"video"|"audio"|"text"
 * @property {string} prompt
 * @property {string} [negativePrompt]
 * @property {string} [model]
 * @property {Object} [parameters] - Provider-specific parameters
 * @property {string} [idempotencyKey]
 * @property {string} [brandKitId]
 */

/**
 * @typedef {Object} AIGenerationResult
 * @property {string} type
 * @property {string} providerId
 * @property {string} model
 * @property {string} [assetUrl] - Object-storage URL (never a provider credential)
 * @property {Buffer|Uint8Array} [bytes] - Raw bytes before storage upload
 * @property {Object} metadata
 * @property {string} metadata.promptHash
 * @property {string} metadata.seed
 * @property {number} metadata.latencyMs
 * @property {number} metadata.estimatedCostUsd
 * @property {number} metadata.tokenCount
 * @property {string} metadata.modelVersion
 */

/**
 * @typedef {Object} AIProviderCapability
 * @property {string} id - Unique provider ID
 * @property {string} locality - "local"|"cloud"
 * @property {string[]} types - Supported generation types
 * @property {string[]} models - Available model IDs
 * @property {number} maxConcurrency
 * @property {number} timeoutSeconds
 * @property {number} rateLimitRpm
 */

/**
 * @typedef {Object} AIProviderHealth
 * @property {string} providerId
 * @property {boolean} healthy
 * @property {number|null} latencyMs
 * @property {string|null} error - No credentials in error messages
 */

/**
 * Abstract base class. Subclass and implement generate() and health().
 */
class AIProvider {
  /** @returns {AIProviderCapability} */
  get capability() {
    throw new Error(`${this.constructor.name} must implement get capability()`);
  }

  /**
   * Generate an AI artifact.
   * @param {AIGenerationRequest} request
   * @returns {Promise<AIGenerationResult>}
   */
  async generate(_request) {
    throw new Error(`${this.constructor.name} must implement generate()`);
  }

  /**
   * Health check — must never expose credentials.
   * @returns {Promise<AIProviderHealth>}
   */
  async health() {
    throw new Error(`${this.constructor.name} must implement health()`);
  }
}

/**
 * FakeAIProvider — deterministic test double. No network calls.
 */
class FakeAIProvider extends AIProvider {
  /**
   * @param {object} [opts]
   * @param {string} [opts.id='fake']
   * @param {string[]} [opts.types]
   * @param {boolean} [opts.healthy=true]
   * @param {string|null} [opts.raiseOn=null] - Throw on generate if set
   */
  constructor({
    id = "fake",
    types = ["image", "text"],
    healthy = true,
    raiseOn = null,
  } = {}) {
    super();
    this._id = id;
    this._types = types;
    this._healthy = healthy;
    this._raiseOn = raiseOn;
  }

  get capability() {
    return {
      id: this._id,
      locality: "local",
      types: this._types,
      models: ["fake-1"],
      maxConcurrency: 4,
      timeoutSeconds: 5,
      rateLimitRpm: 60,
    };
  }

  async generate(request) {
    if (this._raiseOn) throw new Error(this._raiseOn);
    const hash = Buffer.from(request.prompt ?? "")
      .toString("base64")
      .slice(0, 16);
    return {
      type: request.type,
      providerId: this._id,
      model: request.model ?? "fake-1",
      bytes: Buffer.from(`fake-output-${request.type}`),
      metadata: {
        promptHash: hash,
        seed: "fake-seed-0",
        latencyMs: 10,
        estimatedCostUsd: 0,
        tokenCount: 10,
        modelVersion: "fake-1.0",
      },
    };
  }

  async health() {
    return {
      providerId: this._id,
      healthy: this._healthy,
      latencyMs: this._healthy ? 5 : null,
      error: this._healthy ? null : "simulated provider failure",
    };
  }
}

module.exports = {
  AIProvider,
  FakeAIProvider,
};
