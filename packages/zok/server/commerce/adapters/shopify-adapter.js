import { randomUUID } from 'node:crypto';

const UUID_PATTERN = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;

function clampNumber(value, fallback, minimum, maximum) {
  const parsed = Number(value);
  return Number.isFinite(parsed) && parsed >= minimum && parsed <= maximum ? parsed : fallback;
}

function normaliseProduct(product) {
  if (!product || typeof product !== 'object') return null;
  return {
    id: typeof product.id === 'string' ? product.id.trim() : String(product.id || randomUUID()),
    title: typeof product.title === 'string' ? product.title.trim() : 'Untitled Product',
    description: typeof product.description === 'string' ? product.description.trim() : '',
    variants: Array.isArray(product.variants) ? product.variants.map((v) => ({
      id: typeof v?.id === 'string' ? v.id.trim() : String(v?.id || randomUUID()),
      title: typeof v?.title === 'string' ? v.title.trim() : 'Default',
      price: clampNumber(v?.price, 0, 0, Number.MAX_SAFE_INTEGER),
      inventory: clampNumber(v?.inventory, 0, 0, Number.MAX_SAFE_INTEGER),
      sku: typeof v?.sku === 'string' ? v.sku.trim() : null,
    })) : [],
    status: typeof product.status === 'string' ? product.status.trim() : 'draft',
    platform: 'shopify',
  };
}

function normaliseOrder(order) {
  if (!order || typeof order !== 'object') return null;
  return {
    externalOrderId: typeof order.id === 'string' ? order.id.trim() : String(order.id || randomUUID()),
    platform: 'shopify',
    status: typeof order.status === 'string' ? order.status.trim() : 'pending',
    total: clampNumber(order.total_price || order.total, 0, 0, Number.MAX_SAFE_INTEGER),
    currency: typeof order.currency === 'string' ? order.currency.trim() : 'USD',
    customerId: typeof order.customer?.id === 'string' ? order.customer.id.trim() : (typeof order.customer_id === 'string' ? order.customer_id.trim() : null),
    orderDate: typeof order.created_at === 'string' ? order.created_at : new Date().toISOString(),
    items: Array.isArray(order.line_items) ? order.line_items.map((item) => ({
      productId: typeof item.product_id === 'string' ? item.product_id.trim() : null,
      variantId: typeof item.variant_id === 'string' ? item.variant_id.trim() : null,
      title: typeof item.title === 'string' ? item.title.trim() : 'Item',
      quantity: clampNumber(item.quantity, 0, 0, Number.MAX_SAFE_INTEGER),
      price: clampNumber(item.price, 0, 0, Number.MAX_SAFE_INTEGER),
    })) : [],
    shippingAddress: typeof order.shipping_address === 'object' ? {
      name: `${order.shipping_address.first_name || ''} ${order.shipping_address.last_name || ''}`.trim() || null,
      address1: typeof order.shipping_address.address1 === 'string' ? order.shipping_address.address1.trim() : null,
      city: typeof order.shipping_address.city === 'string' ? order.shipping_address.city.trim() : null,
      country: typeof order.shipping_address.country === 'string' ? order.shipping_address.country.trim() : null,
      zip: typeof order.shipping_address.zip === 'string' ? order.shipping_address.zip.trim() : null,
    } : null,
    metadata: typeof order.metadata === 'object' && !Array.isArray(order.metadata) ? order.metadata : {},
  };
}

function normaliseCustomer(customer) {
  if (!customer || typeof customer !== 'object') return null;
  return {
    externalCustomerId: typeof customer.id === 'string' ? customer.id.trim() : String(customer.id || randomUUID()),
    platform: 'shopify',
    email: typeof customer.email === 'string' ? customer.email.trim() : null,
    firstName: typeof customer.first_name === 'string' ? customer.first_name.trim() : null,
    lastName: typeof customer.last_name === 'string' ? customer.last_name.trim() : null,
    phone: typeof customer.phone === 'string' ? customer.phone.trim() : null,
    tags: Array.isArray(customer.tags) ? customer.tags.filter((t) => typeof t === 'string') : [],
    acceptsMarketing: Boolean(customer.accepts_marketing),
    createdAt: typeof customer.created_at === 'string' ? customer.created_at : new Date().toISOString(),
    metadata: typeof customer.metadata === 'object' && !Array.isArray(customer.metadata) ? customer.metadata : {},
  };
}

