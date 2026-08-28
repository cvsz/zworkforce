import { test } from 'node:test';
import assert from 'node:assert/strict';
import { createWhatsAppAdapter } from '../server/channels/adapters/whatsapp-adapter.js';

test('createWhatsAppAdapter returns adapter object', () => {
  const adapter = createWhatsAppAdapter();
  assert.ok(adapter);
  assert.equal(adapter.provider, 'whatsapp');
  assert.ok(typeof adapter.initialize === 'function');
  assert.ok(typeof adapter.sendText === 'function');
  assert.ok(typeof adapter.sendImage === 'function');
  assert.ok(typeof adapter.sendDocument === 'function');
  assert.ok(typeof adapter.sendTemplate === 'function');
  assert.ok(typeof adapter.verifyContact === 'function');
  assert.ok(typeof adapter.healthCheck === 'function');
});

test('WhatsApp adapter simulated mode sends text', async () => {
  const adapter = createWhatsAppAdapter();
  await adapter.initialize();
  const result = await adapter.sendText('+1234567890', 'Hello');
  assert.ok(result.externalId);
  assert.ok(result.externalId.startsWith('whatsapp-sim-'));
  assert.equal(result.status, 'sent');
});

test('WhatsApp adapter simulated mode sends image', async () => {
  const adapter = createWhatsAppAdapter();
  await adapter.initialize();
  const result = await adapter.sendImage('+1234567890', 'https://example.com/image.png');
  assert.ok(result.externalId);
  assert.ok(result.externalId.startsWith('whatsapp-sim-img-'));
  assert.equal(result.status, 'sent');
});

test('WhatsApp adapter simulated mode sends document', async () => {
  const adapter = createWhatsAppAdapter();
  await adapter.initialize();
  const result = await adapter.sendDocument('+1234567890', 'https://example.com/doc.pdf', 'report.pdf');
  assert.ok(result.externalId);
  assert.ok(result.externalId.startsWith('whatsapp-sim-doc-'));
  assert.equal(result.status, 'sent');
});

test('WhatsApp adapter simulated mode sends template', async () => {
  const adapter = createWhatsAppAdapter();
  await adapter.initialize();
  const result = await adapter.sendTemplate('+1234567890', 'shipping_update', { customer_name: 'John' });
  assert.ok(result.externalId);
  assert.ok(result.externalId.startsWith('whatsapp-sim-tpl-'));
  assert.equal(result.status, 'sent');
});

test('WhatsApp adapter validates text length', async () => {
  const adapter = createWhatsAppAdapter();
  await adapter.initialize();
  const longText = 'x'.repeat(4097);
  let error;
  try {
    await adapter.sendText('+1234567890', longText);
  } catch (e) {
    error = e;
  }
  assert.ok(error);
  assert.ok(error.message.includes('exceeds'));
});

test('WhatsApp adapter validates missing text', async () => {
  const adapter = createWhatsAppAdapter();
  await adapter.initialize();
  let error;
  try {
    await adapter.sendText('+1234567890', '');
  } catch (e) {
    error = e;
  }
  assert.ok(error);
  assert.ok(error.message.includes('text is required'));
});

test('WhatsApp adapter validates media URL', async () => {
  const adapter = createWhatsAppAdapter();
  await adapter.initialize();
  let error;
  try {
    await adapter.sendImage('+1234567890', 'not-a-url');
  } catch (e) {
    error = e;
  }
  assert.ok(error);
  assert.ok(error.message.includes('mediaUrl must be a valid URL'));
});

test('WhatsApp adapter verifyContact works in simulated mode', async () => {
  const adapter = createWhatsAppAdapter();
  await adapter.initialize();
  const result = await adapter.verifyContact('+1234567890');
  assert.deepEqual(result, { valid: true, contactId: '+1234567890', platform: 'whatsapp' });
});

test('WhatsApp adapter healthCheck works', async () => {
  const adapter = createWhatsAppAdapter();
  const result = await adapter.healthCheck();
  assert.equal(result.provider, 'whatsapp');
  assert.equal(result.mode, 'simulated');
  assert.equal(result.status, 'ok');
});
