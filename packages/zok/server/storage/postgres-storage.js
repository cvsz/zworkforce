import pg from 'pg';

const { Pool } = pg;
const UUID_PATTERN = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;

export function createPostgresPool({ connectionString, max = 10, idleTimeoutMillis = 30_000 } = {}) {
  if (!connectionString || typeof connectionString !== 'string') {
    throw new TypeError('connectionString is required');
  }
  if (!Number.isSafeInteger(max) || max < 1 || max > 100) {
    throw new TypeError('max must be an integer between 1 and 100');
  }
  return new Pool({ connectionString, max, idleTimeoutMillis });
}

export function createPostgresStorage({ pool } = {}) {
  if (!pool || typeof pool.connect !== 'function' || typeof pool.end !== 'function') {
    throw new TypeError('pool with connect() and end() is required');
  }

  let closed = false;

  async function withTenantTransaction(tenantId, operation) {
    if (typeof tenantId !== 'string' || !UUID_PATTERN.test(tenantId)) {
      throw new TypeError('tenantId is required and must be a UUID');
    }
    if (typeof operation !== 'function') {
      throw new TypeError('operation must be a function');
    }
    if (closed) throw new Error('PostgreSQL storage is closed');

    const client = await pool.connect();
    try {
      await client.query('BEGIN');
      await client.query("SELECT set_config('app.tenant_id', $1, true)", [tenantId]);
      const result = await operation(Object.freeze({
        tenantId,
        query(text, values) {
          return client.query(text, values);
        },
      }));
      await client.query('COMMIT');
      return result;
    } catch (error) {
      await client.query('ROLLBACK').catch(() => undefined);
      throw error;
    } finally {
      client.release();
    }
  }

  async function withSessionAdvisoryLock(lockKey, operation) {
    if (typeof lockKey !== 'string' || lockKey.length === 0 || lockKey.length > 512) {
      throw new TypeError('lockKey is required and must be a non-empty string up to 512 characters');
    }
    if (typeof operation !== 'function') {
      throw new TypeError('operation must be a function');
    }
    if (closed) throw new Error('PostgreSQL storage is closed');

    const client = await pool.connect();
    let acquired = false;
    try {
      const lockResult = await client.query(
        'SELECT pg_try_advisory_lock(hashtextextended($1, 0)) AS acquired',
        [lockKey],
      );
      acquired = lockResult.rows[0]?.acquired === true;
      if (!acquired) {
        throw new Error('PostgreSQL advisory lock is already held');
      }
      return await operation();
    } finally {
      if (acquired) {
        await client.query(
          'SELECT pg_advisory_unlock(hashtextextended($1, 0))',
          [lockKey],
        ).catch(() => undefined);
      }
      client.release();
    }
  }

  async function withIdentityTransaction(identity, operation) {
    if (!identity || typeof identity !== 'object' || Array.isArray(identity)) {
      throw new TypeError('identity with tenantId is required');
    }
    if (typeof identity.tenantId !== 'string' || !UUID_PATTERN.test(identity.tenantId)) {
      throw new TypeError('identity tenantId is required and must be a UUID');
    }
    return withTenantTransaction(identity.tenantId, operation);
  }

  async function close() {
    if (closed) return;
    closed = true;
    await pool.end();
  }

  return Object.freeze({
    withTenantTransaction,
    withSessionAdvisoryLock,
    withIdentityTransaction,
    close,
  });
}