export function createShopifyAdapter({
  apiKey = null,
  apiSecret = null,
  shopDomain = null,
  accessToken = null,
  postgresPool = null,
  jsonStorage = null,
  logger = null,
} = {}) {
  const log = logger || { info: () => {}, warn: () => {}, error: () => {} };
  const configured = Boolean(apiKey && apiSecret && shopDomain && accessToken);

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
    if (!tenantId || !UUID_PATTERN.test(tenantId)) {
      throw new TypeError('Invalid tenantId');
    }
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
          (o) => o.tenantId === tenantId && o.platform === 'shopify' && o.externalOrderId === record.externalOrderId
        );
        if (existingIndex >= 0) {
          current.commerceOrders[existingIndex] = { ...current.commerceOrders[existingIndex], ...record };
        } else {
          current.commerceOrders.push(record);
        }
        return current;
      });
    }

    log.info('shopify order synced', { orderId: record.externalOrderId, tenantId });
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
             variants = EXCLUDED.variants,
             status = EXCLUDED.status,
             updated_at = EXCLUDED.updated_at`,
          [
            record.id,
            record.tenantId,
            record.id,
            record.platform,
            record.title,
            record.description,
            JSON.stringify(record.variants),
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
          (p) => p.tenantId === tenantId && p.platform === 'shopify' && p.id === record.id
        );
        if (existingIndex >= 0) {
          current.commerceProducts[existingIndex] = { ...current.commerceProducts[existingIndex], ...record };
        } else {
          current.commerceProducts.push(record);
        }
        return current;
      });
    }

    log.info('shopify product synced', { productId: record.id, tenantId });
    return record;
  }

  async function persistCustomer(tenantId, customer) {
    if (!tenantId || !UUID_PATTERN.test(tenantId)) return null;
    const normalised = normaliseCustomer(customer);
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
          `INSERT INTO commerce_customers (id, tenant_id, external_customer_id, platform, email, first_name, last_name, phone, tags, accepts_marketing, created_at, updated_at, deleted_at)
           VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9::jsonb, $10, $11, $12, $13)
           ON CONFLICT (tenant_id, platform, external_customer_id) DO UPDATE SET
             email = EXCLUDED.email,
             first_name = EXCLUDED.first_name,
             last_name = EXCLUDED.last_name,
             phone = EXCLUDED.phone,
             tags = EXCLUDED.tags,
             updated_at = EXCLUDED.updated_at`,
          [
            record.id,
            record.tenantId,
            record.externalCustomerId,
            record.platform,
            record.email,
            record.firstName,
            record.lastName,
            record.phone,
            JSON.stringify(record.tags),
            record.acceptsMarketing,
            record.createdAt,
            record.updatedAt,
            record.deletedAt,
          ]
        );
      });
    }

    const db = await readJsonDb();
    if (db) {
      await updateJsonDb((current) => {
        if (!current.commerceCustomers) current.commerceCustomers = [];
        const existingIndex = current.commerceCustomers.findIndex(
          (c) => c.tenantId === tenantId && c.platform === 'shopify' && c.externalCustomerId === record.externalCustomerId
        );
        if (existingIndex >= 0) {
          current.commerceCustomers[existingIndex] = { ...current.commerceCustomers[existingIndex], ...record };
        } else {
          current.commerceCustomers.push(record);
        }
        return current;
      });
    }

    log.info('shopify customer synced', { customerId: record.externalCustomerId, tenantId });
    return record;
  }

  async function syncInventory(tenantId, productId, variantId, quantity) {
    if (!tenantId || !UUID_PATTERN.test(tenantId)) {
      throw new TypeError('Invalid tenantId');
    }
    const safeQuantity = clampNumber(quantity, 0, 0, Number.MAX_SAFE_INTEGER);
    const updatedAt = new Date().toISOString();

    if (postgresPool) {
      await withPgClient(async (client) => {
        await client.query(
          `UPDATE commerce_products
           SET variants = jsonb_set(variants, $1::text[], to_jsonb($2::int), true), updated_at = $3
           WHERE tenant_id = $4 AND platform = 'shopify' AND external_product_id = $5`,
          [
            `{${variantId ? `variants,${variantId}` : 'variants'},inventory}`,
            safeQuantity,
            updatedAt,
            tenantId,
            productId,
          ]
        );
      });
    }

    const db = await readJsonDb();
    if (db && db.commerceProducts) {
      await updateJsonDb((current) => {
        const product = current.commerceProducts.find(
          (p) => p.tenantId === tenantId && p.platform === 'shopify' && p.id === productId
        );
        if (product && product.variants.length > 0) {
          const variant = product.variants.find((v) => v.id === variantId) || product.variants[0];
          variant.inventory = safeQuantity;
          product.updatedAt = updatedAt;
        }
        return current;
      });
    }

    log.info('shopify inventory synced', { productId, variantId, quantity: safeQuantity, tenantId });
    return { productId, variantId, quantity: safeQuantity, updatedAt };
  }

  async function handleOrderWebhook(tenantId, payload) {
    if (!tenantId || !UUID_PATTERN.test(tenantId)) {
      throw new TypeError('Invalid tenantId');
    }
    const order = normaliseOrder(payload);
    if (!order) throw new TypeError('Invalid Shopify order payload');

    const record = await persistOrder(tenantId, payload);
    if (payload.customer) {
      await persistCustomer(tenantId, payload.customer);
    }

    log.info('shopify order webhook handled', { orderId: order.externalOrderId, tenantId });
    return { order: record, action: 'created_or_updated' };
  }

  async function handleInventoryWebhook(tenantId, payload) {
    if (!tenantId || !UUID_PATTERN.test(tenantId)) {
      throw new TypeError('Invalid tenantId');
    }
    const productId = typeof payload.product_id === 'string' ? payload.product_id.trim() : null;
    const variantId = typeof payload.variant_id === 'string' ? payload.variant_id.trim() : null;
    const inventory = typeof payload.inventory_quantity === 'number' ? payload.inventory_quantity : null;
    if (!productId || inventory === null) {
      throw new TypeError('Invalid Shopify inventory webhook payload');
    }

    const result = await syncInventory(tenantId, productId, variantId, inventory);
    log.info('shopify inventory webhook handled', { productId, variantId, tenantId });
    return result;
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
    log.info('shopify catalog synced', { tenantId, count: results.length });
    return results;
  }

  function getConnectionStatus() {
    return {
      configured,
      platform: 'shopify',
      connected: configured,
    };
  }

  return Object.freeze({
    syncCatalog,
    handleOrderWebhook,
    handleInventoryWebhook,
    syncInventory,
    getConnectionStatus,
    persistOrder,
    persistProduct,
    persistCustomer,
  });
}
