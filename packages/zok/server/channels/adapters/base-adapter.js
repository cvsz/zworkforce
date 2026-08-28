import { createLogger } from '../../observability/logger.js';

function sleep(ms) {
  return new Promise(resolve => setTimeout(resolve, ms));
}

async function fetchWithRetry(url, options = {}, retries = 3, backoffMs = 500) {
  const logger = createLogger({ component: 'adapter-http' });

  for (let attempt = 1; attempt <= retries; attempt++) {
    try {
      const response = await fetch(url, options);
      if (response.ok) return response;

      if (response.status === 429 || response.status >= 500) {
        const retryAfter = response.headers.get('retry-after');
        const delay = retryAfter ? Number(retryAfter) * 1000 : backoffMs * attempt;
        logger.warn('Adapter HTTP retry scheduled', {
          url,
          status: response.status,
          attempt,
          retryAfter: delay,
        });
        await sleep(delay);
        continue;
      }

      const body = await response.text();
      let parsed;
      try {
        parsed = JSON.parse(body);
      } catch {
        parsed = { raw: body };
      }

      const error = new Error(parsed.error?.message || `HTTP ${response.status}`);
      error.status = response.status;
      error.payload = parsed;
      throw error;
    } catch (error) {
      if (attempt === retries || error.status) throw error;
      logger.warn('Adapter HTTP attempt failed', {
        url,
        attempt,
        error: error.message,
      });
      await sleep(backoffMs * attempt);
    }
  }

  throw new Error(`Failed after ${retries} attempts`);
}

export function createBaseAdapter(config = {}) {
  const logger = createLogger({ component: 'adapter', provider: config.provider || 'unknown' });
  const provider = config.provider;

  if (!provider) {
    throw new TypeError('provider is required for adapter configuration');
  }

  return {
    provider,
    initialized: false,

    async initialize() {
      this.initialized = true;
      logger.info('adapter initialized', { mode: 'simulated' });
    },

    async sendText(contactId, text) {
      throw new Error('sendText is not implemented');
    },

    async sendImage(contactId, imageUrl, caption = '') {
      throw new Error('sendImage is not implemented');
    },

    async sendDocument(contactId, documentUrl, filename = '') {
      throw new Error('sendDocument is not implemented');
    },

    async sendTemplate(contactId, templateName, templateData = {}) {
      throw new Error('sendTemplate is not implemented');
    },

    async sendQuickReplies(contactId, text, quickReplies = []) {
      throw new Error('sendQuickReplies is not implemented');
    },

    async verifyContact(contactId) {
      return { valid: false, reason: 'not_supported' };
    },

    async healthCheck() {
      return { status: 'ok', provider, mode: 'simulated' };
    },
  };
}

export { fetchWithRetry, sleep };
