import { createLogger } from '../observability/logger.js';

const DEFAULT_RATE_LIMITS = {
  whatsapp: { maxPerSecond: 80, maxBurst: 100 },
  line: { maxPerSecond: 100, maxBurst: 120 },
  messenger: { maxPerSecond: 60, maxBurst: 80 },
  tiktok: { maxPerSecond: 50, maxBurst: 60 },
  shopify: { maxPerSecond: 40, maxBurst: 50 },
};

const CIRCUIT_BREAKER_THRESHOLD = 5;
const CIRCUIT_BREAKER_COOLDOWN_MS = 30_000;

class ChannelRateLimiter {
  constructor() {
    this.buckets = new Map();
    this.logger = createLogger({ component: 'campaign-rate-limiter' });
  }

  getBucket(channel) {
    if (!this.buckets.has(channel)) {
      const config = DEFAULT_RATE_LIMITS[channel] || { maxPerSecond: 30, maxBurst: 40 };
      this.buckets.set(channel, {
        tokens: config.maxBurst,
        maxTokens: config.maxBurst,
        refillRate: config.maxPerSecond,
        lastRefill: Date.now(),
      });
    }
    return this.buckets.get(channel);
  }

  refill(bucket) {
    const now = Date.now();
    const delta = (now - bucket.lastRefill) / 1000;
    bucket.tokens = Math.min(bucket.maxTokens, bucket.tokens + delta * bucket.refillRate);
    bucket.lastRefill = now;
  }

  async acquire(channel) {
    const bucket = this.getBucket(channel);
    this.refill(bucket);

    if (bucket.tokens >= 1) {
      bucket.tokens -= 1;
      return true;
    }

    const waitMs = ((1 - bucket.tokens) / bucket.refillRate) * 1000;
    this.logger.debug('rate limit wait', { channel, waitMs });
    await new Promise(resolve => setTimeout(resolve, Math.min(waitMs, 5000)));
    this.refill(bucket);

    if (bucket.tokens >= 1) {
      bucket.tokens -= 1;
      return true;
    }

    return false;
  }
}

class CircuitBreaker {
  constructor() {
    this.states = new Map();
    this.logger = createLogger({ component: 'campaign-circuit-breaker' });
  }

  getState(channel) {
    if (!this.states.has(channel)) {
      this.states.set(channel, {
        state: 'CLOSED',
        failures: 0,
        lastFailure: null,
        nextRetry: null,
      });
    }
    return this.states.get(channel);
  }

  recordSuccess(channel) {
    const state = this.getState(channel);
    state.failures = 0;
    state.state = 'CLOSED';
    state.lastFailure = null;
    state.nextRetry = null;
  }

  recordFailure(channel, error) {
    const state = this.getState(channel);
    state.failures += 1;
    state.lastFailure = error;
    state.lastFailureAt = Date.now();

    if (state.failures >= CIRCUIT_BREAKER_THRESHOLD) {
      state.state = 'OPEN';
      state.nextRetry = Date.now() + CIRCUIT_BREAKER_COOLDOWN_MS;
      this.logger.warn('circuit breaker opened', { channel, failures: state.failures });
    }
  }

  canProceed(channel) {
    const state = this.getState(channel);

    if (state.state === 'OPEN') {
      if (Date.now() >= state.nextRetry) {
        state.state = 'HALF_OPEN';
        return true;
      }
      return false;
    }

    return true;
  }
}

class CampaignExecutor {
  constructor(options = {}) {
    this.rateLimiter = options.rateLimiter || new ChannelRateLimiter();
    this.circuitBreaker = options.circuitBreaker || new CircuitBreaker();
    this.logger = createLogger({ component: 'campaign-executor' });
    this.auditService = options.auditService || null;
  }

  async executeAction(action) {
    const { type, channel, contactId, campaignId, payload = {}, tenantId } = action;

    if (!this.circuitBreaker.canProceed(channel)) {
      const error = new Error(`Circuit breaker open for channel ${channel}`);
      this.logger.warn('channel circuit breaker open', { channel, campaignId, contactId });
      return { status: 'skipped', reason: 'circuit_breaker_open', error: error.message };
    }

    await this.rateLimiter.acquire(channel);

    try {
      const result = await this.dispatchAction(type, payload);
      this.circuitBreaker.recordSuccess(channel);
      await this.emitAudit(tenantId, 'campaign.execute.success', { campaignId, contactId, channel, type });
      return { status: 'completed', result };
    } catch (error) {
      this.circuitBreaker.recordFailure(channel, error);
      await this.emitAudit(tenantId, 'campaign.execute.failure', { campaignId, contactId, channel, type, error: error.message });
      return { status: 'failed', error: error.message };
    }
  }

  async dispatchAction(type, payload) {
    switch (type) {
      case 'send_message':
        return this.sendMessage(payload);
      case 'update_tag':
        return this.updateTag(payload);
      case 'webhook':
        return this.triggerWebhook(payload);
      default:
        throw new Error(`Unsupported action type: ${type}`);
    }
  }

  async sendMessage(payload) {
    const data = payload.data || payload;
    const { text, to } = data;
    if (!text || !to) {
      throw new Error('send_message requires text and to');
    }
    this.logger.info('sending broadcast message', { to, textLength: text.length });
    return { delivered: true, externalId: `msg_${Date.now()}_${Math.random().toString(36).slice(2, 8)}` };
  }

  async updateTag(payload) {
    const data = payload.data || payload;
    const { contactId, tags } = data;
    if (!contactId || !Array.isArray(tags)) {
      throw new Error('update_tag requires contactId and tags array');
    }
    this.logger.info('updating contact tags', { contactId, tags });
    return { updated: true, tagCount: tags.length };
  }

  async triggerWebhook(payload) {
    const data = payload.data || payload;
    const { url, method = 'POST', headers = {}, body = {} } = data;
    if (!url) {
      throw new Error('webhook requires url');
    }
    this.logger.info('triggering webhook', { url, method });
    return { webhookStatus: 202, url };
  }

  async emitAudit(tenantId, action, metadata = {}) {
    if (!this.auditService) return;
    try {
      await this.auditService.emit({
        tenant_id: tenantId,
        actor_user_id: null,
        action,
        resource_type: 'campaign',
        resource_id: metadata.campaignId,
        request_id: `campaign_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`,
        occurred_at: new Date().toISOString(),
        metadata,
      });
    } catch {
      // audit is best-effort
    }
  }
}

export function createCampaignExecutor(options = {}) {
  return new CampaignExecutor(options);
}
