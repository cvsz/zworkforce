import { test } from 'node:test';
import assert from 'node:assert/strict';
import {
  createWebhookVerifier,
  verifyWebhookSignature,
  getExpectedSignatureHeader,
} from '../server/channels/webhook-verifier.js';
import { createHmac } from 'node:crypto';

function computeSignature(secret, payload) {
  const body = Buffer.isBuffer(payload) ? payload : Buffer.from(
    typeof payload === 'string' ? payload : JSON.stringify(payload),
  );
  return createHmac('sha256', secret).update(body).digest('hex');
}

test('createWebhookVerifier validates config', () => {
  assert.throws(() => createWebhookVerifier({}), /Valid provider is required/);
  assert.throws(() => createWebhookVerifier({ provider: 'unknown' }), /Valid provider is required/);
  assert.throws(() => createWebhookVerifier({ provider: 'whatsapp', secret: 'short' }), /Webhook secret must be a string of at least 16 characters/);
});

test('verifyWebhookSignature rejects missing signature header', () => {
  const verifier = createWebhookVerifier({ provider: 'whatsapp', secret: 'a'.repeat(16), header: 'x-hub-signature-256' });
  const result = verifier.verify('{}', '');
  assert.equal(result.valid, false);
  assert.ok(result.error.includes('missing'));
});

test('verifyWebhookSignature accepts valid HMAC-SHA256 signature', () => {
  const secret = 'test-webhook-secret-123';
  const payload = JSON.stringify({ event: 'test' });
  const signature = computeSignature(secret, payload);
  const header = `sha256=${signature}`;

  const verifier = createWebhookVerifier({ provider: 'whatsapp', secret, header: 'x-hub-signature-256' });
  const result = verifier.verify(payload, header);

  assert.equal(result.valid, true);
  assert.equal(result.provider, 'whatsapp');
  assert.ok(result.payload);
});

test('verifyWebhookSignature rejects invalid signature', () => {
  const verifier = createWebhookVerifier({ provider: 'whatsapp', secret: 'a'.repeat(16), header: 'x-hub-signature-256' });
  const result = verifier.verify('{}', 'sha256=invalid');
  assert.equal(result.valid, false);
  assert.ok(result.error.includes('Invalid'));
});

test('verifyWebhookSignature accepts Buffer payload', () => {
  const secret = 'test-webhook-secret-123';
  const payload = Buffer.from(JSON.stringify({ event: 'test' }));
  const signature = computeSignature(secret, payload);
  const header = `sha256=${signature}`;

  const verifier = createWebhookVerifier({ provider: 'messenger', secret, header: 'x-hub-signature-256' });
  const result = verifier.verify(payload, header);

  assert.equal(result.valid, true);
  assert.equal(result.provider, 'messenger');
});

test('verifyWebhookSignature extracts event type for WhatsApp', () => {
  const verifier = createWebhookVerifier({ provider: 'whatsapp', secret: 'a'.repeat(16), header: 'x-hub-signature-256' });
  
  const messagePayload = {
    entry: [
      {
        changes: [
          {
            value: {
              messages: [
                { id: 'msg-1' }
              ]
            }
          }
        ]
      }
    ]
  };
  const signature = computeSignature('a'.repeat(16), JSON.stringify(messagePayload));
  const result = verifier.verify(JSON.stringify(messagePayload), `sha256=${signature}`);
  assert.equal(result.valid, true);
  assert.equal(result.eventType, 'message');

  const readPayload = {
    entry: [
      {
        changes: [
          {
            value: {
              reads: [
                { id: 'read-1' }
              ]
            }
          }
        ]
      }
    ]
  };
  const readSignature = computeSignature('a'.repeat(16), JSON.stringify(readPayload));
  const result2 = verifier.verify(JSON.stringify(readPayload), `sha256=${readSignature}`);
  assert.equal(result2.valid, true);
  assert.equal(result2.eventType, 'read');
});

