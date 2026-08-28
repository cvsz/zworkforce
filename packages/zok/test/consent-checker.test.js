import test from 'node:test';
import assert from 'node:assert/strict';
import { createConsentChecker } from '../server/channels/consent-checker.js';

function createMockPool() {
  const records = [];
  return {
    async query(text, values = []) {
      if (text.includes('INSERT INTO consent_records')) {
        records.push({ tenant_id: values[0], contact_id: values[1], channel: values[2], status: values[3], source: values[4] });
        return { rows: [] };
      }
      if (text.includes('FROM consent_records')) {
        const match = records.find(r => r.tenant_id === values[0] && r.contact_id === values[1] && r.channel === values[2]);
        if (match) {
          return { rows: [{ id: 'c1', tenant_id: match.tenant_id, contact_id: match.contact_id, channel: match.channel, status: match.status, source: match.source, recorded_at: new Date().toISOString() }] };
        }
        return { rows: [] };
      }
      if (text.includes('FROM contacts')) {
        const contactId = values[1];
        const externalId = values[2] || values[1];
        if (records.some(() => true)) {
          return { rows: [{ id: contactId === 'ext-1' ? 'uuid-1' : contactId }] };
        }
        return { rows: [] };
      }
      return { rows: [] };
    },
  };
}

test('consent checker returns false when no record exists', async () => {
  const checker = createConsentChecker(createMockPool());
  assert.equal(await checker.isAllowed('contact-1', 'whatsapp', 'tenant-1'), false);
});

test('consent checker returns true for granted status', async () => {
  const pool = createMockPool();
  const checker = createConsentChecker(pool);
  await checker.setConsent('contact-1', 'whatsapp', 'granted', 'tenant-1');
  assert.equal(await checker.isAllowed('contact-1', 'whatsapp', 'tenant-1'), true);
});

test('consent checker returns false for revoked status', async () => {
  const pool = createMockPool();
  const checker = createConsentChecker(pool);
  await checker.setConsent('contact-1', 'whatsapp', 'revoked', 'tenant-1');
  assert.equal(await checker.isAllowed('contact-1', 'whatsapp', 'tenant-1'), false);
});

test('consent checker throws on invalid inputs', async () => {
  const checker = createConsentChecker(createMockPool());
  await assert.rejects(() => checker.isAllowed('', 'whatsapp', 'tenant-1'), /contactId is required/);
  await assert.rejects(() => checker.isAllowed('contact-1', 'unknown', 'tenant-1'), /Invalid channel/);
  await assert.rejects(() => checker.setConsent('', 'whatsapp', 'granted', 'tenant-1'), /contactId is required/);
  await assert.rejects(() => checker.setConsent('contact-1', 'unknown', 'granted', 'tenant-1'), /Invalid channel/);
  await assert.rejects(() => checker.setConsent('contact-1', 'whatsapp', 'invalid', 'tenant-1'), /Consent status must be/);
});

test('consent checker setConsent returns record', async () => {
  const pool = createMockPool();
  const checker = createConsentChecker(pool);
  const record = await checker.setConsent('contact-1', 'line', 'granted', 'tenant-1', 'webhook');
  assert.equal(record.channel, 'line');
  assert.equal(record.status, 'granted');
  assert.equal(record.source, 'webhook');
});

test('consent checker getConsent returns record or null', async () => {
  const pool = createMockPool();
  const checker = createConsentChecker(pool);
  assert.equal(await checker.getConsent('contact-1', 'whatsapp', 'tenant-1'), null);

  await checker.setConsent('contact-1', 'whatsapp', 'granted', 'tenant-1');
  const record = await checker.getConsent('contact-1', 'whatsapp', 'tenant-1');
  assert.ok(record);
  assert.equal(record.channel, 'whatsapp');
  assert.equal(record.status, 'granted');
});

test('consent checker works without pool (in-memory mode)', async () => {
  const checker = createConsentChecker(null);
  assert.equal(await checker.isAllowed('contact-1', 'whatsapp'), false);

  await checker.setConsent('contact-1', 'whatsapp', 'granted');
  assert.equal(await checker.isAllowed('contact-1', 'whatsapp'), true);

  await checker.setConsent('contact-1', 'whatsapp', 'revoked');
  assert.equal(await checker.isAllowed('contact-1', 'whatsapp'), false);
});

test('consent checker in-memory mode returns record via getConsent', async () => {
  const checker = createConsentChecker(null);
  await checker.setConsent('contact-1', 'line', 'granted');
  const record = await checker.getConsent('contact-1', 'line');
  assert.ok(record);
  assert.equal(record.channel, 'line');
  assert.equal(record.status, 'granted');
});

test('consent checker handles different channels independently', async () => {
  const pool = createMockPool();
  const checker = createConsentChecker(pool);
  await checker.setConsent('contact-1', 'whatsapp', 'granted', 'tenant-1');
  await checker.setConsent('contact-1', 'line', 'revoked', 'tenant-1');

  assert.equal(await checker.isAllowed('contact-1', 'whatsapp', 'tenant-1'), true);
  assert.equal(await checker.isAllowed('contact-1', 'line', 'tenant-1'), false);
});
