import test from 'node:test';
import assert from 'node:assert/strict';
import { createReconciliationEngine } from '../server/commerce/reconciliation.js';

const tenantId = 'bbbbbbbb-2222-4222-8222-bbbbbbbbbbbb';

function createMockPool(initialOrders = []) {
  const orders = [...initialOrders];
  const reconciliationRecords = [];

  return {
    async connect() {
      return {
        async query(text, values = []) {
          const trimmed = text.trimStart();
          if (trimmed.startsWith('SELECT') && trimmed.includes('commerce_orders')) {
            return { rows: orders };
          }
          if (trimmed.startsWith('SELECT') && trimmed.includes('reconciliation_records')) {
            const hasPlatformFilter = trimmed.includes("platform_order->>'platform'");
            return {
              rows: reconciliationRecords.filter((r) => {
                if (hasPlatformFilter) {
                  const platformIdx = values.indexOf('shopify');
                  if (platformIdx >= 0 && r.platformOrder?.platform !== 'shopify') return false;
                }
                return true;
              }),
            };
          }
          if (trimmed.startsWith('INSERT') && trimmed.includes('reconciliation_records')) {
            const row = JSON.parse(values[6] || '{}');
            reconciliationRecords.push({
              id: values[0],
              tenantId: values[1],
              platformOrder: values[2] ? JSON.parse(values[2]) : null,
              existingOrder: values[3] ? JSON.parse(values[3]) : null,
              status: values[4],
              mode: values[5],
              reconciliationId: values[6],
              differences: values[7] ? JSON.parse(values[7]) : {},
              resolvedAt: values[8],
              createdAt: values[9],
              updatedAt: values[10],
            });
            return { rows: [] };
          }
          if (trimmed.startsWith('UPDATE') && trimmed.includes('reconciliation_records')) {
            const record = reconciliationRecords.find((r) => r.id === values[3]);
            if (record) {
              record.status = values[0];
              record.resolvedAt = values[1];
              record.updatedAt = values[2];
            }
            return { rows: [] };
          }
          return { rows: [] };
        },
        release() {},
      };
    },
  };
}

function createEngine(initialOrders = []) {
  return createReconciliationEngine({
    postgresPool: createMockPool(initialOrders),
    jsonStorage: null,
    logger: { info: () => {}, warn: () => {}, error: () => {} },
  });
}

test('createReconciliationEngine fails closed without pool', () => {
  assert.throws(() => createReconciliationEngine({}), /PostgreSQL pool is required/i);
});

test('reconcileOrders returns missing for new platform orders', async () => {
  const engine = createEngine();
  const results = await engine.reconcileOrders({
    tenantId,
    platformOrders: [
      {
        externalOrderId: 'SHOP-1',
        platform: 'shopify',
        status: 'delivered',
        total: 100,
        currency: 'USD',
        customerId: 'cust-1',
      },
    ],
    mode: 'automatic',
  });

  assert.equal(results.length, 1);
  assert.equal(results[0].status, 'missing');
  assert.equal(results[0].platformOrder.externalOrderId, 'SHOP-1');
});

test('reconcileOrders matches identical pre-seeded orders', async () => {
  const seedOrders = [
    {
      id: 'seed-1',
      tenantId,
      externalOrderId: 'SHOP-1',
      platform: 'shopify',
      status: 'delivered',
      total: 100,
      currency: 'USD',
      customerId: 'cust-1',
      orderDate: '2026-08-01T00:00:00Z',
      items: [],
      metadata: {},
      deletedAt: null,
    },
  ];

  const engine = createEngine(seedOrders);
  const results = await engine.reconcileOrders({
    tenantId,
    platformOrders: [
      {
        externalOrderId: 'SHOP-1',
        platform: 'shopify',
        status: 'delivered',
        total: 100,
        currency: 'USD',
        customerId: 'cust-1',
      },
    ],
    mode: 'automatic',
  });

  assert.equal(results.length, 1);
  assert.equal(results[0].status, 'matched');
});

