import { createBaseAdapter, fetchWithRetry, sleep } from './base-adapter.js';
import { createLogger } from '../../observability/logger.js';

const MESSAGE_TYPES = Object.freeze(['text', 'image', 'document', 'template', 'interactive']);
const RATE_LIMIT_WINDOW_MS = 60000;
const MAX_REQUESTS_PER_WINDOW = 80;

function validateWhatsAppMessage(payload) {
  if (!payload || typeof payload !== 'object' || Array.isArray(payload)) {
    return { valid: false, error: 'Message payload must be a non-null object' };
  }

  const type = typeof payload.type === 'string' ? payload.type : 'text';
  if (!MESSAGE_TYPES.includes(type)) {
    return { valid: false, error: `Unsupported WhatsApp message type: ${type}` };
  }

  if (type === 'text') {
    const text = typeof payload.text === 'string' ? payload.text.trim() : '';
    if (!text) return { valid: false, error: 'text is required for text messages' };
    if (text.length > 4096) return { valid: false, error: 'text exceeds 4096 characters' };
  }

  if (type === 'image' || type === 'document') {
    const link = typeof payload.mediaUrl === 'string' ? payload.mediaUrl.trim() : '';
    if (!link) return { valid: false, error: 'mediaUrl is required for media messages' };
    if (!/^https?:\/\//.test(link)) return { valid: false, error: 'mediaUrl must be a valid URL' };
  }

  return { valid: true, type };
}

export function createWhatsAppAdapter(config = {}) {
  const base = createBaseAdapter({ provider: 'whatsapp' });
  const logger = createLogger({ component: 'whatsapp-adapter' });

  const accessToken = (config.accessToken || process.env.ZOK_WHATSAPP_ACCESS_TOKEN || '').trim();
  const phoneNumberId = (config.phoneNumberId || process.env.ZOK_WHATSAPP_PHONE_NUMBER_ID || '').trim();
  const apiVersion = (config.apiVersion || process.env.ZOK_WHATSAPP_API_VERSION || 'v18.0').trim();
  const businessAccountId = (config.businessAccountId || process.env.ZOK_WHATSAPP_BUSINESS_ACCOUNT_ID || '').trim();

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
    if (!accessToken || !phoneNumberId) {
      throw new Error('WhatsApp access token and phone number ID are required for real mode');
    }

    const rateKey = phoneNumberId;
    const rate = checkRateLimit(rateKey);
    if (!rate.allowed) {
      const error = new Error('WhatsApp rate limit exceeded');
      error.retryAfter = Math.max(1, Math.ceil((rate.resetAt - Date.now()) / 1000));
      throw error;
    }

    const url = `https://graph.facebook.com/${apiVersion}/${phoneNumberId}/messages`;
    const response = await fetchWithRetry(
      url,
      {
        method: 'POST',
        headers: {
          Authorization: `Bearer ${accessToken}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(body),
      },
      3,
      1000,
    );

    const data = await response.json();
    if (!response.ok || data.error) {
      const error = new Error(data.error?.message || `WhatsApp API error ${response.status}`);
      error.status = response.status;
      error.payload = data;
      throw error;
    }

    return data;
  }

  async function initialize() {
    this.initialized = true;
    if (accessToken && phoneNumberId) {
      try {
        const url = `https://graph.facebook.com/${apiVersion}/${phoneNumberId}?fields=verified_name,display_phone_number`;
        const response = await fetchWithRetry(
          url,
          {
            headers: { Authorization: `Bearer ${accessToken}` },
          },
          2,
          500,
        );
        const data = await response.json();
        if (!response.ok || data.error) {
          logger.warn('WhatsApp phone number verification failed', { error: data.error?.message });
        } else {
          logger.info('WhatsApp phone number verified', {
            verifiedName: data.verified_name,
            displayPhoneNumber: data.display_phone_number,
          });
        }
      } catch (error) {
        logger.warn('WhatsApp verification check skipped', { error: error.message });
      }
    }
    logger.info('WhatsApp adapter initialized', {
      mode: accessToken && phoneNumberId ? 'real' : 'simulated',
      phoneNumberId: phoneNumberId || 'not-configured',
    });
  }

  async function sendText(contactId, text) {
    const validation = validateWhatsAppMessage({ type: 'text', text });
    if (!validation.valid) {
      throw new TypeError(validation.error);
    }

    if (!accessToken || !phoneNumberId) {
      logger.info('Simulated WhatsApp text message', { contactId, textLength: text.length });
      return { externalId: `whatsapp-sim-${Date.now()}`, status: 'sent' };
    }

    const body = {
      messaging_product: 'whatsapp',
      to: contactId,
      type: 'text',
      text: { body: text, preview_url: true },
    };

    const result = await makeRequest(body);
    logger.info('WhatsApp text message sent', { contactId, externalId: result.messages?.[0]?.id });
    return { externalId: result.messages?.[0]?.id, status: 'sent', payload: result };
  }

  async function sendImage(contactId, imageUrl, caption = '') {
    const validation = validateWhatsAppMessage({ type: 'image', mediaUrl: imageUrl });
    if (!validation.valid) {
      throw new TypeError(validation.error);
    }

    if (!accessToken || !phoneNumberId) {
      logger.info('Simulated WhatsApp image message', { contactId, imageUrl });
      return { externalId: `whatsapp-sim-img-${Date.now()}`, status: 'sent' };
    }

    const body = {
      messaging_product: 'whatsapp',
      to: contactId,
      type: 'image',
      image: { link: imageUrl, caption: caption || undefined },
    };

    const result = await makeRequest(body);
    logger.info('WhatsApp image message sent', { contactId, externalId: result.messages?.[0]?.id });
    return { externalId: result.messages?.[0]?.id, status: 'sent', payload: result };
  }

  async function sendDocument(contactId, documentUrl, filename = '') {
    const validation = validateWhatsAppMessage({ type: 'document', mediaUrl: documentUrl });
    if (!validation.valid) {
      throw new TypeError(validation.error);
    }

    if (!accessToken || !phoneNumberId) {
      logger.info('Simulated WhatsApp document message', { contactId, documentUrl, filename });
      return { externalId: `whatsapp-sim-doc-${Date.now()}`, status: 'sent' };
    }

    const body = {
      messaging_product: 'whatsapp',
      to: contactId,
      type: 'document',
      document: {
        link: documentUrl,
        filename: filename || 'document.pdf',
      },
    };

    const result = await makeRequest(body);
    logger.info('WhatsApp document message sent', { contactId, externalId: result.messages?.[0]?.id });
    return { externalId: result.messages?.[0]?.id, status: 'sent', payload: result };
  }

  async function sendTemplate(contactId, templateName, templateData = {}) {
    if (!accessToken || !phoneNumberId) {
      logger.info('Simulated WhatsApp template message', { contactId, templateName, templateData });
      return { externalId: `whatsapp-sim-tpl-${Date.now()}`, status: 'sent' };
    }

    const components = [];
    if (Object.keys(templateData).length > 0) {
      const bodyComponents = Object.entries(templateData).map(([key, value]) => ({
        type: 'body',
        parameters: [
          {
            type: 'text',
            text: String(value),
          },
        ],
      }));
      components.push(...bodyComponents);
    }

    const body = {
      messaging_product: 'whatsapp',
      to: contactId,
      type: 'template',
      template: {
        name: templateName,
        language: { code: 'en_US', policy: 'deterministic' },
        components,
      },
    };

    const result = await makeRequest(body);
    logger.info('WhatsApp template message sent', { contactId, templateName, externalId: result.messages?.[0]?.id });
    return { externalId: result.messages?.[0]?.id, status: 'sent', payload: result };
  }

  async function verifyContact(contactId) {
    if (!accessToken || !phoneNumberId) {
      logger.info('Simulated WhatsApp contact verification', { contactId });
      return { valid: true, contactId, platform: 'whatsapp' };
    }

    try {
      const url = `https://graph.facebook.com/${apiVersion}/${phoneNumberId}/contacts?blocking=wait&phone_number=${encodeURIComponent(contactId)}`;
      const response = await fetchWithRetry(
        url,
        {
          method: 'POST',
          headers: {
            Authorization: `Bearer ${accessToken}`,
            'Content-Type': 'application/json',
          },
        },
        2,
          500,
      );
      const data = await response.json();
      if (data.error) {
        return { valid: false, contactId, error: data.error.message };
      }
      return { valid: true, contactId, platform: 'whatsapp', waId: data.wa_id };
    } catch (error) {
      logger.warn('WhatsApp contact verification failed', { contactId, error: error.message });
      return { valid: false, contactId, error: error.message };
    }
  }

  async function healthCheck() {
    if (!accessToken || !phoneNumberId) {
      return { status: 'ok', provider: 'whatsapp', mode: 'simulated' };
    }
    try {
      const url = `https://graph.facebook.com/${apiVersion}/${phoneNumberId}?fields=verified_name`;
      const response = await fetchWithRetry(
        url,
        {
          headers: { Authorization: `Bearer ${accessToken}` },
        },
        1,
      );
      if (response.ok) {
        return { status: 'ok', provider: 'whatsapp', mode: 'real' };
      }
      return { status: 'degraded', provider: 'whatsapp', mode: 'real', error: 'unhealthy' };
    } catch (error) {
      return { status: 'degraded', provider: 'whatsapp', mode: 'real', error: error.message };
    }
  }

  return {
    ...base,
    initialize,
    sendText,
    sendImage,
    sendDocument,
    sendTemplate,
    verifyContact,
    healthCheck,
  };
}

export default createWhatsAppAdapter;
