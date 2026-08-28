import { createBaseAdapter, fetchWithRetry, sleep } from './base-adapter.js';
import { createLogger } from '../../observability/logger.js';

const MESSAGE_TYPES = Object.freeze(['text', 'product', 'order_update', 'image']);
const RATE_LIMIT_WINDOW_MS = 60000;
const MAX_REQUESTS_PER_WINDOW = 120;

function validateTikTokMessage(payload) {
  if (!payload || typeof payload !== 'object' || Array.isArray(payload)) {
    return { valid: false, error: 'Message payload must be a non-null object' };
  }

  const type = typeof payload.type === 'string' ? payload.type : 'text';
  if (!MESSAGE_TYPES.includes(type)) {
    return { valid: false, error: `Unsupported TikTok message type: ${type}` };
  }

  if (type === 'text') {
    const text = typeof payload.text === 'string' ? payload.text.trim() : '';
    if (!text) return { valid: false, error: 'text is required for text messages' };
    if (text.length > 2000) return { valid: false, error: 'text exceeds 2000 characters' };
  }

  return { valid: true, type };
}

function buildAuthHeader(appKey, appSecret, accessToken) {
  const token = accessToken || appSecret || '';
  return `Bearer ${token}`;
}

export function createTikTokAdapter(config = {}) {
  const base = createBaseAdapter({ provider: 'tiktok' });
  const logger = createLogger({ component: 'tiktok-adapter' });

  const appKey = (config.appKey || process.env.ZOK_TIKTOK_APP_KEY || '').trim();
  const appSecret = (config.appSecret || process.env.ZOK_TIKTOK_APP_SECRET || '').trim();
  const accessToken = (config.accessToken || process.env.ZOK_TIKTOK_ACCESS_TOKEN || '').trim();
  const shopId = (config.shopId || process.env.ZOK_TIKTOK_SHOP_ID || '').trim();
  const apiVersion = (config.apiVersion || process.env.ZOK_TIKTOK_API_VERSION || '202309').trim();
  const region = (config.region || process.env.ZOK_TIKTOK_REGION || 'US').trim().toUpperCase();

  const baseUrls = {
    US: 'https://open-api.tiktokglobalshop.com',
    EU: 'https://open-api.tiktokglobalshop.com',
    SEA: 'https://open-api.tiktokglobalshop.com',
    SG: 'https://open-api-sg.tiktokglobalshop.com',
  };

  const requestBuckets = new Map();

  function checkRateLimit(key) {
    const now = Date.now();
    const bucket = requestBuckets.get(key) || { count: 0, resetAt: now + RATE_LIMIT_WINDOW_MS };
    if (bucket.resetAt <= now) {
      bucket.count = 0;
      bucket.resetAt = now + RATE_LIMIT_WINDOW_MS;
    }
    bucket.count += 1;
    requestBuckets.set(key, bucket);
    return {
      allowed: bucket.count <= MAX_REQUESTS_PER_WINDOW,
      remaining: Math.max(0, MAX_REQUESTS_PER_WINDOW - bucket.count),
      resetAt: bucket.resetAt,
    };
  }

  function getBaseUrl() {
    return baseUrls[region] || baseUrls.US;
  }

  async function makeRequest(action, body) {
    if (!appKey || !appSecret) {
      throw new Error('TikTok app key and app secret are required for real mode');
    }

    const rateKey = shopId || 'default';
    const rate = checkRateLimit(rateKey);
    if (!rate.allowed) {
      const error = new Error('TikTok rate limit exceeded');
      error.retryAfter = Math.max(1, Math.ceil((rate.resetAt - Date.now()) / 1000));
      throw error;
    }

    const url = `${getBaseUrl()}/${apiVersion}/msg/${action}`;
    const response = await fetchWithRetry(
      url,
      {
        method: 'POST',
        headers: {
          Authorization: buildAuthHeader(appKey, appSecret, accessToken),
          'Content-Type': 'application/json',
          'x-tts-access-token': accessToken || appSecret,
        },
        body: JSON.stringify(body),
      },
      3,
      1000,
    );

    const data = await response.json();
    if (!response.ok || data.error) {
      const error = new Error(data.error?.message || `TikTok API error ${response.status}`);
      error.status = response.status;
      error.payload = data;
      throw error;
    }

    return data;
  }

  async function initialize() {
    this.initialized = true;
    if (appKey && appSecret) {
      logger.info('TikTok adapter initialized', {
        mode: 'real',
        shopId: shopId || 'not-configured',
        region,
        apiVersion,
      });
    } else {
      logger.info('TikTok adapter initialized', { mode: 'simulated' });
    }
  }

  async function sendText(contactId, text) {
    const validation = validateTikTokMessage({ type: 'text', text });
    if (!validation.valid) {
      throw new TypeError(validation.error);
    }

    if (!appKey || !appSecret) {
      logger.info('Simulated TikTok text message', { contactId, textLength: text.length });
      return { externalId: `tiktok-sim-${Date.now()}`, status: 'sent' };
    }

    const result = await makeRequest('send_text', {
      to_user_id: contactId,
      message: text,
    });
    logger.info('TikTok text message sent', { contactId, externalId: result?.message_id });
    return { externalId: result?.message_id, status: 'sent', payload: result };
  }

  async function sendProductMessage(contactId, productId, shopIdOverride) {
    if (!appKey || !appSecret) {
      logger.info('Simulated TikTok product message', { contactId, productId });
      return { externalId: `tiktok-sim-prod-${Date.now()}`, status: 'sent' };
    }

    const result = await makeRequest('send_product', {
      to_user_id: contactId,
      product_id: productId,
      shop_id: shopIdOverride || shopId,
    });
    logger.info('TikTok product message sent', { contactId, productId, externalId: result?.message_id });
    return { externalId: result?.message_id, status: 'sent', payload: result };
  }

  async function sendOrderUpdate(contactId, orderId, status, shopIdOverride) {
    if (!appKey || !appSecret) {
      logger.info('Simulated TikTok order update', { contactId, orderId, status });
      return { externalId: `tiktok-sim-ord-${Date.now()}`, status: 'sent' };
    }

    const result = await makeRequest('send_order', {
      to_user_id: contactId,
      order_id: orderId,
      status,
      shop_id: shopIdOverride || shopId,
    });
    logger.info('TikTok order update sent', { contactId, orderId, status, externalId: result?.message_id });
    return { externalId: result?.message_id, status: 'sent', payload: result };
  }

  async function sendImage(contactId, imageUrl, caption = '') {
    const validation = validateTikTokMessage({ type: 'image' });
    if (!validation.valid) {
      throw new TypeError(validation.error);
    }

    if (!appKey || !appSecret) {
      logger.info('Simulated TikTok image message', { contactId, imageUrl });
      return { externalId: `tiktok-sim-img-${Date.now()}`, status: 'sent' };
    }

    const result = await makeRequest('send_image', {
      to_user_id: contactId,
      image_url: imageUrl,
      caption,
    });
    logger.info('TikTok image message sent', { contactId, externalId: result?.message_id });
    return { externalId: result?.message_id, status: 'sent', payload: result };
  }

  async function updateTransactionStatus(contactId, transactionId, status, shopIdOverride) {
    if (!appKey || !appSecret) {
      logger.info('Simulated TikTok transaction status update', { contactId, transactionId, status });
      return { externalId: `tiktok-sim-txn-${Date.now()}`, status: 'sent' };
    }

    const result = await makeRequest('update_transaction', {
      to_user_id: contactId,
      transaction_id: transactionId,
      status,
      shop_id: shopIdOverride || shopId,
    });
    logger.info('TikTok transaction status updated', {
      contactId,
      transactionId,
      status,
      externalId: result?.message_id,
    });
    return { externalId: result?.message_id, status: 'sent', payload: result };
  }

  async function verifyContact(contactId) {
    if (!appKey || !appSecret) {
      logger.info('Simulated TikTok contact verification', { contactId });
      return { valid: true, contactId, platform: 'tiktok' };
    }

    try {
      const result = await makeRequest('get_user_info', { user_id: contactId });
      if (result.error) {
        return { valid: false, contactId, error: result.error.message };
      }
      return { valid: true, contactId, platform: 'tiktok', userInfo: result };
    } catch (error) {
      logger.warn('TikTok contact verification failed', { contactId, error: error.message });
      return { valid: false, contactId, error: error.message };
    }
  }

  async function healthCheck() {
    if (!appKey || !appSecret) {
      return { status: 'ok', provider: 'tiktok', mode: 'simulated' };
    }
    try {
      const url = `${getBaseUrl()}/${apiVersion}/authorization/health`;
      const response = await fetchWithRetry(
        url,
        {
          method: 'GET',
          headers: {
            Authorization: buildAuthHeader(appKey, appSecret, accessToken),
          },
        },
        1,
      );
      if (response.ok) {
        return { status: 'ok', provider: 'tiktok', mode: 'real' };
      }
      return { status: 'degraded', provider: 'tiktok', mode: 'real', error: 'unhealthy' };
    } catch (error) {
      return { status: 'degraded', provider: 'tiktok', mode: 'real', error: error.message };
    }
  }

  return {
    ...base,
    initialize,
    sendText,
    sendImage,
    sendProductMessage,
    sendOrderUpdate,
    updateTransactionStatus,
    verifyContact,
    healthCheck,
  };
}

export default createTikTokAdapter;
