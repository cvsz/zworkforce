import { randomUUID } from 'node:crypto';

const UUID_PATTERN = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;
const PLATFORMS = new Set(['shopify', 'tiktok', 'lazada', 'shopee', 'zok']);
const RECONCILIATION_STATUSES = new Set([
  'pending', 'matched', 'mismatched', 'duplicate', 'missing', 'resolved', 'failed'
]);

function validatePlatform(value) {
  if (typeof value !== 'string') return null;
  const platform = value.trim().toLowerCase();
  return PLATFORMS.has(platform) ? platform : null;
}

function validateStatus(value) {
  if (typeof value !== 'string') return null;
  const status = value.trim().toLowerCase();
  return RECONCILIATION_STATUSES.has(status) ? status : null;
}

function clampNumber(value, fallback, minimum, maximum) {
  const parsed = Number(value);
  return Number.isFinite(parsed) && parsed >= minimum && parsed <= maximum ? parsed : fallback;
}

function buildOrderKey(order) {
  if (!order || typeof order !== 'object') return null;
  const platform = validatePlatform(order.platform);
  const externalOrderId = typeof order.externalOrderId === 'string' ? order.externalOrderId.trim() : '';
  if (!platform || !externalOrderId) return null;
  return `${platform}:${externalOrderId}`;
}

function normaliseOrder(order) {
  const platform = validatePlatform(order.platform);
  if (!platform) return null;
  return {
    externalOrderId: typeof order.externalOrderId === 'string' ? order.externalOrderId.trim() : '',
    platform,
    status: typeof order.status === 'string' ? order.status.trim() : 'unknown',
    total: clampNumber(order.total, 0, 0, Number.MAX_SAFE_INTEGER),
    currency: typeof order.currency === 'string' ? order.currency.trim() : 'USD',
    customerId: typeof order.customerId === 'string' ? order.customerId.trim() : null,
    orderDate: typeof order.orderDate === 'string' ? order.orderDate : new Date().toISOString(),
    items: Array.isArray(order.items) ? order.items : [],
    metadata: typeof order.metadata === 'object' && !Array.isArray(order.metadata) ? order.metadata : {},
  };
}

