import { test } from 'node:test';
import assert from 'node:assert/strict';
import {
  INBOUND_EVENT_TYPES,
  OUTBOUND_EVENT_TYPES,
  PROVIDERS,
  validateInboundEvent,
  validateOutboundEvent,
  buildIdempotencyKey,
  parseIdempotencyKey,
  createIdempotencyRecord,
  isIdempotencyKeyExpired,
  validateWebhookSignatureConfig,
} from '../server/channels/channel-contracts.js';

test('validateInboundEvent rejects invalid objects', () => {
  assert.deepEqual(validateInboundEvent(null), { valid: false, error: 'Event must be an object' });
  assert.deepEqual(validateInboundEvent('string'), { valid: false, error: 'Event must be an object' });
  assert.deepEqual(validateInboundEvent([]), { valid: false, error: 'Event must be an object' });
});

test('validateInboundEvent rejects invalid type', () => {
  assert.deepEqual(
    validateInboundEvent({ type: 'invalid', provider: 'whatsapp', contactId: '123' }),
    { valid: false, error: 'Invalid inbound event type: invalid' },
  );
});

test('validateInboundEvent rejects invalid provider', () => {
  assert.deepEqual(
    validateInboundEvent({ type: 'message', provider: 'unknown', contactId: '123' }),
    { valid: false, error: 'Invalid provider: unknown' },
  );
});

test('validateInboundEvent rejects missing contactId', () => {
  assert.deepEqual(
    validateInboundEvent({ type: 'message', provider: 'whatsapp' }),
    { valid: false, error: 'contactId is required and must be a non-empty string' },
  );
});

test('validateInboundEvent accepts valid inbound event', () => {
  const result = validateInboundEvent({ type: 'message', provider: 'whatsapp', contactId: '123', timestamp: '2024-01-01T00:00:00Z', payload: { text: 'hi' } });
  assert.equal(result.valid, true);
  assert.deepEqual(result.normalized, {
    type: 'message',
    provider: 'whatsapp',
    contactId: '123',
    timestamp: '2024-01-01T00:00:00Z',
    payload: { text: 'hi' },
  });
});

test('validateOutboundEvent rejects invalid objects', () => {
  assert.deepEqual(validateOutboundEvent(null), { valid: false, error: 'Event must be an object' });
  assert.deepEqual(validateOutboundEvent('string'), { valid: false, error: 'Event must be an object' });
});

test('validateOutboundEvent rejects invalid type', () => {
  assert.deepEqual(
    validateOutboundEvent({ type: 'invalid', provider: 'whatsapp', contactId: '123' }),
    { valid: false, error: 'Invalid outbound event type: invalid' },
  );
});

test('validateOutboundEvent accepts valid outbound event', () => {
  const result = validateOutboundEvent({ type: 'send', provider: 'line', contactId: '456', payload: { text: 'hello' } });
  assert.equal(result.valid, true);
  assert.deepEqual(result.normalized, {
    type: 'send',
    provider: 'line',
    contactId: '456',
    payload: { text: 'hello' },
  });
});

test('INBOUND_EVENT_TYPES and OUTBOUND_EVENT_TYPES are frozen arrays', () => {
  assert.ok(Array.isArray(INBOUND_EVENT_TYPES));
  assert.ok(Array.isArray(OUTBOUND_EVENT_TYPES));
  assert.deepEqual(INBOUND_EVENT_TYPES, ['message', 'read', 'delivery', 'status']);
  assert.deepEqual(OUTBOUND_EVENT_TYPES, ['send', 'cancel', 'template']);
});

test('PROVIDERS is a frozen array of supported providers', () => {
  assert.ok(Array.isArray(PROVIDERS));
  assert.ok(PROVIDERS.includes('whatsapp'));
  assert.ok(PROVIDERS.includes('line'));
  assert.ok(PROVIDERS.includes('messenger'));
  assert.ok(PROVIDERS.includes('tiktok'));
});

