import { test } from 'node:test';
import assert from 'node:assert/strict';
import { createMessengerAdapter } from '../server/channels/adapters/messenger-adapter.js';

test('createMessengerAdapter returns adapter object', () => {
  const adapter = createMessengerAdapter();
  assert.ok(adapter);
  assert.equal(adapter.provider, 'messenger');
  assert.ok(typeof adapter.initialize === 'function');
  assert.ok(typeof adapter.sendText === 'function');
  assert.ok(typeof adapter.sendImage === 'function');
  assert.ok(typeof adapter.sendGenericTemplate === 'function');
  assert.ok(typeof adapter.sendQuickReplies === 'function');
  assert.ok(typeof adapter.setPersistentMenu === 'function');
  assert.ok(typeof adapter.verifyContact === 'function');
  assert.ok(typeof adapter.healthCheck === 'function');
});

test('Messenger adapter simulated mode sends text', async () => {
  const adapter = createMessengerAdapter();
  await adapter.initialize();
  const result = await adapter.sendText('PSID123', 'Hello');
  assert.ok(result.externalId);
  assert.ok(result.externalId.startsWith('messenger-sim-'));
  assert.equal(result.status, 'sent');
});

test('Messenger adapter simulated mode sends image', async () => {
  const adapter = createMessengerAdapter();
  await adapter.initialize();
  const result = await adapter.sendImage('PSID123', 'https://example.com/image.png');
  assert.ok(result.externalId);
  assert.ok(result.externalId.startsWith('messenger-sim-img-'));
  assert.equal(result.status, 'sent');
});

test('Messenger adapter simulated mode sends generic template', async () => {
  const adapter = createMessengerAdapter();
  await adapter.initialize();
  const result = await adapter.sendGenericTemplate('PSID123', {
    elements: [
      { title: 'Product 1', subtitle: 'Description', imageUrl: 'https://example.com/img.png' },
    ],
  });
  assert.ok(result.externalId);
  assert.ok(result.externalId.startsWith('messenger-sim-tpl-'));
  assert.equal(result.status, 'sent');
});

test('Messenger adapter simulated mode sends quick replies', async () => {
  const adapter = createMessengerAdapter();
  await adapter.initialize();
  const result = await adapter.sendQuickReplies('PSID123', 'Choose an option', [
    { title: 'Yes', payload: 'yes' },
    { title: 'No', payload: 'no' },
  ]);
  assert.ok(result.externalId);
  assert.ok(result.externalId.startsWith('messenger-sim-qr-'));
  assert.equal(result.status, 'sent');
});

test('Messenger adapter validates text length', async () => {
  const adapter = createMessengerAdapter();
  await adapter.initialize();
  const longText = 'x'.repeat(2001);
  let error;
  try {
    await adapter.sendText('PSID123', longText);
  } catch (e) {
    error = e;
  }
  assert.ok(error);
  assert.ok(error.message.includes('exceeds'));
});

test('Messenger adapter validates missing text', async () => {
  const adapter = createMessengerAdapter();
  await adapter.initialize();
  let error;
  try {
    await adapter.sendText('PSID123', '');
  } catch (e) {
    error = e;
  }
  assert.ok(error);
  assert.ok(error.message.includes('text is required'));
});

test('Messenger adapter setPersistentMenu works in simulated mode', async () => {
  const adapter = createMessengerAdapter();
  await adapter.initialize();
  const result = await adapter.setPersistentMenu('PSID123', [
    { title: 'Help', payload: 'help' },
  ]);
  assert.deepEqual(result, { success: true });
});

test('Messenger adapter verifyContact works in simulated mode', async () => {
  const adapter = createMessengerAdapter();
  await adapter.initialize();
  const result = await adapter.verifyContact('PSID123');
  assert.deepEqual(result, { valid: true, psid: 'PSID123', platform: 'messenger' });
});

test('Messenger adapter healthCheck works', async () => {
  const adapter = createMessengerAdapter();
  const result = await adapter.healthCheck();
  assert.equal(result.provider, 'messenger');
  assert.equal(result.mode, 'simulated');
  assert.equal(result.status, 'ok');
});
