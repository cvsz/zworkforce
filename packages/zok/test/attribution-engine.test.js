import test from 'node:test';
import assert from 'node:assert/strict';
import { createAttributionEngine } from '../server/commerce/attribution-engine.js';

const tenantId = 'bbbbbbbb-2222-4222-8222-bbbbbbbbbbbb';

const mockPool = {
  async connect() {
    return {
      async query(text, values = []) {
        if (text.trimStart().startsWith('SELECT')) {
          return { rows: [] };
        }
        return { rows: [] };
      },
      release() {},
    };
  },
};

function createEngine() {
  return createAttributionEngine({
    postgresPool: mockPool,
    jsonStorage: null,
    logger: { info: () => {}, warn: () => {}, error: () => {} },
  });
}

test('createAttributionEngine fails closed without pool', () => {
  assert.throws(() => createAttributionEngine({}), /PostgreSQL pool is required/i);
});

test('recordTouchpoint rejects invalid tenantId', async () => {
  const engine = createEngine();
  let threw = false;
  try {
    await engine.recordTouchpoint({ tenantId: 'bad', contactId: 'c1', channel: 'whatsapp' });
  } catch (e) {
    threw = true;
    assert.match(e.message, /Invalid attribution touchpoint/i);
  }
  assert.ok(threw, 'expected recordTouchpoint to reject invalid tenantId');
});

test('recordTouchpoint rejects empty contactId', async () => {
  const engine = createEngine();
  let threw = false;
  try {
    await engine.recordTouchpoint({ tenantId, contactId: '', channel: 'whatsapp' });
  } catch (e) {
    threw = true;
    assert.match(e.message, /Invalid attribution touchpoint/i);
  }
  assert.ok(threw, 'expected recordTouchpoint to reject empty contactId');
});

test('recordTouchpoint rejects invalid channel', async () => {
  const engine = createEngine();
  let threw = false;
  try {
    await engine.recordTouchpoint({ tenantId, contactId: 'c1', channel: 'telegram' });
  } catch (e) {
    threw = true;
    assert.match(e.message, /Invalid attribution touchpoint/i);
  }
  assert.ok(threw, 'expected recordTouchpoint to reject invalid channel');
});

test('recordTouchpoint stores valid touchpoint via postgres', async () => {
  const engine = createEngine();
  const touchpoint = await engine.recordTouchpoint({
    tenantId,
    contactId: 'contact-1',
    channel: 'whatsapp',
    campaignId: tenantId,
    eventType: 'campaign_sent',
    messageId: 'msg-1',
    metadata: { campaignId: '1' },
  });

  assert.ok(touchpoint.id);
  assert.equal(touchpoint.tenantId, tenantId);
  assert.equal(touchpoint.contactId, 'contact-1');
  assert.equal(touchpoint.channel, 'whatsapp');
  assert.equal(touchpoint.campaignId, tenantId);
});

test('attributeOrder first_touch model credits earliest touchpoint', async () => {
  const seededPool = {
    async connect() {
      return {
        async query(text, values = []) {
          if (text.trimStart().startsWith('INSERT')) {
            return { rows: [] };
          }
          if (text.trimStart().startsWith('SELECT')) {
            return {
              rows: [
                { id: 't1', channel: 'email', event_type: 'click', campaign_id: null, metadata: {}, occurred_at: '2026-08-01T10:00:00Z' },
                { id: 't2', channel: 'whatsapp', event_type: 'campaign_sent', campaign_id: tenantId, metadata: {}, occurred_at: '2026-08-05T10:00:00Z' },
              ],
            };
          }
          return { rows: [] };
        },
        release() {},
      };
    },
  };

  const engine = createAttributionEngine({
    postgresPool: seededPool,
    jsonStorage: null,
    logger: { info: () => {}, warn: () => {}, error: () => {} },
  });

  const attribution = await engine.attributeOrder({
    tenantId,
    contactId: 'c1',
    orderId: 'ORD-1',
    orderValue: 100,
    model: 'first_touch',
    orderDate: '2026-08-10T10:00:00Z',
  });

  assert.equal(attribution.attribution.length, 1);
  assert.equal(attribution.attribution[0].channel, 'email');
  assert.equal(attribution.attribution[0].credit, 100);
  assert.equal(attribution.model, 'first_touch');
});

