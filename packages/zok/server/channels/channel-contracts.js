const UUID_PATTERN = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;

export const INBOUND_EVENT_TYPES = Object.freeze(['message', 'read', 'delivery', 'status']);
export const OUTBOUND_EVENT_TYPES = Object.freeze(['send', 'cancel', 'template']);

export const PROVIDERS = Object.freeze([
  'whatsapp',
  'line',
  'messenger',
  'tiktok',
]);

export function validateInboundEvent(event) {
  if (!event || typeof event !== 'object' || Array.isArray(event)) {
    return { valid: false, error: 'Event must be an object' };
  }

  const { type, provider, contactId, timestamp, payload } = event;

  if (typeof type !== 'string' || !INBOUND_EVENT_TYPES.includes(type)) {
    return { valid: false, error: `Invalid inbound event type: ${type}` };
  }

  if (typeof provider !== 'string' || !PROVIDERS.includes(provider)) {
    return { valid: false, error: `Invalid provider: ${provider}` };
  }

  if (typeof contactId !== 'string' || !contactId.trim()) {
    return { valid: false, error: 'contactId is required and must be a non-empty string' };
  }

  if (timestamp !== undefined && timestamp !== null && typeof timestamp !== 'string') {
    return { valid: false, error: 'timestamp must be a string' };
  }

  if (payload !== undefined && payload !== null && typeof payload !== 'object') {
    return { valid: false, error: 'payload must be an object' };
  }

  return { valid: true, normalized: { type, provider, contactId: contactId.trim(), timestamp, payload: payload || {} } };
}

export function validateOutboundEvent(event) {
  if (!event || typeof event !== 'object' || Array.isArray(event)) {
    return { valid: false, error: 'Event must be an object' };
  }

  const { type, provider, contactId, payload } = event;

  if (typeof type !== 'string' || !OUTBOUND_EVENT_TYPES.includes(type)) {
    return { valid: false, error: `Invalid outbound event type: ${type}` };
  }

  if (typeof provider !== 'string' || !PROVIDERS.includes(provider)) {
    return { valid: false, error: `Invalid provider: ${provider}` };
  }

  if (typeof contactId !== 'string' || !contactId.trim()) {
    return { valid: false, error: 'contactId is required and must be a non-empty string' };
  }

  if (payload !== undefined && payload !== null && typeof payload !== 'object') {
    return { valid: false, error: 'payload must be an object' };
  }

  return { valid: true, normalized: { type, provider, contactId: contactId.trim(), payload: payload || {} } };
}

export function buildIdempotencyKey(provider, eventType, externalId) {
  if (typeof provider !== 'string' || !provider.trim()) {
    throw new TypeError('Provider is required for idempotency key');
  }
  if (typeof eventType !== 'string' || !eventType.trim()) {
    throw new TypeError('Event type is required for idempotency key');
  }
  if (typeof externalId !== 'string' || !externalId.trim()) {
    throw new TypeError('External id is required for idempotency key');
  }

  const normalizedProvider = provider.trim().toLowerCase();
  const normalizedEventType = eventType.trim().toLowerCase();
  const normalizedExternalId = externalId.trim();

  const raw = `${normalizedProvider}:${normalizedEventType}:${normalizedExternalId}`;
  return Buffer.from(raw).toString('base64url');
}

export function parseIdempotencyKey(key) {
  if (typeof key !== 'string' || !key.trim()) {
    return null;
  }

  try {
    const decoded = Buffer.from(key.trim(), 'base64url').toString('utf8');
    const [provider, eventType, ...externalIdParts] = decoded.split(':');
    const externalId = externalIdParts.join(':');

    if (!provider || !eventType || !externalId) {
      return null;
    }

    return { provider, eventType, externalId };
  } catch {
    return null;
  }
}

export function createIdempotencyRecord(key, ttlSeconds = 86400) {
  if (typeof key !== 'string' || !key.trim()) {
    throw new TypeError('Idempotency key is required');
  }
  const ttl = Number(ttlSeconds);
  if (!Number.isSafeInteger(ttl) || ttl <= 0) {
    throw new TypeError('TTL must be a positive integer in seconds');
  }

  const now = new Date();
  const expiresAt = new Date(now.getTime() + ttl * 1000);

  return {
    key: key.trim(),
    ttl,
    createdAt: now.toISOString(),
    expiresAt: expiresAt.toISOString(),
  };
}

export function isIdempotencyKeyExpired(record) {
  if (!record || !record.expiresAt) return true;
  return new Date(record.expiresAt).getTime() <= Date.now();
}

export function validateWebhookSignatureConfig(config) {
  if (!config || typeof config !== 'object' || Array.isArray(config)) {
    throw new TypeError('Webhook signature config is required');
  }

  const { provider, secret, header } = config;

  if (typeof provider !== 'string' || !PROVIDERS.includes(provider)) {
    throw new TypeError('Valid provider is required for webhook signature verification');
  }

  if (typeof secret !== 'string' || secret.length < 16) {
    throw new TypeError('Webhook secret must be a string of at least 16 characters');
  }

  if (typeof header !== 'string' || !header.trim()) {
    throw new TypeError('Signature header name is required');
  }

  return { provider: provider.trim().toLowerCase(), secret, header: header.trim() };
}
