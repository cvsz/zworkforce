import { test } from 'node:test';
import assert from 'node:assert/strict';
import { createTikTokAdapter } from '../server/channels/adapters/tiktok-adapter.js';

test('createTikTokAdapter returns adapter object', () => {
  const adapter = createTikTokAdapter();
  assert.ok(adapter);
  assert.equal(adapter.provider, 'tiktok');
  assert.ok(typeof adapter.initialize === 'function');
  assert.ok(typeof adapter.sendText === 'function');
  assert.ok(typeof adapter.sendImage === 'function');
  assert.ok(typeof adapter.sendProductMessage === 'function');
  assert.ok(typeof adapter.sendOrderUpdate === 'function');
  assert.ok(typeof adapter.updateTransactionStatus === 'function');
  assert.ok(typeof adapter.verifyContact === 'function');
  assert.ok(typeof adapter.healthCheck === 'function');
});

test('TikTok adapter simulated mode sends text', async () => {
  const adapter = createTikTokAdapter();
  await adapter.initialize();
  const result = await adapter.sendText('U1234567890', 'Hello');
  assert.ok(result.externalId);
  assert.ok(result.externalId.startsWith('tiktok-sim-'));
  assert.equal(result.status, 'sent');
});

test('TikTok adapter simulated mode sends image', async () => {
  const adapter = createTikTokAdapter();
  await adapter.initialize();
  const result = await adapter.sendImage('U1234567890', 'https://example.com/image.png');
  assert.ok(result.externalId);
  assert.ok(result.externalId.startsWith('tiktok-sim-img-'));
  assert.equal(result.status, 'sent');
});

test('TikTok adapter simulated mode sends product message', async () => {
  const adapter = createTikTokAdapter();
  await adapter.initialize();
  const result = await adapter.sendProductMessage('U1234567890', 'PROD_001');
  assert.ok(result.externalId);
  assert.ok(result.externalId.startsWith('tiktok-sim-prod-'));
  assert.equal(result.status, 'sent');
});

test('TikTok adapter simulated mode sends order update', async () => {
  const adapter = createTikTokAdapter();
  await adapter.initialize();
  const result = await adapter.sendOrderUpdate('U1234567890', 'ORD_001', 'shipped');
  assert.ok(result.externalId);
  assert.ok(result.externalId.startsWith('tiktok-sim-ord-'));
  assert.equal(result.status, 'sent');
});

test('TikTok adapter simulated mode updates transaction status', async () => {
  const adapter = createTikTokAdapter();
  await adapter.initialize();
  const result = await adapter.updateTransactionStatus('U1234567890', 'TXN_001', 'completed');
  assert.ok(result.externalId);
  assert.ok(result.externalId.startsWith('tiktok-sim-txn-'));
  assert.equal(result.status, 'sent');
});

test('TikTok adapter validates text length', async () => {
  const adapter = createTikTokAdapter();
  await adapter.initialize();
  const longText = 'x'.repeat(2001);
  let error;
  try {
    await adapter.sendText('U1234567890', longText);
  } catch (e) {
    error = e;
  }
  assert.ok(error);
  assert.ok(error.message.includes('exceeds'));
});

test('TikTok adapter validates missing text', async () => {
  const adapter = createTikTokAdapter();
  await adapter.initialize();
  let error;
  try {
    await adapter.sendText('U1234567890', '');
  } catch (e) {
    error = e;
  }
  assert.ok(error);
  assert.ok(error.message.includes('text is required'));
});

test('TikTok adapter verifyContact works in simulated mode', async () => {
  const adapter = createTikTokAdapter();
  await adapter.initialize();
  const result = await adapter.verifyContact('U1234567890');
  assert.deepEqual(result, { valid: true, contactId: 'U1234567890', platform: 'tiktok' });
});

test('TikTok adapter healthCheck works', async () => {
  const adapter = createTikTokAdapter();
  const result = await adapter.healthCheck();
  assert.equal(result.provider, 'tiktok');
  assert.equal(result.mode, 'simulated');
  assert.equal(result.status, 'ok');
});
