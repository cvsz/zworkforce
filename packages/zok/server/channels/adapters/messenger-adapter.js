import { createBaseAdapter, fetchWithRetry, sleep } from './base-adapter.js';
import { createLogger } from '../../observability/logger.js';

const MESSAGE_TYPES = Object.freeze(['text', 'image', 'template', 'generic_template', 'quick_replies']);
const RATE_LIMIT_WINDOW_MS = 60000;
const MAX_REQUESTS_PER_WINDOW = 200;

function validateMessengerMessage(payload) {
  if (!payload || typeof payload !== 'object' || Array.isArray(payload)) {
    return { valid: false, error: 'Message payload must be a non-null object' };
  }

  const type = typeof payload.type === 'string' ? payload.type : 'text';
  if (!MESSAGE_TYPES.includes(type)) {
    return { valid: false, error: `Unsupported Messenger message type: ${type}` };
  }

  if (type === 'text') {
    const text = typeof payload.text === 'string' ? payload.text.trim() : '';
    if (!text) return { valid: false, error: 'text is required for text messages' };
    if (text.length > 2000) return { valid: false, error: 'text exceeds 2000 characters' };
  }

  return { valid: true, type };
}

export function createMessengerAdapter(config = {}) {
  const base = createBaseAdapter({ provider: 'messenger' });
  const logger = createLogger({ component: 'messenger-adapter' });

  const pageAccessToken = (config.pageAccessToken || process.env.ZOK_MESSENGER_PAGE_ACCESS_TOKEN || '').trim();
  const appSecret = (config.appSecret || process.env.ZOK_MESSENGER_APP_SECRET || '').trim();
  const appId = (config.appId || process.env.ZOK_MESSENGER_APP_ID || '').trim();
  const pageId = (config.pageId || process.env.ZOK_MESSENGER_PAGE_ID || '').trim();
  const apiVersion = (config.apiVersion || process.env.ZOK_MESSENGER_API_VERSION || 'v18.0').trim();

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

  async function makeRequest(psid, body) {
    if (!pageAccessToken) {
      throw new Error('Messenger page access token is required for real mode');
    }

    const rateKey = psid;
    const rate = checkRateLimit(rateKey);
    if (!rate.allowed) {
      const error = new Error('Messenger rate limit exceeded');
      error.retryAfter = Math.max(1, Math.ceil((rate.resetAt - Date.now()) / 1000));
      throw error;
    }

    const url = `https://graph.facebook.com/${apiVersion}/me/messages`;
    const response = await fetchWithRetry(
      url,
      {
        method: 'POST',
        headers: {
          Authorization: `Bearer ${pageAccessToken}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          recipient: { id: psid },
          ...body,
        }),
      },
      3,
      1000,
    );

    const data = await response.json();
    if (!response.ok || data.error) {
      const error = new Error(data.error?.message || `Messenger API error ${response.status}`);
      error.status = response.status;
      error.payload = data;
      throw error;
    }

    return data;
  }

  async function initialize() {
    this.initialized = true;
    if (pageAccessToken && pageId) {
      try {
        const url = `https://graph.facebook.com/${apiVersion}/${pageId}?fields=name,fan_count`;
        const response = await fetchWithRetry(
          url,
          {
            headers: { Authorization: `Bearer ${pageAccessToken}` },
          },
          2,
          500,
        );
        const data = await response.json();
        if (!response.ok || data.error) {
          logger.warn('Messenger page verification failed', { error: data.error?.message });
        } else {
          logger.info('Messenger page verified', {
            pageName: data.name,
            pageId,
            fanCount: data.fan_count,
          });
        }
      } catch (error) {
        logger.warn('Messenger verification check skipped', { error: error.message });
      }
    }
    logger.info('Messenger adapter initialized', {
      mode: pageAccessToken ? 'real' : 'simulated',
      pageId: pageId || 'not-configured',
    });
  }

  async function sendText(psid, text) {
    const validation = validateMessengerMessage({ type: 'text', text });
    if (!validation.valid) {
      throw new TypeError(validation.error);
    }

    if (!pageAccessToken) {
      logger.info('Simulated Messenger text message', { psid, textLength: text.length });
      return { externalId: `messenger-sim-${Date.now()}`, status: 'sent' };
    }

    const result = await makeRequest(psid, {
      message: { text, quick_replies: undefined },
    });
    logger.info('Messenger text message sent', { psid, externalId: result.message_id });
    return { externalId: result.message_id, status: 'sent', payload: result };
  }

  async function sendImage(psid, imageUrl, caption = '') {
    const validation = validateMessengerMessage({ type: 'image' });
    if (!validation.valid) {
      throw new TypeError(validation.error);
    }

    if (!pageAccessToken) {
      logger.info('Simulated Messenger image message', { psid, imageUrl });
      return { externalId: `messenger-sim-img-${Date.now()}`, status: 'sent' };
    }

    const result = await makeRequest(psid, {
      message: {
        attachment: {
          type: 'image',
          payload: { url: imageUrl, is_reusable: true },
          ...(caption ? { caption } : {}),
        },
      },
    });
    logger.info('Messenger image message sent', { psid, externalId: result.message_id });
    return { externalId: result.message_id, status: 'sent', payload: result };
  }

  async function sendGenericTemplate(psid, templateData) {
    if (!pageAccessToken) {
      logger.info('Simulated Messenger generic template', { psid, templateData });
      return { externalId: `messenger-sim-tpl-${Date.now()}`, status: 'sent' };
    }

    const elements = Array.isArray(templateData.elements) ? templateData.elements.slice(0, 10) : [];
    const result = await makeRequest(psid, {
      message: {
        attachment: {
          type: 'template',
          payload: {
            template_type: 'generic',
            elements: elements.map(el => ({
              title: typeof el.title === 'string' ? el.title : '',
              image_url: typeof el.imageUrl === 'string' ? el.imageUrl : undefined,
              subtitle: typeof el.subtitle === 'string' ? el.subtitle : undefined,
              default_action: el.defaultAction ? {
                type: 'web_url',
                url: el.defaultAction.url,
                webview_height_ratio: 'tall',
              } : undefined,
              buttons: Array.isArray(el.buttons) ? el.buttons.map(btn => ({
                type: btn.type || 'web_url',
                url: btn.url || '',
                title: btn.title || 'View',
              })) : [],
            })),
          },
        },
      },
    });
    logger.info('Messenger generic template sent', { psid, externalId: result.message_id });
    return { externalId: result.message_id, status: 'sent', payload: result };
  }

  async function sendQuickReplies(psid, text, quickReplies = []) {
    const validation = validateMessengerMessage({ type: 'text', text });
    if (!validation.valid) {
      throw new TypeError(validation.error);
    }

    if (!pageAccessToken) {
      logger.info('Simulated Messenger quick replies', { psid, textLength: text.length, quickReplies });
      return { externalId: `messenger-sim-qr-${Date.now()}`, status: 'sent' };
    }

    const result = await makeRequest(psid, {
      message: {
        text,
        quick_replies: quickReplies.slice(0, 13).map(qr => ({
          content_type: 'text',
          title: typeof qr.title === 'string' ? qr.title.slice(0, 20) : 'Option',
          payload: typeof qr.payload === 'string' ? qr.payload : '',
        })),
      },
    });
    logger.info('Messenger quick replies sent', { psid, externalId: result.message_id });
    return { externalId: result.message_id, status: 'sent', payload: result };
  }

  async function setPersistentMenu(psid, menuItems = []) {
    if (!pageAccessToken) {
      logger.info('Simulated Messenger persistent menu set', { psid });
      return { success: true };
    }

    const url = `https://graph.facebook.com/${apiVersion}/me/messenger_profile`;
    const response = await fetchWithRetry(
      url,
      {
        method: 'POST',
        headers: {
          Authorization: `Bearer ${pageAccessToken}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          persistent_menu: [
            {
              locale: 'default',
              composer_input_disabled: false,
              call_to_actions: menuItems.slice(0, 3).map(item => ({
                type: 'postback',
                title: typeof item.title === 'string' ? item.title.slice(0, 30) : 'Menu',
                payload: typeof item.payload === 'string' ? item.payload : '',
              })),
            },
          ],
        }),
      },
      2,
      500,
    );
    const data = await response.json();
    if (!response.ok || data.error) {
      throw new Error(data.error?.message || `Failed to set persistent menu: ${response.status}`);
    }
    logger.info('Messenger persistent menu set', { psid });
    return { success: true, payload: data };
  }

  async function verifyContact(psid) {
    if (!pageAccessToken) {
      logger.info('Simulated Messenger PSID verification', { psid });
      return { valid: true, psid, platform: 'messenger' };
    }

    try {
      const url = `https://graph.facebook.com/${apiVersion}/${psid}?fields=id,name,profile_pic`;
      const response = await fetchWithRetry(
        url,
        {
          headers: { Authorization: `Bearer ${pageAccessToken}` },
        },
        2,
        500,
      );
      const data = await response.json();
      if (data.error) {
        return { valid: false, psid, error: data.error.message };
      }
      return { valid: true, psid, platform: 'messenger', name: data.name, profilePic: data.profile_pic };
    } catch (error) {
      logger.warn('Messenger PSID verification failed', { psid, error: error.message });
      return { valid: false, psid, error: error.message };
    }
  }

  async function healthCheck() {
    if (!pageAccessToken) {
      return { status: 'ok', provider: 'messenger', mode: 'simulated' };
    }
    try {
      const url = `https://graph.facebook.com/${apiVersion}/me`;
      const response = await fetchWithRetry(
        url,
        {
          headers: { Authorization: `Bearer ${pageAccessToken}` },
          method: 'GET',
        },
        1,
      );
      if (response.ok) {
        return { status: 'ok', provider: 'messenger', mode: 'real' };
      }
      return { status: 'degraded', provider: 'messenger', mode: 'real', error: 'unhealthy' };
    } catch (error) {
      return { status: 'degraded', provider: 'messenger', mode: 'real', error: error.message };
    }
  }

  return {
    ...base,
    initialize,
    sendText,
    sendImage,
    sendGenericTemplate,
    sendQuickReplies,
    setPersistentMenu,
    verifyContact,
    healthCheck,
  };
}

export default createMessengerAdapter;
