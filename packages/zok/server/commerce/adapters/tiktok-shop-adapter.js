import { randomUUID } from 'node:crypto';

const UUID_PATTERN = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;
const SHOP_STATUSES = new Set(['active', 'suspended', 'pending', 'closed']);
const ORDER_STATUSES = new Set(['pending', 'confirmed', 'shipped', 'delivered', 'cancelled', 'refunded']);

function clampNumber(value, fallback, minimum, maximum) {
  const parsed = Number(value);
  return Number.isFinite(parsed) && parsed >= minimum && parsed <= maximum ? parsed : fallback;
}

function validateShopStatus(value) {
  if (typeof value !== 'string') return null;
  const status = value.trim().toLowerCase();
  return SHOP_STATUSES.has(status) ? status : null;
}

function validateOrderStatus(value) {
  if (typeof value !== 'string') return null;
  const status = value.trim().toLowerCase();
  return ORDER_STATUSES.has(status) ? status : null;
}

function normaliseProduct(product) {
  if (!product || typeof product !== 'object') return null;
  return {
    id: typeof product.id === 'string' ? product.id.trim() : String(product.id || randomUUID()),
    title: typeof product.title === 'string' ? product.title.trim() : 'Untitled Product',
    description: typeof product.description === 'string' ? product.description.trim() : '',
    price: clampNumber(product.price, 0, 0, Number.MAX_SAFE_INTEGER),
    stock: clampNumber(product.stock, 0, 0, Number.MAX_SAFE_INTEGER),
    status: typeof product.status === 'string' ? product.status.trim() : 'draft',
    platform: 'tiktok',
  };
}

function normaliseOrder(order) {
  if (!order || typeof order !== 'object') return null;
  return {
    externalOrderId: typeof order.id === 'string' ? order.id.trim() : String(order.id || randomUUID()),
    platform: 'tiktok',
    status: validateOrderStatus(order.status) || 'pending',
    total: clampNumber(order.total_amount || order.total, 0, 0, Number.MAX_SAFE_INTEGER),
    currency: typeof order.currency === 'string' ? order.currency.trim() : 'USD',
    customerId: typeof order.customer_id === 'string' ? order.customer_id.trim() : null,
    orderDate: typeof order.create_time === 'string' ? order.create_time : new Date().toISOString(),
    items: Array.isArray(order.items) ? order.items.map((item) => ({
      productId: typeof item.product_id === 'string' ? item.product_id.trim() : null,
      sku: typeof item.sku_id === 'string' ? item.sku_id.trim() : null,
      title: typeof item.product_name === 'string' ? item.product_name.trim() : 'Item',
      quantity: clampNumber(item.quantity, 0, 0, Number.MAX_SAFE_INTEGER),
      price: clampNumber(item.sale_price || item.price, 0, 0, Number.MAX_SAFE_INTEGER),
    })) : [],
    fulfillmentStatus: typeof order.fulfillment_status === 'string' ? order.fulfillment_status.trim() : 'unfulfilled',
    shippingAddress: typeof order.address === 'object' ? {
      name: typeof order.address.name === 'string' ? order.address.name.trim() : null,
      phone: typeof order.address.phone === 'string' ? order.address.phone.trim() : null,
      address1: typeof order.address.detail_address === 'string' ? order.address.detail_address.trim() : null,
      city: typeof order.address.city === 'string' ? order.address.city.trim() : null,
      country: typeof order.address.country === 'string' ? order.address.country.trim() : null,
      zip: typeof order.address.zip_code === 'string' ? order.address.zip_code.trim() : null,
    } : null,
    metadata: typeof order.metadata === 'object' && !Array.isArray(order.metadata) ? order.metadata : {},
  };
}