test('buildIdempotencyKey produces consistent keys', () => {
  const key1 = buildIdempotencyKey('whatsapp', 'message', 'msg-123');
  const key2 = buildIdempotencyKey('whatsapp', 'message', 'msg-123');
  assert.equal(key1, key2);
});

test('buildIdempotencyKey normalizes inputs', () => {
  const key = buildIdempotencyKey('WhatsApp', 'MESSAGE', 'msg-123');
  assert.equal(key, buildIdempotencyKey('whatsapp', 'message', 'msg-123'));
});

test('buildIdempotencyKey throws on invalid inputs', () => {
  assert.throws(() => buildIdempotencyKey('', 'message', 'msg-123'), /Provider is required/);
  assert.throws(() => buildIdempotencyKey('whatsapp', '', 'msg-123'), /Event type is required/);
  assert.throws(() => buildIdempotencyKey('whatsapp', 'message', ''), /External id is required/);
});

test('parseIdempotencyKey round-trips correctly', () => {
  const key = buildIdempotencyKey('whatsapp', 'message', 'msg-123');
  const parsed = parseIdempotencyKey(key);
  assert.deepEqual(parsed, { provider: 'whatsapp', eventType: 'message', externalId: 'msg-123' });
});

test('parseIdempotencyKey returns null for invalid keys', () => {
  assert.equal(parseIdempotencyKey(''), null);
  assert.equal(parseIdempotencyKey('not-a-valid-key'), null);
  assert.equal(parseIdempotencyKey(null), null);
});

test('createIdempotencyRecord creates valid record', () => {
  const record = createIdempotencyRecord('key-123', 3600);
  assert.equal(record.key, 'key-123');
  assert.equal(record.ttl, 3600);
  assert.ok(record.createdAt);
  assert.ok(record.expiresAt);
});

test('createIdempotencyRecord throws on invalid ttl', () => {
  assert.throws(() => createIdempotencyRecord('key', 0), /TTL must be a positive integer/);
  assert.throws(() => createIdempotencyRecord('key', -1), /TTL must be a positive integer/);
  assert.throws(() => createIdempotencyRecord('key', 1.5), /TTL must be a positive integer/);
});

test('isIdempotencyKeyExpired returns true for missing record', () => {
  assert.equal(isIdempotencyKeyExpired(null), true);
  assert.equal(isIdempotencyKeyExpired({}), true);
});

test('isIdempotencyKeyExpired returns true when past expiry', () => {
  assert.equal(isIdempotencyKeyExpired({ expiresAt: new Date(Date.now() - 1000).toISOString() }), true);
});

test('isIdempotencyKeyExpired returns false when not expired', () => {
  assert.equal(isIdempotencyKeyExpired({ expiresAt: new Date(Date.now() + 100000).toISOString() }), false);
});

test('validateWebhookSignatureConfig validates required fields', () => {
  assert.throws(() => validateWebhookSignatureConfig(null), /Webhook signature config is required/);
  assert.throws(() => validateWebhookSignatureConfig({}), /Valid provider is required/);
  assert.throws(() => validateWebhookSignatureConfig({ provider: 'unknown' }), /Valid provider is required/);
  assert.throws(() => validateWebhookSignatureConfig({ provider: 'whatsapp' }), /Webhook secret must be a string of at least 16 characters/);
  assert.throws(() => validateWebhookSignatureConfig({ provider: 'whatsapp', secret: 'short' }), /Webhook secret must be a string of at least 16 characters/);
  assert.throws(() => validateWebhookSignatureConfig({ provider: 'whatsapp', secret: 'a'.repeat(16) }), /Signature header name is required/);

  const result = validateWebhookSignatureConfig({ provider: 'whatsapp', secret: 'a'.repeat(16), header: 'X-Hub-Signature-256' });
  assert.deepEqual(result, { provider: 'whatsapp', secret: 'a'.repeat(16), header: 'X-Hub-Signature-256' });
});
