import test from 'node:test';
import assert from 'node:assert/strict';
import { createTikTokShopAdapter } from '../server/commerce/adapters/tiktok-shop-adapter.js';

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

function createAdapter() {
  return createTikTokShopAdapter({
    appKey: 'key',
    appSecret: 'secret',
    shopId: 'shop-1',
    accessToken: 'token',
    postgresPool: mockPool,
    jsonStorage: null,
    logger: { info: () => {}, warn: () => {}, error: () => {} },
  });
}

test('createTikTokShopAdapter reports connection status', () => {
  const adapter = createAdapter();
  const status = adapter.getConnectionStatus();
  assert.deepEqual(status, { configured: true, platform: 'tiktok', connected: true });
});

test('persistOrder normalises and stores order', async () => {
  const adapter = createAdapter();
  const order = await adapter.persistOrder(tenantId, {
    id: 'TIK-123',
    status: 'confirmed',
    total_amount: 99.5,
    currency: 'USD',
    customer_id: 'CUST-1',
    items: [
      { product_id: 'P1', sku_id: 'SKU-1', product_name: 'Sticker', quantity: 3, price: 33.17 },
    ],
    create_time: '2026-08-01T00:00:00Z',
  });

  assert.ok(order.id);
  assert.equal(order.externalOrderId, 'TIK-123');
  assert.equal(order.status, 'confirmed');
  assert.equal(order.total, 99.5);
  assert.equal(order.items[0].title, 'Sticker');
});

test('persistProduct normalises and stores product', async () => {
  const adapter = createAdapter();
  const product = await adapter.persistProduct(tenantId, {
    id: 'PROD-1',
    title: 'TikTok Tee',
    price: 25,
    stock: 200,
    status: 'active',
  });

  assert.ok(product.id);
  assert.equal(product.title, 'TikTok Tee');
  assert.equal(product.stock, 200);
});

test('handleShopStatusChange logs status change', async () => {
  const adapter = createAdapter();
  const result = await adapter.handleShopStatusChange(tenantId, {
    shop_id: 'shop-1',
    status: 'active',
    timestamp: '2026-08-01T00:00:00Z',
  });

  assert.equal(result.shopId, 'shop-1');
  assert.equal(result.status, 'active');
});

test('handleFulfillmentWebhook updates order status', async () => {
  const adapter = createAdapter();
  const result = await adapter.handleFulfillmentWebhook(tenantId, {
    order_id: 'TIK-123',
    fulfillment_status: 'shipped',
  });

  assert.equal(result.orderId, 'TIK-123');
  assert.equal(result.fulfillmentStatus, 'shipped');
});

test('syncCatalog processes multiple products', async () => {
  const adapter = createAdapter();
  const products = [
    { id: 'P1', title: 'Item 1' },
    { id: 'P2', title: 'Item 2' },
  ];

  const results = await adapter.syncCatalog(tenantId, products);
  assert.equal(results.length, 2);
});

test('handleShopStatusChange rejects invalid tenantId', async () => {
  const adapter = createAdapter();
  await assert.rejects(
    () => adapter.handleShopStatusChange('bad', { shop_id: '1', status: 'active' }),
    /Invalid tenantId/i
  );
});

test('handleFulfillmentWebhook rejects invalid payload', async () => {
  const adapter = createAdapter();
  await assert.rejects(
    () => adapter.handleFulfillmentWebhook(tenantId, { order_id: 'TIK-1' }),
    /Invalid TikTok fulfillment webhook payload/i
  );
});
