import { test } from 'node:test';
import assert from 'node:assert/strict';
import { createLINEAdapter } from '../server/channels/adapters/line-adapter.js';

test('createLINEAdapter returns adapter object', () => {
  const adapter = createLINEAdapter();
  assert.ok(adapter);
  assert.equal(adapter.provider, 'line');
  assert.ok(typeof adapter.initialize === 'function');
  assert.ok(typeof adapter.sendText === 'function');
  assert.ok(typeof adapter.sendImage === 'function');
  assert.ok(typeof adapter.sendTemplate === 'function');
  assert.ok(typeof adapter.sendFlexMessage === 'function');
  assert.ok(typeof adapter.setRichMenu === 'function');
  assert.ok(typeof adapter.linkRichMenuToUser === 'function');
  assert.ok(typeof adapter.verifyUserId === 'function');
  assert.ok(typeof adapter.healthCheck === 'function');
});

test('LINE adapter simulated mode sends text', async () => {
  const adapter = createLINEAdapter();
  await adapter.initialize();
  const result = await adapter.sendText('U1234567890', 'Hello');
  assert.ok(result.externalId);
  assert.ok(result.externalId.startsWith('line-sim-'));
  assert.equal(result.status, 'sent');
});

test('LINE adapter simulated mode sends image', async () => {
  const adapter = createLINEAdapter();
  await adapter.initialize();
  const result = await adapter.sendImage('U1234567890', 'https://example.com/image.png');
  assert.ok(result.externalId);
  assert.ok(result.externalId.startsWith('line-sim-img-'));
  assert.equal(result.status, 'sent');
});

test('LINE adapter simulated mode sends template', async () => {
  const adapter = createLINEAdapter();
  await adapter.initialize();
  const result = await adapter.sendTemplate('U1234567890', 'order_confirmation', { text: 'Your order is ready', actions: [] });
  assert.ok(result.externalId);
  assert.ok(result.externalId.startsWith('line-sim-tpl-'));
  assert.equal(result.status, 'sent');
});

test('LINE adapter simulated mode sends flex message', async () => {
  const adapter = createLINEAdapter();
  await adapter.initialize();
  const result = await adapter.sendFlexMessage('U1234567890', { type: 'bubble', body: { contents: [] } });
  assert.ok(result.externalId);
  assert.ok(result.externalId.startsWith('line-sim-flex-'));
  assert.equal(result.status, 'sent');
});

test('LINE adapter validates text length', async () => {
  const adapter = createLINEAdapter();
  await adapter.initialize();
  const longText = 'x'.repeat(5001);
  let error;
  try {
    await adapter.sendText('U1234567890', longText);
  } catch (e) {
    error = e;
  }
  assert.ok(error);
  assert.ok(error.message.includes('exceeds'));
});

test('LINE adapter validates missing text', async () => {
  const adapter = createLINEAdapter();
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

test('LINE adapter verifyUserId works in simulated mode', async () => {
  const adapter = createLINEAdapter();
  await adapter.initialize();
  const result = await adapter.verifyUserId('U1234567890');
  assert.deepEqual(result, { valid: true, userId: 'U1234567890', platform: 'line' });
});

test('LINE adapter setRichMenu works in simulated mode', async () => {
  const adapter = createLINEAdapter();
  await adapter.initialize();
  const result = await adapter.setRichMenu('richmenu-123');
  assert.deepEqual(result, { success: true });
});

test('LINE adapter healthCheck works', async () => {
  const adapter = createLINEAdapter();
  const result = await adapter.healthCheck();
  assert.equal(result.provider, 'line');
  assert.equal(result.mode, 'simulated');
  assert.equal(result.status, 'ok');
});