export function createTikTokShopAdapter({
  appKey = null,
  appSecret = null,
  shopId = null,
  accessToken = null,
  postgresPool = null,
  jsonStorage = null,
  logger = null,
} = {}) {
  const log = logger || { info: () => {}, warn: () => {}, error: () => {} };
  const configured = Boolean(appKey && appSecret && shopId && accessToken);

  async function withPgClient(query) {
    if (!postgresPool) throw new Error('PostgreSQL pool is required');
    const client = await postgresPool.connect();
    try {
      return await query(client);
    } finally {
      client.release();
    }
  }

  async function readJsonDb() {
    if (!jsonStorage) return null;
    try {
      return await jsonStorage.read();
    } catch {
      return null;
    }
  }

  async function updateJsonDb(mutator) {
    if (!jsonStorage) return null;
    try {
      return await jsonStorage.update(mutator);
    } catch {
      return null;
    }
  }

  async function persistOrder(tenantId, order) {
    if (!tenantId || !UUID_PATTERN.test(tenantId)) return null;
    const normalised = normaliseOrder(order);
    if (!normalised) return null;

    const record = {
      id: randomUUID(),
      tenantId,
      ...normalised,
      deletedAt: null,
      createdAt: new Date().toISOString(),
      updatedAt: new Date().toISOString(),
    };

    if (postgresPool) {
      await withPgClient(async (client) => {
        await client.query(
          `INSERT INTO commerce_orders (id, tenant_id, external_order_id, platform, status, total, currency, customer_id, order_date, items, shipping_address, metadata, deleted_at, created_at, updated_at)
           VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10::jsonb, $11::jsonb, $12::jsonb, $13, $14, $15)
           ON CONFLICT (tenant_id, platform, external_order_id) DO UPDATE SET
             status = EXCLUDED.status,
             total = EXCLUDED.total,
             fulfillment_status = $5,
             items = EXCLUDED.items,
             updated_at = EXCLUDED.updated_at`,
          [
            record.id,
            record.tenantId,
            record.externalOrderId,
            record.platform,
            record.status,
            record.total,
            record.currency,
            record.customerId,
            record.orderDate,
            JSON.stringify(record.items),
            JSON.stringify(record.shippingAddress),
            JSON.stringify(record.metadata),
            record.deletedAt,
            record.createdAt,
            record.updatedAt,
          ]
        );
      });
    }

    const db = await readJsonDb();
    if (db) {
      await updateJsonDb((current) => {
        if (!current.commerceOrders) current.commerceOrders = [];
        const existingIndex = current.commerceOrders.findIndex(
          (o) => o.tenantId === tenantId && o.platform === 'tiktok' && o.externalOrderId === record.externalOrderId
        );
        if (existingIndex >= 0) {
          current.commerceOrders[existingIndex] = { ...current.commerceOrders[existingIndex], ...record };
        } else {
          current.commerceOrders.push(record);
        }
        return current;
      });
    }

    log.info('tiktok order synced', { orderId: record.externalOrderId, tenantId });
    return record;
  }

  async function persistProduct(tenantId, product) {
    if (!tenantId || !UUID_PATTERN.test(tenantId)) return null;
    const normalised = normaliseProduct(product);
    if (!normalised) return null;

    const record = {
      id: randomUUID(),
      tenantId,
      ...normalised,
      deletedAt: null,
      createdAt: new Date().toISOString(),
      updatedAt: new Date().toISOString(),
    };

    if (postgresPool) {
      await withPgClient(async (client) => {
        await client.query(
          `INSERT INTO commerce_products (id, tenant_id, external_product_id, platform, title, description, variants, status, deleted_at, created_at, updated_at)
           VALUES ($1, $2, $3, $4, $5, $6, $7::jsonb, $8, $9, $10, $11)
           ON CONFLICT (tenant_id, platform, external_product_id) DO UPDATE SET
             title = EXCLUDED.title,
             description = EXCLUDED.description,
             variants = jsonb_set(variants, '{stock}', to_jsonb($7::jsonb->>'stock')) ,
             status = EXCLUDED.status,
             updated_at = EXCLUDED.updated_at`,
          [
            record.id,
            record.tenantId,
            record.id,
            record.platform,
            record.title,
            record.description,
            JSON.stringify([{ id: record.id, title: 'Default', price: record.price, inventory: record.stock, sku: null }]),
            record.status,
            record.deletedAt,
            record.createdAt,
            record.updatedAt,
          ]
        );
      });
    }

    const db = await readJsonDb();
    if (db) {
      await updateJsonDb((current) => {
        if (!current.commerceProducts) current.commerceProducts = [];
        const existingIndex = current.commerceProducts.findIndex(
          (p) => p.tenantId === tenantId && p.platform === 'tiktok' && p.id === record.id
        );
        if (existingIndex >= 0) {
          current.commerceProducts[existingIndex] = { ...current.commerceProducts[existingIndex], ...record };
        } else {
          current.commerceProducts.push(record);
        }
        return current;
      });
    }

    log.info('tiktok product synced', { productId: record.id, tenantId });
    return record;
  }

  async function handleShopStatusChange(tenantId, payload) {
    if (!tenantId || !UUID_PATTERN.test(tenantId)) {
      throw new TypeError('Invalid tenantId');
    }
    const status = validateShopStatus(payload.status) || 'active';
    const updatedAt = new Date().toISOString();

    if (postgresPool) {
      await withPgClient(async (client) => {
        await client.query(
          `INSERT INTO integration_status_logs (tenant_id, provider, external_id, status, metadata, created_at)
           VALUES ($1, $2, $3, $4, $5::jsonb, $6)`,
          [
            tenantId,
            'tiktok',
            typeof payload.shop_id === 'string' ? payload.shop_id.trim() : null,
            status,
            JSON.stringify(payload),
            updatedAt,
          ]
        );
      });
    }

    const db = await readJsonDb();
    if (db) {
      await updateJsonDb((current) => {
        if (!current.integrationStatusLogs) current.integrationStatusLogs = [];
        current.integrationStatusLogs.push({
          id: randomUUID(),
          tenantId,
          provider: 'tiktok',
          externalId: typeof payload.shop_id === 'string' ? payload.shop_id.trim() : null,
          status,
          metadata: payload,
          createdAt: updatedAt,
        });
        return current;
      });
    }

    log.info('tiktok shop status changed', { tenantId, status });
    return { shopId: payload.shop_id, status, updatedAt };
  }

  async function handleFulfillmentWebhook(tenantId, payload) {
    if (!tenantId || !UUID_PATTERN.test(tenantId)) {
      throw new TypeError('Invalid tenantId');
    }
    const orderId = typeof payload.order_id === 'string' ? payload.order_id.trim() : null;
    const fulfillmentStatus = typeof payload.fulfillment_status === 'string' ? payload.fulfillment_status.trim() : null;
    if (!orderId || !fulfillmentStatus) {
      throw new TypeError('Invalid TikTok fulfillment webhook payload');
    }

    const updatedAt = new Date().toISOString();

    if (postgresPool) {
      await withPgClient(async (client) => {
        await client.query(
          `UPDATE commerce_orders
           SET status = $1, updated_at = $2
           WHERE tenant_id = $3 AND platform = 'tiktok' AND external_order_id = $4`,
          [fulfillmentStatus, updatedAt, tenantId, orderId]
        );
      });
    }

    const db = await readJsonDb();
    if (db && db.commerceOrders) {
      await updateJsonDb((current) => {
        const order = current.commerceOrders.find(
          (o) => o.tenantId === tenantId && o.platform === 'tiktok' && o.externalOrderId === orderId
        );
        if (order) {
          order.status = fulfillmentStatus;
          order.updatedAt = updatedAt;
        }
        return current;
      });
    }

    log.info('tiktok fulfillment webhook handled', { orderId, fulfillmentStatus, tenantId });
    return { orderId, fulfillmentStatus, updatedAt };
  }

  async function syncCatalog(tenantId, products) {
    if (!Array.isArray(products)) {
      throw new TypeError('products must be an array');
    }
    const results = [];
    for (const product of products) {
      const record = await persistProduct(tenantId, product);
      if (record) results.push(record);
    }
    log.info('tiktok catalog synced', { tenantId, count: results.length });
    return results;
  }

  function getConnectionStatus() {
    return {
      configured,
      platform: 'tiktok',
      connected: configured,
    };
  }

  return Object.freeze({
    syncCatalog,
    handleShopStatusChange,
    handleFulfillmentWebhook,
    getConnectionStatus,
    persistOrder,
    persistProduct,
  });
}