test('verifyWebhookSignature extracts event type for LINE', () => {
  const verifier = createWebhookVerifier({ provider: 'line', secret: 'a'.repeat(16), header: 'x-line-signature' });
  
  const messagePayload = { events: [{ type: 'message', message: { id: 'msg-1' } }] };
  const signature = computeSignature('a'.repeat(16), JSON.stringify(messagePayload));
  const result = verifier.verify(JSON.stringify(messagePayload), `sha256=${signature}`);
  assert.equal(result.valid, true);
  assert.equal(result.eventType, 'message');

  const postbackPayload = { events: [{ type: 'postback', postback: { data: 'action' } }] };
  const postbackSignature = computeSignature('a'.repeat(16), JSON.stringify(postbackPayload));
  const result2 = verifier.verify(JSON.stringify(postbackPayload), `sha256=${postbackSignature}`);
  assert.equal(result2.valid, true);
  assert.equal(result2.eventType, 'status');
});

test('verifyWebhookSignature extracts event type for Messenger', () => {
  const verifier = createWebhookVerifier({ provider: 'messenger', secret: 'a'.repeat(16), header: 'x-hub-signature-256' });
  
  const messagePayload = {
    entry: [
      {
        changes: [
          {
            value: {
              messages: [
                { mid: 'msg-1' }
              ]
            }
          }
        ]
      }
    ]
  };
  const signature = computeSignature('a'.repeat(16), JSON.stringify(messagePayload));
  const result = verifier.verify(JSON.stringify(messagePayload), `sha256=${signature}`);
  assert.equal(result.valid, true);
  assert.equal(result.eventType, 'message');
});

test('verifyWebhookSignature extracts event type for TikTok', () => {
  const verifier = createWebhookVerifier({ provider: 'tiktok', secret: 'a'.repeat(16), header: 'x-tiktok-signature' });
  
  const messagePayload = { type: 'message', data: { id: 'msg-1' } };
  const signature = computeSignature('a'.repeat(16), JSON.stringify(messagePayload));
  const result = verifier.verify(JSON.stringify(messagePayload), `sha256=${signature}`);
  assert.equal(result.valid, true);
  assert.equal(result.eventType, 'message');

  const statusPayload = { type: 'status', data: { status: 'sent' } };
  const statusSignature = computeSignature('a'.repeat(16), JSON.stringify(statusPayload));
  const result2 = verifier.verify(JSON.stringify(statusPayload), `sha256=${statusSignature}`);
  assert.equal(result2.valid, true);
  assert.equal(result2.eventType, 'status');
});

test('verifyWebhookSignature returns unknown for unrecognized payload', () => {
  const verifier = createWebhookVerifier({ provider: 'whatsapp', secret: 'a'.repeat(16), header: 'x-hub-signature-256' });
  const payload = JSON.stringify({});
  const signature = computeSignature('a'.repeat(16), payload);
  const result = verifier.verify(payload, `sha256=${signature}`);
  assert.equal(result.valid, true);
  assert.equal(result.eventType, 'unknown');
});

test('getExpectedSignatureHeader returns correct header for each provider', () => {
  assert.equal(getExpectedSignatureHeader('whatsapp'), 'x-hub-signature-256');
  assert.equal(getExpectedSignatureHeader('messenger'), 'x-hub-signature-256');
  assert.equal(getExpectedSignatureHeader('line'), 'x-line-signature');
  assert.equal(getExpectedSignatureHeader('tiktok'), 'x-tiktok-signature');
});

test('getExpectedSignatureHeader throws for unknown provider', () => {
  assert.throws(() => getExpectedSignatureHeader('unknown'), /Unsupported provider/);
});

test('verifyWebhookSignature convenience function works', () => {
  const secret = 'test-secret-123456789012';
  const payload = JSON.stringify({ hello: 'world' });
  const signature = computeSignature(secret, payload);
  
  const result = verifyWebhookSignature('whatsapp', secret, payload, `sha256=${signature}`);
  assert.equal(result.valid, true);
  assert.equal(result.provider, 'whatsapp');
});