export function createReconciliationEngine({ postgresPool, jsonStorage, logger } = {}) {
  if (!postgresPool) {
    throw new Error('PostgreSQL pool is required for reconciliation engine');
  }
  const log = logger || { info: () => {}, warn: () => {}, error: () => {} };

  async function withPgClient(query) {
    if (!postgresPool) {
      throw new Error('PostgreSQL pool is required for reconciliation engine');
    }
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

  async function loadExistingOrders(tenantId) {
    const validTenantId = typeof tenantId === 'string' && UUID_PATTERN.test(tenantId) ? tenantId : null;
    if (!validTenantId) return [];

    let orders = [];
    if (postgresPool) {
      const result = await withPgClient(async (client) => {
        const { rows } = await client.query(
          `SELECT id, external_order_id, platform, status, total, currency, customer_id, order_date, items, metadata, deleted_at
           FROM commerce_orders
           WHERE tenant_id = $1 AND deleted_at IS NULL`,
          [validTenantId]
        );
        return rows;
      });
      orders = result;
    }

    const db = await readJsonDb();
    if (db && db.commerceOrders && orders.length === 0) {
      orders = db.commerceOrders.filter((o) => o.tenantId === validTenantId);
    }

    return orders;
  }

  async function reconcileOrders({
    tenantId,
    platformOrders = [],
    mode = 'automatic',
    reconciliationId = null,
  }) {
    const validTenantId = typeof tenantId === 'string' && UUID_PATTERN.test(tenantId) ? tenantId : null;
    if (!validTenantId) {
      throw new TypeError('tenantId is required for reconciliation');
    }

    const normalisedPlatformOrders = platformOrders.map(normaliseOrder).filter(Boolean);
    const existingOrders = await loadExistingOrders(validTenantId);
    const existingMap = new Map();
    const seenKeys = new Set();

    for (const order of existingOrders) {
      const key = buildOrderKey(order);
      if (!key) continue;
      if (seenKeys.has(key)) {
        const record = await markDuplicate(validTenantId, order, reconciliationId);
        log.warn('duplicate order detected during reconciliation', { orderKey: key, recordId: record.id });
        continue;
      }
      seenKeys.add(key);
      existingMap.set(key, order);
    }

    const results = [];
    const matchedKeys = new Set();

    for (const platformOrder of normalisedPlatformOrders) {
      const key = buildOrderKey(platformOrder);
      if (!key) continue;

      const existing = existingMap.get(key);
      if (existing) {
        matchedKeys.add(key);

        const isMatch = existing.status === platformOrder.status
          && Math.abs((Number(existing.total) || 0) - platformOrder.total) < 0.01
          && existing.currency === platformOrder.currency;

        const record = await persistReconciliationRecord({
          tenantId: validTenantId,
          platformOrder,
          existingOrder: existing,
          status: isMatch ? 'matched' : 'mismatched',
          mode,
          reconciliationId,
          differences: isMatch ? {} : {
            status: existing.status !== platformOrder.status,
            total: Math.abs((Number(existing.total) || 0) - platformOrder.total),
            currency: existing.currency !== platformOrder.currency,
          },
        });

        if (mode === 'automatic' && !isMatch) {
          await resolveReconciliation(validTenantId, record.id, 'manual_review_required');
        }

        results.push(record);
      } else {
        const record = await persistReconciliationRecord({
          tenantId: validTenantId,
          platformOrder,
          existingOrder: null,
          status: 'missing',
          mode,
          reconciliationId,
          differences: { missingInZok: true },
        });
        results.push(record);
      }
    }

    for (const [key, existing] of existingMap) {
      if (matchedKeys.has(key)) continue;
      const record = await persistReconciliationRecord({
        tenantId: validTenantId,
        platformOrder: null,
        existingOrder: existing,
        status: 'missing',
        mode,
        reconciliationId,
        differences: { missingInPlatform: true },
      });
      results.push(record);
    }

    log.info('reconciliation completed', {
      tenantId: validTenantId,
      mode,
      processed: results.length,
      matched: results.filter((r) => r.status === 'matched').length,
      mismatched: results.filter((r) => r.status === 'mismatched').length,
      missing: results.filter((r) => r.status === 'missing').length,
    });

    return results;
  }

  async function persistReconciliationRecord({
    tenantId,
    platformOrder,
    existingOrder,
    status,
    mode,
    reconciliationId,
    differences = {},
  }) {
    const record = {
      id: randomUUID(),
      tenantId,
      platformOrder,
      existingOrder,
      status,
      mode: typeof mode === 'string' ? mode.trim() : 'automatic',
      reconciliationId: typeof reconciliationId === 'string' ? reconciliationId : null,
      differences,
      resolvedAt: null,
      createdAt: new Date().toISOString(),
      updatedAt: new Date().toISOString(),
    };

    if (postgresPool) {
      await withPgClient(async (client) => {
        await client.query(
          `INSERT INTO reconciliation_records (id, tenant_id, platform_order, existing_order, status, mode, reconciliation_id, differences, resolved_at, created_at, updated_at)
           VALUES ($1, $2, $3, $4, $5, $6, $7, $8::jsonb, $9, $10, $11)`,
          [
            record.id,
            record.tenantId,
            JSON.stringify(record.platformOrder),
            JSON.stringify(record.existingOrder),
            record.status,
            record.mode,
            record.reconciliationId,
            JSON.stringify(record.differences),
            record.resolvedAt,
            record.createdAt,
            record.updatedAt,
          ]
        );
      });
    }

    const db = await readJsonDb();
    if (db) {
      await updateJsonDb((current) => {
        if (!current.reconciliationRecords) current.reconciliationRecords = [];
        current.reconciliationRecords.push(record);
        return current;
      });
    }

    return record;
  }

  async function markDuplicate(tenantId, order, reconciliationId) {
    return persistReconciliationRecord({
      tenantId,
      platformOrder: order,
      existingOrder: order,
      status: 'duplicate',
      mode: 'automatic',
      reconciliationId,
      differences: { duplicateKey: buildOrderKey(order) },
    });
  }

  async function resolveReconciliation(tenantId, recordId, resolution) {
    const validTenantId = typeof tenantId === 'string' && UUID_PATTERN.test(tenantId) ? tenantId : null;
    if (!validTenantId) {
      throw new TypeError('tenantId is required');
    }

    const validStatus = validateStatus(resolution);
    const allowedResolutions = new Set(['resolved', 'failed']);
    const finalStatus = allowedResolutions.has(validStatus) ? validStatus : 'resolved';

    const recordIdStr = typeof recordId === 'string' ? recordId.trim() : '';
    if (!recordIdStr || !UUID_PATTERN.test(recordIdStr)) {
      throw new TypeError('Invalid recordId');
    }

    const updatedAt = new Date().toISOString();

    if (postgresPool) {
      await withPgClient(async (client) => {
        await client.query(
          `UPDATE reconciliation_records
           SET status = $1, resolved_at = $2, updated_at = $3
           WHERE id = $4 AND tenant_id = $5`,
          [finalStatus, updatedAt, updatedAt, recordIdStr, validTenantId]
        );
      });
    }

    const db = await readJsonDb();
    if (db && db.reconciliationRecords) {
      await updateJsonDb((current) => {
        const record = current.reconciliationRecords.find((r) => r.id === recordIdStr);
        if (record) {
          record.status = finalStatus;
          record.resolvedAt = updatedAt;
          record.updatedAt = updatedAt;
        }
        return current;
      });
    }

    log.info('reconciliation record resolved', { recordId: recordIdStr, status: finalStatus });
    return { id: recordIdStr, status: finalStatus, resolvedAt: updatedAt };
  }

  async function getReconciliationReport({
    tenantId,
    status = null,
    platform = null,
    startDate = null,
    endDate = null,
    limit = 100,
    offset = 0,
  }) {
    const validTenantId = typeof tenantId === 'string' && UUID_PATTERN.test(tenantId) ? tenantId : null;
    if (!validTenantId) {
      throw new TypeError('tenantId is required for reconciliation reports');
    }

    const safeLimit = clampNumber(limit, 100, 1, 1000);
    const safeOffset = clampNumber(offset, 0, 0, 10000);

    let records = [];
    if (postgresPool) {
      const conditions = ['tenant_id = $1'];
      const values = [validTenantId];
      let idx = 2;

      if (status) {
        conditions.push(`status = $${idx++}`);
        values.push(status);
      }
      if (platform) {
        conditions.push(`platform_order->>'platform' = $${idx++}`);
        values.push(platform);
      }
      if (startDate) {
        conditions.push(`created_at >= $${idx++}`);
        values.push(new Date(startDate).toISOString());
      }
      if (endDate) {
        conditions.push(`created_at <= $${idx++}`);
        values.push(new Date(endDate).toISOString());
      }

      const result = await withPgClient(async (client) => {
        const { rows } = await client.query(
          `SELECT id, platform_order, existing_order, status, mode, reconciliation_id, differences, resolved_at, created_at, updated_at
           FROM reconciliation_records
           WHERE ${conditions.join(' AND ')}
           ORDER BY created_at DESC
           LIMIT ${safeLimit} OFFSET ${safeOffset}`,
          values
        );
        return rows;
      });
      records = result;
    }

    const db = await readJsonDb();
    if (db && db.reconciliationRecords && records.length === 0) {
      records = db.reconciliationRecords.filter((rec) => {
        if (rec.tenantId !== validTenantId) return false;
        if (status && rec.status !== status) return false;
        if (platform && rec.platformOrder?.platform !== platform) return false;
        if (startDate && rec.createdAt < new Date(startDate).toISOString()) return false;
        if (endDate && rec.createdAt > new Date(endDate).toISOString()) return false;
        return true;
      }).slice(safeOffset, safeOffset + safeLimit);
    }

    const summary = {
      total: records.length,
      matched: records.filter((r) => r.status === 'matched').length,
      mismatched: records.filter((r) => r.status === 'mismatched').length,
      missing: records.filter((r) => r.status === 'missing').length,
      duplicates: records.filter((r) => r.status === 'duplicate').length,
      resolved: records.filter((r) => r.status === 'resolved').length,
      failed: records.filter((r) => r.status === 'failed').length,
    };

    return { records, summary, limit: safeLimit, offset: safeOffset };
  }

  return Object.freeze({
    reconcileOrders,
    resolveReconciliation,
    getReconciliationReport,
    loadExistingOrders,
  });
}
