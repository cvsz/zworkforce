import { PROVIDERS } from './channel-contracts.js';
import { createWhatsAppAdapter } from './adapters/whatsapp-adapter.js';
import { createLINEAdapter } from './adapters/line-adapter.js';
import { createMessengerAdapter } from './adapters/messenger-adapter.js';
import { createTikTokAdapter } from './adapters/tiktok-adapter.js';
import { createLogger } from '../observability/logger.js';

const ADAPTER_MODE = (process.env.ZOK_CHANNEL_ADAPTERS || 'simulated').trim().toLowerCase();
const ADAPTER_CREATORS = Object.freeze({
  whatsapp: createWhatsAppAdapter,
  line: createLINEAdapter,
  messenger: createMessengerAdapter,
  tiktok: createTikTokAdapter,
});

function validateConfig(config = {}) {
  if (!config || typeof config !== 'object' || Array.isArray(config)) {
    throw new TypeError('Adapter configuration must be a non-null object');
  }

  for (const provider of PROVIDERS) {
    const providerConfig = config[provider];
    if (providerConfig && typeof providerConfig !== 'object') {
      throw new TypeError(`Adapter configuration for ${provider} must be an object`);
    }
  }
}

export function createAdapterFactory(config = {}) {
  const logger = createLogger({ component: 'adapter-factory' });
  validateConfig(config);

  const cache = new Map();
  const initialized = new Set();

  function getAdapter(provider) {
    if (!PROVIDERS.includes(provider)) {
      throw new TypeError(`Unsupported provider: ${provider}`);
    }

    if (cache.has(provider)) {
      return cache.get(provider);
    }

    const creator = ADAPTER_CREATORS[provider];
    if (!creator) {
      throw new Error(`No adapter registered for provider: ${provider}`);
    }

    const providerConfig = {
      ...(config[provider] || {}),
    };

    if (ADAPTER_MODE === 'real') {
      providerConfig.mode = 'real';
    }

    try {
      const adapter = creator(providerConfig);
      cache.set(provider, adapter);
      return adapter;
    } catch (error) {
      logger.error('Failed to create adapter', { provider, error: error.message });
      throw error;
    }
  }

  async function initializeAdapter(provider) {
    const adapter = getAdapter(provider);
    if (initialized.has(provider)) {
      return adapter;
    }

    try {
      await adapter.initialize();
      initialized.add(provider);
      logger.info('Adapter initialized via factory', { provider, mode: ADAPTER_MODE });
      return adapter;
    } catch (error) {
      logger.error('Adapter initialization failed', { provider, error: error.message });
      throw error;
    }
  }

  async function initializeAll() {
    const results = {};
    for (const provider of PROVIDERS) {
      try {
        results[provider] = await initializeAdapter(provider);
      } catch (error) {
        results[provider] = { error: error.message };
      }
    }
    return results;
  }

  async function healthChecks() {
    const results = {};
    for (const provider of PROVIDERS) {
      try {
        const adapter = getAdapter(provider);
        results[provider] = await adapter.healthCheck();
      } catch (error) {
        results[provider] = { status: 'error', provider, error: error.message };
      }
    }
    return results;
  }

  return {
    getAdapter,
    initializeAdapter,
    initializeAll,
    healthChecks,
    get mode() {
      return ADAPTER_MODE;
    },
    get providers() {
      return [...PROVIDERS];
    },
  };
}

export { ADAPTER_MODE };
