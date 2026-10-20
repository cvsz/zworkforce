/**
 * AI provider registry for Zeto generation plane.
 *
 * Provides duplicate-protection registration, capability-based
 * lookup, and health summary without exposing credentials.
 * @module zeto/providers/ai/aiProviderRegistry
 */

"use strict";

class DuplicateProviderError extends Error {
  constructor(id) {
    super(`AI provider '${id}' is already registered`);
    this.name = "DuplicateProviderError";
  }
}

class ProviderNotFoundError extends Error {
  constructor(id) {
    super(`AI provider '${id}' not found`);
    this.name = "ProviderNotFoundError";
  }
}

class AIProviderRegistry {
  constructor() {
    /** @type {Map<string, import('./aiProvider.js').AIProvider>} */
    this._providers = new Map();
  }

  /**
   * Register an AI provider.
   * @param {AIProvider} provider
   * @throws {DuplicateProviderError}
   */
  register(provider) {
    const id = provider.capability.id;
    if (!id)
      throw new TypeError("provider.capability.id must be a non-empty string");
    if (this._providers.has(id)) throw new DuplicateProviderError(id);
    this._providers.set(id, provider);
  }

  /**
   * Get a provider by ID.
   * @param {string} id
   * @throws {ProviderNotFoundError}
   */
  get(id) {
    const p = this._providers.get(id);
    if (!p) throw new ProviderNotFoundError(id);
    return p;
  }

  /**
   * Find providers that support a given generation type.
   * @param {string} type - "image"|"video"|"audio"|"text"
   * @returns {AIProvider[]}
   */
  findByType(type) {
    return [...this._providers.values()].filter((p) =>
      p.capability.types.includes(type),
    );
  }

  /** @returns {string[]} All registered provider IDs. */
  list() {
    return [...this._providers.keys()].sort();
  }

  /**
   * Health summary — must not expose credentials.
   * @returns {Promise<object[]>}
   */
  async healthSummary() {
    const results = await Promise.allSettled(
      [...this._providers.values()].map(async (p) => {
        try {
          return await p.health();
        } catch (err) {
          return {
            providerId: p.capability.id,
            healthy: false,
            latencyMs: null,
            error: String(err.message),
          };
        }
      }),
    );
    return results.map((r) =>
      r.status === "fulfilled"
        ? r.value
        : { providerId: "unknown", healthy: false, error: r.reason?.message },
    );
  }
}

module.exports = {
  DuplicateProviderError,
  ProviderNotFoundError,
  AIProviderRegistry,
};
