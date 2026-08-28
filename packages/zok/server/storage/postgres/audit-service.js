import pg from 'pg';

const REQUIRED_FIELDS = [
  'tenant_id',
  'actor_user_id',
  'action',
  'resource_type',
  'resource_id',
  'request_id',
  'occurred_at',
];

export function createAuditService(pool) {
  if (!pool || typeof pool.connect !== 'function') {
    throw new TypeError('pg Pool is required');
  }

  async function emit(event) {
    if (!event || typeof event !== 'object') {
      console.error('[audit] invalid event: event must be an object');
      return;
    }

    const missing = REQUIRED_FIELDS.filter((field) => !(field in event));
    if (missing.length > 0) {
      console.error(`[audit] invalid event: missing fields ${missing.join(', ')}`);
      return;
    }

    const client = await pool.connect();
    try {
      await client.query(
        `INSERT INTO audit_events (tenant_id, actor_user_id, action, resource_type, resource_id, request_id, metadata, occurred_at)
         VALUES ($1, $2, $3, $4, $5, $6, $7, $8)`,
        [
          event.tenant_id,
          event.actor_user_id,
          event.action,
          event.resource_type,
          event.resource_id ?? null,
          event.request_id,
          event.metadata ?? {},
          event.occurred_at,
        ]
      );
    } catch (error) {
      console.error(`[audit] failed to emit event: ${error.message}`);
    } finally {
      client.release();
    }
  }

  return Object.freeze({ emit });
}
