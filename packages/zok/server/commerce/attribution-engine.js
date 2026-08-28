import { randomUUID } from 'node:crypto';

const UUID_PATTERN = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;
const TOUCHPOINT_CHANNELS = new Set([
  'whatsapp', 'line', 'messenger', 'tiktok', 'shopify', 'email', 'sms', 'web'
]);

function validateContactId(value) {
  if (!value || typeof value !== 'string') return null;
  return value.trim() || null;
}

function validateChannel(value) {
  if (typeof value !== 'string') return null;
  const channel = value.trim().toLowerCase();
  return TOUCHPOINT_CHANNELS.has(channel) ? channel : null;
}

function clampNumber(value, fallback, minimum, maximum) {
  const parsed = Number(value);
  return Number.isFinite(parsed) && parsed >= minimum && parsed <= maximum ? parsed : fallback;
}

export function createAttributionEngine({ postgresPool, jsonStorage, logger } = {}) {
  if (!postgresPool) {
    throw new Error('PostgreSQL pool is required for attribution engine');
  }
  const log = logger || { info: () => {}, warn: () => {}, error: () => {} };

  async function withPgClient(query) {
    if (!postgresPool) {
      throw new Error('PostgreSQL pool is required for attribution engine');
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

  async function recordTouchpoint({
    tenantId,
    contactId,
    channel,
    eventType = 'message',
    campaignId = null,
    messageId = null,
    metadata = {},
    occurredAt = new Date().toISOString(),
  }) {
    const validTenantId = typeof tenantId === 'string' && UUID_PATTERN.test(tenantId) ? tenantId : null;
    const validContactId = validateContactId(contactId);
    const validChannel = validateChannel(channel);
    if (!validTenantId || !validContactId || !validChannel) {
      throw new TypeError('Invalid attribution touchpoint: tenantId, contactId, and channel are required');
    }

    const touchpoint = {
      id: randomUUID(),
      tenantId: validTenantId,
      contactId: validContactId,
      channel: validChannel,
      eventType: typeof eventType === 'string' ? eventType.trim() : 'message',
      campaignId: typeof campaignId === 'string' && UUID_PATTERN.test(campaignId) ? campaignId : null,
      messageId: typeof messageId === 'string' ? messageId.trim() : null,
      metadata: typeof metadata === 'object' && !Array.isArray(metadata) ? metadata : {},
      occurredAt: typeof occurredAt === 'string' ? occurredAt : new Date().toISOString(),
      createdAt: new Date().toISOString(),
    };

    if (postgresPool) {
      await withPgClient(async (client) => {
        await client.query(
          `INSERT INTO attribution_touchpoints (id, tenant_id, contact_id, channel, event_type, campaign_id, message_id, metadata, occurred_at, created_at)
           VALUES ($1, $2, $3, $4, $5, $6, $7, $8::jsonb, $9, $10)`,
          [
            touchpoint.id,
            touchpoint.tenantId,
            touchpoint.contactId,
            touchpoint.channel,
            touchpoint.eventType,
            touchpoint.campaignId,
            touchpoint.messageId,
            JSON.stringify(touchpoint.metadata),
            touchpoint.occurredAt,
            touchpoint.createdAt,
          ]
        );
      });
    }

    const db = await readJsonDb();
    if (db) {
      await updateJsonDb((current) => {
        if (!current.attributionTouchpoints) current.attributionTouchpoints = [];
        current.attributionTouchpoints.push(touchpoint);
        return current;
      });
    }

    log.info('attribution touchpoint recorded', { touchpointId: touchpoint.id, channel: touchpoint.channel });
    return touchpoint;
  }

  async function attributeOrder({
    tenantId,
    contactId,
    orderId,
    orderValue,
    currency = 'USD',
    platform = 'zok',
    orderDate = new Date().toISOString(),
    model = 'last_touch',
    attributionWindowDays = 30,
  }) {
    const validTenantId = typeof tenantId === 'string' && UUID_PATTERN.test(tenantId) ? tenantId : null;
    const validContactId = validateContactId(contactId);
    if (!validTenantId || !validContactId) {
      throw new TypeError('Invalid attribution order: tenantId and contactId are required');
    }

    const value = clampNumber(orderValue, 0, 0, Number.MAX_SAFE_INTEGER);
    const windowMs = clampNumber(attributionWindowDays, 30, 1, 365) * 24 * 60 * 60 * 1000;
    const orderTimestamp = new Date(orderDate).getTime() || Date.now();
    const windowStart = new Date(orderTimestamp - windowMs).toISOString();

    let touchpoints = [];
    if (postgresPool) {
      const result = await withPgClient(async (client) => {
        const { rows } = await client.query(
          `SELECT id, channel, event_type, campaign_id, metadata, occurred_at
           FROM attribution_touchpoints
           WHERE tenant_id = $1 AND contact_id = $2 AND occurred_at >= $3
           ORDER BY occurred_at ASC`,
          [validTenantId, validContactId, windowStart]
        );
        return rows;
      });
      touchpoints = result;
    }

    const db = await readJsonDb();
    if (db && db.attributionTouchpoints && touchpoints.length === 0) {
      touchpoints = db.attributionTouchpoints.filter(
        (tp) => tp.tenantId === validTenantId && tp.contactId === validContactId && tp.occurredAt >= windowStart
      );
    }

    let attribution = [];
    if (model !== 'first_touch' && model !== 'last_touch' && model !== 'multi_touch_linear') {
      throw new TypeError(`Unsupported attribution model: ${model}`);
    }

    if (touchpoints.length === 0) {
      attribution = [];
    } else if (model === 'first_touch') {
      const first = touchpoints[0];
      attribution = [{
        touchpointId: first.id,
        channel: first.channel,
        campaignId: first.campaignId,
        eventType: first.eventType,
        weight: 1,
        credit: value,
        occurredAt: first.occurredAt,
      }];
    } else if (model === 'last_touch') {
      const last = touchpoints[touchpoints.length - 1];
      attribution = [{
        touchpointId: last.id,
        channel: last.channel,
        campaignId: last.campaignId,
        eventType: last.eventType,
        weight: 1,
        credit: value,
        occurredAt: last.occurredAt,
      }];
    } else if (model === 'multi_touch_linear') {
      const weight = 1 / touchpoints.length;
      attribution = touchpoints.map((tp) => ({
        touchpointId: tp.id,
        channel: tp.channel,
        campaignId: tp.campaignId,
        eventType: tp.eventType,
        weight,
        credit: value * weight,
        occurredAt: tp.occurredAt,
      }));
    } else {
      throw new TypeError(`Unsupported attribution model: ${model}`);
    }

    const attributionRecord = {
      id: randomUUID(),
      tenantId: validTenantId,
      contactId: validContactId,
      orderId: typeof orderId === 'string' ? orderId.trim() : String(orderId),
      orderValue: value,
      currency: typeof currency === 'string' ? currency.trim() : 'USD',
      platform: typeof platform === 'string' ? platform.trim() : 'zok',
      orderDate: new Date(orderDate).toISOString(),
      model,
      attributionWindowDays: clampNumber(attributionWindowDays, 30, 1, 365),
      touchpointCount: touchpoints.length,
      attribution,
      createdAt: new Date().toISOString(),
    };

    if (postgresPool) {
      await withPgClient(async (client) => {
        await client.query(
          `INSERT INTO order_attributions (id, tenant_id, contact_id, order_id, order_value, currency, platform, order_date, model, attribution_window_days, touchpoint_count, attribution, created_at)
           VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12::jsonb, $13)`,
          [
            attributionRecord.id,
            attributionRecord.tenantId,
            attributionRecord.contactId,
            attributionRecord.orderId,
            attributionRecord.orderValue,
            attributionRecord.currency,
            attributionRecord.platform,
            attributionRecord.orderDate,
            attributionRecord.model,
            attributionRecord.attributionWindowDays,
            attributionRecord.touchpointCount,
            JSON.stringify(attributionRecord.attribution),
            attributionRecord.createdAt,
          ]
        );
      });
    }

    const jsonDb = await readJsonDb();
    if (jsonDb) {
      await updateJsonDb((current) => {
        if (!current.orderAttributions) current.orderAttributions = [];
        current.orderAttributions.push(attributionRecord);
        return current;
      });
    }

    log.info('order attributed', {
      attributionId: attributionRecord.id,
      orderId: attributionRecord.orderId,
      model,
      touchpoints: touchpoints.length,
    });
    return attributionRecord;
  }

  async function getReport({
    tenantId,
    contactId = null,
    channel = null,
    startDate = null,
    endDate = null,
    model = null,
    limit = 100,
    offset = 0,
  }) {
    const validTenantId = typeof tenantId === 'string' && UUID_PATTERN.test(tenantId) ? tenantId : null;
    if (!validTenantId) {
      throw new TypeError('tenantId is required for attribution reports');
    }

    const safeLimit = clampNumber(limit, 100, 1, 1000);
    const safeOffset = clampNumber(offset, 0, 0, 10000);

    let rows = [];
    if (postgresPool) {
      const conditions = ['tenant_id = $1'];
      const values = [validTenantId];
      let idx = 2;

      if (contactId) {
        conditions.push(`contact_id = $${idx++}`);
        values.push(contactId);
      }
      if (channel) {
        conditions.push(`attribution @> $${idx++}::jsonb`);
        values.push(JSON.stringify([{ channel }]));
      }
      if (model) {
        conditions.push(`model = $${idx++}`);
        values.push(model);
      }
      if (startDate) {
        conditions.push(`order_date >= $${idx++}`);
        values.push(new Date(startDate).toISOString());
      }
      if (endDate) {
        conditions.push(`order_date <= $${idx++}`);
        values.push(new Date(endDate).toISOString());
      }

      const result = await withPgClient(async (client) => {
        const { rows: data } = await client.query(
          `SELECT id, contact_id, order_id, order_value, currency, platform, order_date, model, touchpoint_count, attribution, created_at
           FROM order_attributions
           WHERE ${conditions.join(' AND ')}
           ORDER BY created_at DESC
           LIMIT ${safeLimit} OFFSET ${safeOffset}`,
          values
        );
        return data;
      });
      rows = result;
    }

    const db = await readJsonDb();
    if (db && db.orderAttributions && rows.length === 0) {
      rows = db.orderAttributions.filter((rec) => {
        if (rec.tenantId !== validTenantId) return false;
        if (contactId && rec.contactId !== contactId) return false;
        if (model && rec.model !== model) return false;
        if (channel && !rec.attribution.some((a) => a.channel === channel)) return false;
        if (startDate && rec.orderDate < new Date(startDate).toISOString()) return false;
        if (endDate && rec.orderDate > new Date(endDate).toISOString()) return false;
        return true;
      }).slice(safeOffset, safeOffset + safeLimit);
    }

    const summary = {
      totalOrders: rows.length,
      totalValue: rows.reduce((sum, r) => sum + (Number(r.order_value) || 0), 0),
      byChannel: {},
      byModel: {},
    };

    for (const row of rows) {
      for (const attr of row.attribution || []) {
        summary.byChannel[attr.channel] = (summary.byChannel[attr.channel] || 0) + (Number(attr.credit) || 0);
      }
      summary.byModel[row.model] = (summary.byModel[row.model] || 0) + (Number(row.order_value) || 0);
    }

    return { rows, summary, limit: safeLimit, offset: safeOffset, total: rows.length };
  }

  return Object.freeze({
    recordTouchpoint,
    attributeOrder,
    getReport,
  });
}
