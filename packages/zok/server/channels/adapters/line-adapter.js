import { createBaseAdapter, fetchWithRetry, sleep } from './base-adapter.js';
import { createLogger } from '../../observability/logger.js';

const MESSAGE_TYPES = Object.freeze(['text', 'image', 'template', 'flex', 'sticker']);
const RATE_LIMIT_WINDOW_MS = 60000;
const MAX_REQUESTS_PER_WINDOW = 100;

function validateLINEMessage(payload) {
  if (!payload || typeof payload !== 'object' || Array.isArray(payload)) {
    return { valid: false, error: 'Message payload must be a non-null object' };
  }

  const type = typeof payload.type === 'string' ? payload.type : 'text';
  if (!MESSAGE_TYPES.includes(type)) {
    return { valid: false, error: `Unsupported LINE message type: ${type}` };
  }

  if (type === 'text') {
    const text = typeof payload.text === 'string' ? payload.text.trim() : '';
    if (!text) return { valid: false, error: 'text is required for text messages' };
    if (text.length > 5000) return { valid: false, error: 'text exceeds 5000 characters' };
  }

  return { valid: true, type };
}

export function createLINEAdapter(config = {}) {
  const base = createBaseAdapter({ provider: 'line' });
  const logger = createLogger({ component: 'line-adapter' });

  const channelAccessToken = (config.channelAccessToken || process.env.ZOK_LINE_CHANNEL_ACCESS_TOKEN || '').trim();
  const channelSecret = (config.channelSecret || process.env.ZOK_LINE_CHANNEL_SECRET || '').trim();
  const botUserId = (config.botUserId || process.env.ZOK_LINE_BOT_USER_ID || '').trim();
  const apiVersion = (config.apiVersion || process.env.ZOK_LINE_API_VERSION || 'v2').trim();

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

  async function makeRequest(body) {
    if (!channelAccessToken) {
      throw new Error('LINE channel access token is required for real mode');
    }

    const rateKey = botUserId || 'default';
    const rate = checkRateLimit(rateKey);
    if (!rate.allowed) {
      const error = new Error('LINE rate limit exceeded');
      error.retryAfter = Math.max(1, Math.ceil((rate.resetAt - Date.now()) / 1000));
      throw error;
    }

    const url = `https://api.line.me/${apiVersion}/bot/message/push`;
    const response = await fetchWithRetry(
      url,
      {
        method: 'POST',
        headers: {
          Authorization: `Bearer ${channelAccessToken}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(body),
      },
      3,
      1000,
    );

    const data = await response.json();
    if (!response.ok || data.error) {
      const error = new Error(data.error?.message || `LINE API error ${response.status}`);
      error.status = response.status;
      error.payload = data;
      throw error;
    }

    return data;
  }

  async function initialize() {
    this.initialized = true;
    if (channelAccessToken) {
      try {
        const url = `https://api.line.me/${apiVersion}/bot/info`;
        const response = await fetchWithRetry(
          url,
          {
            headers: { Authorization: `Bearer ${channelAccessToken}` },
          },
          2,
          500,
        );
        const data = await response.json();
        if (!response.ok || data.error) {
          logger.warn('LINE bot info fetch failed', { error: data.error?.message });
        } else {
          logger.info('LINE bot verified', {
            botName: data.displayName,
            botUserId: data.userId,
          });
        }
      } catch (error) {
        logger.warn('LINE verification check skipped', { error: error.message });
      }
    }
    logger.info('LINE adapter initialized', {
      mode: channelAccessToken ? 'real' : 'simulated',
      botUserId: botUserId || 'not-configured',
    });
  }

  async function sendText(contactId, text) {
    const validation = validateLINEMessage({ type: 'text', text });
    if (!validation.valid) {
      throw new TypeError(validation.error);
    }

    if (!channelAccessToken) {
      logger.info('Simulated LINE text message', { contactId, textLength: text.length });
      return { externalId: `line-sim-${Date.now()}`, status: 'sent' };
    }

    const body = {
      to: contactId,
      messages: [
        {
          type: 'text',
          text,
        },
      ],
    };

    const result = await makeRequest(body);
    logger.info('LINE text message sent', { contactId, externalId: result?.sentMessageId });
    return { externalId: result?.sentMessageId, status: 'sent', payload: result };
  }

  async function sendImage(contactId, imageUrl, caption = '') {
    const validation = validateLINEMessage({ type: 'image' });
    if (!validation.valid) {
      throw new TypeError(validation.error);
    }

    if (!channelAccessToken) {
      logger.info('Simulated LINE image message', { contactId, imageUrl });
      return { externalId: `line-sim-img-${Date.now()}`, status: 'sent' };
    }

    const body = {
      to: contactId,
      messages: [
        {
          type: 'image',
          originalContentUrl: imageUrl,
          previewImageUrl: imageUrl,
          ...(caption ? { name: caption } : {}),
        },
      ],
    };

    const result = await makeRequest(body);
    logger.info('LINE image message sent', { contactId, externalId: result?.sentMessageId });
    return { externalId: result?.sentMessageId, status: 'sent', payload: result };
  }

  async function sendTemplate(contactId, templateName, templateData = {}) {
    if (!channelAccessToken) {
      logger.info('Simulated LINE template message', { contactId, templateName, templateData });
      return { externalId: `line-sim-tpl-${Date.now()}`, status: 'sent' };
    }

    const altText = templateData.altText || templateName;
    const body = {
      to: contactId,
      messages: [
        {
          type: 'template',
          altText,
          template: {
            type: 'buttons',
            text: templateData.text || templateName,
            actions: (templateData.actions || []).map(action => ({
              type: action.type || 'message',
              label: action.label,
              text: action.text || action.label,
              ...(action.uri ? { uri: action.uri } : {}),
            })),
          },
        },
      ],
    };

    const result = await makeRequest(body);
    logger.info('LINE template message sent', { contactId, templateName, externalId: result?.sentMessageId });
    return { externalId: result?.sentMessageId, status: 'sent', payload: result };
  }

  async function sendFlexMessage(contactId, flexContent, altText = 'Flex Message') {
    if (!channelAccessToken) {
      logger.info('Simulated LINE flex message', { contactId, altText });
      return { externalId: `line-sim-flex-${Date.now()}`, status: 'sent' };
    }

    const body = {
      to: contactId,
      messages: [
        {
          type: 'flex',
          altText,
          contents: flexContent,
        },
      ],
    };

    const result = await makeRequest(body);
    logger.info('LINE flex message sent', { contactId, externalId: result?.sentMessageId });
    return { externalId: result?.sentMessageId, status: 'sent', payload: result };
  }

  async function setRichMenu(richMenuId) {
    if (!channelAccessToken) {
      logger.info('Simulated LINE rich menu set', { richMenuId });
      return { success: true };
    }

    const url = `https://api.line.me/${apiVersion}/bot/richmenu/${richMenuId}`;
    const response = await fetchWithRetry(
      url,
      {
        method: 'POST',
        headers: { Authorization: `Bearer ${channelAccessToken}` },
      },
      2,
      500,
    );
    const data = await response.json();
    if (!response.ok || data.error) {
      throw new Error(data.error?.message || `Failed to set rich menu: ${response.status}`);
    }
    logger.info('LINE rich menu set', { richMenuId });
    return { success: true, payload: data };
  }

  async function linkRichMenuToUser(userId, richMenuId) {
    if (!channelAccessToken) {
      logger.info('Simulated LINE rich menu link', { userId, richMenuId });
      return { success: true };
    }

    const url = `https://api.line.me/${apiVersion}/bot/user/${userId}/richmenu/${richMenuId}`;
    const response = await fetchWithRetry(
      url,
      {
        method: 'POST',
        headers: { Authorization: `Bearer ${channelAccessToken}` },
      },
      2,
      500,
    );
    const data = await response.json();
    if (!response.ok || data.error) {
      throw new Error(data.error?.message || `Failed to link rich menu: ${response.status}`);
    }
    logger.info('LINE rich menu linked', { userId, richMenuId });
    return { success: true, payload: data };
  }

  async function verifyUserId(userId) {
    if (!channelAccessToken) {
      logger.info('Simulated LINE user ID verification', { userId });
      return { valid: true, userId, platform: 'line' };
    }

    try {
      const url = `https://api.line.me/${apiVersion}/bot/profile/${encodeURIComponent(userId)}`;
      const response = await fetchWithRetry(
        url,
        {
          headers: { Authorization: `Bearer ${channelAccessToken}` },
        },
        2,
        500,
      );
      const data = await response.json();
      if (data.error) {
        return { valid: false, userId, error: data.error.message };
      }
      return { valid: true, userId, platform: 'line', displayName: data.displayName, userId: data.userId };
    } catch (error) {
      logger.warn('LINE user ID verification failed', { userId, error: error.message });
      return { valid: false, userId, error: error.message };
    }
  }

  async function healthCheck() {
    if (!channelAccessToken) {
      return { status: 'ok', provider: 'line', mode: 'simulated' };
    }
    try {
      const url = `https://api.line.me/${apiVersion}/bot/info`;
      const response = await fetchWithRetry(
        url,
        {
          headers: { Authorization: `Bearer ${channelAccessToken}` },
        },
        1,
      );
      if (response.ok) {
        return { status: 'ok', provider: 'line', mode: 'real' };
      }
      return { status: 'degraded', provider: 'line', mode: 'real', error: 'unhealthy' };
    } catch (error) {
      return { status: 'degraded', provider: 'line', mode: 'real', error: error.message };
    }
  }

  return {
    ...base,
    initialize,
    sendText,
    sendImage,
    sendTemplate,
    sendFlexMessage,
    setRichMenu,
    linkRichMenuToUser,
    verifyUserId,
    healthCheck,
  };
}

export default createLINEAdapter;