test('reconcileOrders detects mismatched orders when pre-seeded', async () => {
  const seedOrders = [
    {
      id: 'seed-1',
      tenantId,
      externalOrderId: 'SHOP-1',
      platform: 'shopify',
      status: 'delivered',
      total: 100,
      currency: 'USD',
      customerId: 'cust-1',
      orderDate: '2026-08-01T00:00:00Z',
      items: [],
      metadata: {},
      deletedAt: null,
    },
  ];

  const engine = createEngine(seedOrders);
  const results = await engine.reconcileOrders({
    tenantId,
    platformOrders: [
      {
        externalOrderId: 'SHOP-1',
        platform: 'shopify',
        status: 'pending',
        total: 200,
        currency: 'USD',
        customerId: 'cust-1',
      },
    ],
    mode: 'automatic',
  });

  assert.equal(results.length, 1);
  assert.equal(results[0].status, 'mismatched');
  assert.deepEqual(results[0].differences, { status: true, total: 100, currency: false });
});

test('reconcileOrders detects platform orders missing from zok', async () => {
  const seedOrders = [
    {
      id: 'seed-1',
      tenantId,
      externalOrderId: 'SHOP-1',
      platform: 'shopify',
      status: 'delivered',
      total: 100,
      currency: 'USD',
      customerId: 'cust-1',
      orderDate: '2026-08-01T00:00:00Z',
      items: [],
      metadata: {},
      deletedAt: null,
    },
  ];

  const engine = createEngine(seedOrders);
  const results = await engine.reconcileOrders({
    tenantId,
    platformOrders: [
      {
        externalOrderId: 'SHOP-1',
        platform: 'shopify',
        status: 'delivered',
        total: 100,
        currency: 'USD',
        customerId: 'cust-1',
      },
      {
        externalOrderId: 'TIK-1',
        platform: 'tiktok',
        status: 'pending',
        total: 200,
        currency: 'USD',
        customerId: 'cust-2',
      },
    ],
    mode: 'automatic',
  });

  const missingInZok = results.filter((r) => r.status === 'missing' && r.differences?.missingInZok);
  assert.equal(missingInZok.length, 1);
  assert.equal(missingInZok[0].platformOrder.externalOrderId, 'TIK-1');
});

test('resolveReconciliation marks record resolved', async () => {
  const engine = createEngine();
  const results = await engine.reconcileOrders({
    tenantId,
    platformOrders: [
      { externalOrderId: 'SHOP-1', platform: 'shopify', status: 'delivered', total: 100, currency: 'USD' },
    ],
    mode: 'manual',
  });

  const recordId = results[0].id;
  const resolved = await engine.resolveReconciliation(tenantId, recordId, 'resolved');
  assert.equal(resolved.status, 'resolved');
  assert.ok(resolved.resolvedAt);
});

test('resolveReconciliation rejects invalid tenantId', async () => {
  const engine = createEngine();
  let threw = false;
  try {
    await engine.resolveReconciliation('bad', 'some-id', 'resolved');
  } catch (e) {
    threw = true;
    assert.match(e.message, /tenantId is required/i);
  }
  assert.ok(threw, 'expected resolveReconciliation to reject invalid tenantId');
});

test('getReconciliationReport filters by platform', async () => {
  const initialOrders = [
    {
      id: 'seed-1',
      tenantId,
      externalOrderId: 'SHOP-1',
      platform: 'shopify',
      status: 'delivered',
      total: 100,
      currency: 'USD',
      customerId: 'cust-1',
      orderDate: '2026-08-01T00:00:00Z',
      items: [],
      metadata: {},
      deletedAt: null,
    },
    {
      id: 'seed-2',
      tenantId,
      externalOrderId: 'TIK-1',
      platform: 'tiktok',
      status: 'pending',
      total: 200,
      currency: 'USD',
      customerId: 'cust-2',
      orderDate: '2026-08-01T00:00:00Z',
      items: [],
      metadata: {},
      deletedAt: null,
    },
  ];

  const engine = createEngine(initialOrders);
  await engine.reconcileOrders({
    tenantId,
    platformOrders: [
      { externalOrderId: 'SHOP-1', platform: 'shopify', status: 'delivered', total: 100, currency: 'USD' },
      { externalOrderId: 'TIK-1', platform: 'tiktok', status: 'pending', total: 200, currency: 'USD' },
    ],
  });

  const report = await engine.getReconciliationReport({ tenantId, platform: 'shopify', limit: 10 });
  assert.equal(report.records.length, 1);
  assert.equal(report.records[0].platformOrder.platform, 'shopify');
  assert.equal(report.summary.total, 1);
});
