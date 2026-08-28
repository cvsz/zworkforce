import { createHmac, timingSafeEqual } from 'node:crypto';
import { PROVIDERS, validateWebhookSignatureConfig } from './channel-contracts.js';

const PROVIDER_HEADERS = Object.freeze({
  whatsapp: 'x-hub-signature-256',
  messenger: 'x-hub-signature-256',
  line: 'x-line-signature',
  tiktok: 'x-tiktok-signature',
});

const SIGNATURE_PREFIX = 'sha256=';

function computeSignature(secret, payload) {
  if (typeof payload === 'string') {
    return createHmac('sha256', secret).update(payload, 'utf8').digest('hex');
  }
  const body = Buffer.isBuffer(payload) ? payload : Buffer.from(JSON.stringify(payload));
  return createHmac('sha256', secret).update(body).digest('hex');
}

export function createWebhookVerifier(config) {
  const { provider, secret, header } = validateWebhookSignatureConfig(config);
  const expectedHeader = header.toLowerCase();

  return {
    provider,
    verify(payload, signatureHeader) {
      if (typeof signatureHeader !== 'string' || !signatureHeader.trim()) {
        return { valid: false, error: 'Signature header is missing' };
      }

      const received = signatureHeader.trim().toLowerCase();
      const expected = computeSignature(secret, payload);

      let signatureValue = received;
      if (received.startsWith(SIGNATURE_PREFIX)) {
        signatureValue = received.slice(SIGNATURE_PREFIX.length);
      }

      if (signatureValue.length !== expected.length) {
        return { valid: false, error: 'Invalid signature length' };
      }

      const signatureBuffer = Buffer.from(signatureValue, 'hex');
      const expectedBuffer = Buffer.from(expected, 'hex');

      let isValid = false;
      try {
        isValid = timingSafeEqual(signatureBuffer, expectedBuffer);
      } catch {
        isValid = false;
      }

      if (!isValid) {
        return { valid: false, error: 'Invalid signature' };
      }

      let extractedPayload = payload;
      if (typeof payload === 'string') {
        try {
          extractedPayload = JSON.parse(payload);
        } catch {
          // keep as string if not JSON
        }
      } else if (Buffer.isBuffer(payload)) {
        try {
          extractedPayload = JSON.parse(payload.toString('utf8'));
        } catch {
          // keep as buffer if not JSON
        }
      }

      const eventType = extractEventType(provider, extractedPayload);

      return {
        valid: true,
        provider,
        eventType,
        payload: extractedPayload,
      };
    },
  };
}

export function verifyWebhookSignature(provider, secret, payload, signatureHeader) {
  if (!PROVIDERS.includes(provider)) {
    throw new TypeError('Unsupported provider for webhook verification');
  }
  const verifier = createWebhookVerifier({
    provider,
    secret,
    header: PROVIDER_HEADERS[provider],
  });
  return verifier.verify(payload, signatureHeader);
}

function extractEventType(provider, payload) {
  if (!payload || typeof payload !== 'object') {
    return 'unknown';
  }

  switch (provider) {
    case 'whatsapp':
    case 'messenger': {
      const entries = payload.entry;
      if (Array.isArray(entries) && entries[0]?.changes?.[0]?.value) {
        const value = entries[0].changes[0].value;
        if (value.messages) return 'message';
        if (value.reads) return 'read';
        if (value.deliveries) return 'delivery';
        if (value.statuses) return 'status';
      }
      return 'unknown';
    }
    case 'line': {
      const events = payload.events;
      if (Array.isArray(events) && events[0]) {
        const type = events[0].type;
        if (type === 'message') return 'message';
        if (type === 'read') return 'read';
        if (type === 'delivery') return 'delivery';
        if (type === 'postback') return 'status';
      }
      return 'unknown';
    }
    case 'tiktok': {
      if (payload.type === 'message') return 'message';
      if (payload.type === 'read') return 'read';
      if (payload.type === 'delivery') return 'delivery';
      if (payload.type === 'status') return 'status';
      return 'unknown';
    }
    default:
      return 'unknown';
  }
}

export function getExpectedSignatureHeader(provider) {
  if (!PROVIDERS.includes(provider)) {
    throw new TypeError('Unsupported provider');
  }
  return PROVIDER_HEADERS[provider];
}