test('attributeOrder last_touch model credits latest touchpoint', async () => {
  const seededPool = {
    async connect() {
      return {
        async query(text, values = []) {
          if (text.trimStart().startsWith('INSERT')) {
            return { rows: [] };
          }
          if (text.trimStart().startsWith('SELECT')) {
            return {
              rows: [
                { id: 't1', channel: 'email', event_type: 'click', campaign_id: null, metadata: {}, occurred_at: '2026-08-01T10:00:00Z' },
                { id: 't2', channel: 'whatsapp', event_type: 'campaign_sent', campaign_id: tenantId, metadata: {}, occurred_at: '2026-08-05T10:00:00Z' },
              ],
            };
          }
          return { rows: [] };
        },
        release() {},
      };
    },
  };

  const engine = createAttributionEngine({
    postgresPool: seededPool,
    jsonStorage: null,
    logger: { info: () => {}, warn: () => {}, error: () => {} },
  });

  const attribution = await engine.attributeOrder({
    tenantId,
    contactId: 'c2',
    orderId: 'ORD-2',
    orderValue: 100,
    model: 'last_touch',
    orderDate: '2026-08-10T10:00:00Z',
  });

  assert.equal(attribution.attribution.length, 1);
  assert.equal(attribution.attribution[0].channel, 'whatsapp');
  assert.equal(attribution.attribution[0].credit, 100);
});

test('attributeOrder multi_touch_linear splits credit evenly', async () => {
  const seededPool = {
    async connect() {
      return {
        async query(text, values = []) {
          if (text.trimStart().startsWith('INSERT')) {
            return { rows: [] };
          }
          if (text.trimStart().startsWith('SELECT')) {
            return {
              rows: [
                { id: 't1', channel: 'email', event_type: 'click', campaign_id: null, metadata: {}, occurred_at: '2026-08-01T10:00:00Z' },
                { id: 't2', channel: 'whatsapp', event_type: 'campaign_sent', campaign_id: tenantId, metadata: {}, occurred_at: '2026-08-05T10:00:00Z' },
              ],
            };
          }
          return { rows: [] };
        },
        release() {},
      };
    },
  };

  const engine = createAttributionEngine({
    postgresPool: seededPool,
    jsonStorage: null,
    logger: { info: () => {}, warn: () => {}, error: () => {} },
  });

  const attribution = await engine.attributeOrder({
    tenantId,
    contactId: 'c3',
    orderId: 'ORD-3',
    orderValue: 100,
    model: 'multi_touch_linear',
    orderDate: '2026-08-10T10:00:00Z',
  });

  assert.equal(attribution.attribution.length, 2);
  assert.equal(attribution.attribution[0].credit, 50);
  assert.equal(attribution.attribution[1].credit, 50);
  assert.equal(attribution.touchpointCount, 2);
});

test('attributeOrder rejects unsupported model', async () => {
  const engine = createEngine();
  let threw = false;
  try {
    await engine.attributeOrder({ tenantId, contactId: 'c1', orderId: 'ORD-1', model: 'unknown' });
  } catch (e) {
    threw = true;
    assert.match(e.message, /Unsupported attribution model/i);
  }
  assert.ok(threw, 'expected attributeOrder to reject unsupported model');
});

test('getReport filters by contactId and channel', async () => {
  const seededPool = {
    async connect() {
      return {
        async query(text, values = []) {
          if (text.trimStart().startsWith('SELECT') && text.includes('order_attributions')) {
            const trimmed = text.trimStart();
            const hasChannelFilter = trimmed.includes('attribution @>');
            const hasContactFilter = trimmed.includes('contact_id =');
            const baseRows = [
              {
                id: 'a1', contact_id: 'c1', order_id: 'ORD-1', order_value: 100, currency: 'USD',
                platform: 'zok', order_date: '2026-08-10T10:00:00Z', model: 'last_touch',
                touchpoint_count: 1, attribution: [{ channel: 'whatsapp', credit: 100 }],
                created_at: '2026-08-10T10:00:00Z',
              },
              {
                id: 'a2', contact_id: 'c2', order_id: 'ORD-2', order_value: 200, currency: 'USD',
                platform: 'zok', order_date: '2026-08-11T10:00:00Z', model: 'last_touch',
                touchpoint_count: 1, attribution: [{ channel: 'email', credit: 200 }],
                created_at: '2026-08-11T10:00:00Z',
              },
            ];
            return {
              rows: baseRows.filter((row) => {
                if (hasChannelFilter && !row.attribution.some((a) => a.channel === 'whatsapp')) return false;
                if (hasContactFilter && row.contact_id !== 'c1') return false;
                return true;
              }),
            };
          }
          return { rows: [] };
        },
        release() {},
      };
    },
  };

  const engine = createAttributionEngine({
    postgresPool: seededPool,
    jsonStorage: null,
    logger: { info: () => {}, warn: () => {}, error: () => {} },
  });

  const report = await engine.getReport({ tenantId, channel: 'whatsapp', limit: 10 });
  assert.equal(report.rows.length, 1);
  assert.equal(report.rows[0].contact_id, 'c1');
  assert.equal(report.summary.totalValue, 100);
});
