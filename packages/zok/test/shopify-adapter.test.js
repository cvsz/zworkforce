import test from 'node:test';
import assert from 'node:assert/strict';
import { createShopifyAdapter } from '../server/commerce/adapters/shopify-adapter.js';

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
  return createShopifyAdapter({
    apiKey: 'key',
    apiSecret: 'secret',
    shopDomain: 'shop.myshopify.com',
    accessToken: 'token',
    postgresPool: mockPool,
    jsonStorage: null,
    logger: { info: () => {}, warn: () => {}, error: () => {} },
  });
}

test('createShopifyAdapter reports connection status', () => {
  const adapter = createAdapter();
  const status = adapter.getConnectionStatus();
  assert.deepEqual(status, { configured: true, platform: 'shopify', connected: true });
});

test('persistOrder normalises and stores order', async () => {
  const adapter = createAdapter();
  const order = await adapter.persistOrder(tenantId, {
    id: 'SHOP-123',
    status: 'fulfilled',
    total_price: 149.99,
    currency: 'USD',
    customer: { id: 'CUST-1', email: 'user@example.com' },
    line_items: [
      { product_id: 'P1', variant_id: 'V1', title: 'T-Shirt', quantity: 2, price: 74.99 },
    ],
    created_at: '2026-08-01T00:00:00Z',
  });

  assert.ok(order.id);
  assert.equal(order.externalOrderId, 'SHOP-123');
  assert.equal(order.status, 'fulfilled');
  assert.equal(order.total, 149.99);
  assert.equal(order.items.length, 1);
  assert.equal(order.items[0].productId, 'P1');
});

test('persistProduct normalises and stores product', async () => {
  const adapter = createAdapter();
  const product = await adapter.persistProduct(tenantId, {
    id: 'PROD-1',
    title: 'Cool Shirt',
    status: 'active',
    variants: [
      { id: 'V1', title: 'M', price: 29.99, inventory: 100, sku: 'SKU-1' },
    ],
  });

  assert.ok(product.id);
  assert.equal(product.title, 'Cool Shirt');
  assert.equal(product.variants.length, 1);
  assert.equal(product.variants[0].inventory, 100);
});

test('persistCustomer normalises and stores customer', async () => {
  const adapter = createAdapter();
  const customer = await adapter.persistCustomer(tenantId, {
    id: 'CUST-1',
    email: 'user@example.com',
    first_name: 'Jane',
    last_name: 'Doe',
    phone: '+1234567890',
    tags: ['vip', 'shopify-buyer'],
    accepts_marketing: true,
  });

  assert.ok(customer.id);
  assert.equal(customer.email, 'user@example.com');
  assert.equal(customer.firstName, 'Jane');
  assert.deepEqual(customer.tags, ['vip', 'shopify-buyer']);
});

test('syncInventory updates product variant stock', async () => {
  const adapter = createAdapter();
  const result = await adapter.syncInventory(tenantId, 'PROD-1', 'V1', 50);
  assert.equal(result.quantity, 50);
});

test('handleOrderWebhook creates order and customer', async () => {
  const adapter = createAdapter();
  const payload = {
    id: 'SHOP-456',
    status: 'pending',
    total_price: 50,
    currency: 'USD',
    customer: { id: 'CUST-2', email: 'new@example.com' },
    line_items: [],
    created_at: '2026-08-02T00:00:00Z',
  };

  const result = await adapter.handleOrderWebhook(tenantId, payload);
  assert.equal(result.action, 'created_or_updated');
  assert.equal(result.order.externalOrderId, 'SHOP-456');
});

test('handleInventoryWebhook updates inventory', async () => {
  const adapter = createAdapter();
  const result = await adapter.handleInventoryWebhook(tenantId, {
    product_id: 'PROD-1',
    variant_id: 'V1',
    inventory_quantity: 75,
  });

  assert.equal(result.quantity, 75);
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

test('persistOrder rejects invalid tenantId', async () => {
  const adapter = createAdapter();
  await assert.rejects(() => adapter.persistOrder('bad', { id: '1' }), /Invalid tenantId/);
});
