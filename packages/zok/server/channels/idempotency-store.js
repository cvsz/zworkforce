import { createHmac } from 'node:crypto';
import { PROVIDERS } from './channel-contracts.js';

export function createIdempotencyStore(pool) {
  const usePostgres = pool != null && typeof pool.query === 'function';
  const memoryStore = new Map();

  if (usePostgres) {
    initializeTable(pool).catch(() => {
      // Table may already exist or pool may not be available in all contexts.
    });
  }

  async function initializeTable(poolInstance) {
    await poolInstance.query(`
      CREATE TABLE IF NOT EXISTS webhook_idempotency (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        key TEXT NOT NULL UNIQUE,
        provider TEXT NOT NULL,
        event_type TEXT NOT NULL,
        contact_id TEXT NOT NULL,
        processed_at TIMESTAMPTZ NOT NULL DEFAULT now(),
        expires_at TIMESTAMPTZ NOT NULL,
        payload JSONB NOT NULL DEFAULT '{}'::jsonb
      )
    `);
    await poolInstance.query(`
      CREATE INDEX IF NOT EXISTS webhook_idempotency_key_idx ON webhook_idempotency (key)
    `);
    await poolInstance.query(`
      CREATE INDEX IF NOT EXISTS webhook_idempotency_expires_idx ON webhook_idempotency (expires_at)
    `);
  }

  async function check(key) {
    if (typeof key !== 'string' || !key.trim()) {
      throw new TypeError('Idempotency key is required');
    }

    if (usePostgres) {
      try {
        const result = await pool.query(
          'SELECT id, key, expires_at FROM webhook_idempotency WHERE key = $1 LIMIT 1',
          [key.trim()],
        );
        const row = result.rows[0];
        if (!row) return false;
        if (new Date(row.expires_at).getTime() <= Date.now()) {
          await pool.query('DELETE FROM webhook_idempotency WHERE id = $1', [row.id]);
          return false;
        }
        return true;
      } catch {
        // Fall back to memory on database errors
      }
    }

    const record = memoryStore.get(key.trim());
    if (!record) return false;
    if (new Date(record.expiresAt).getTime() <= Date.now()) {
      memoryStore.delete(key.trim());
      return false;
    }
    return true;
  }

  async function mark(key, ttlSeconds = 86400, metadata = {}) {
    if (typeof key !== 'string' || !key.trim()) {
      throw new TypeError('Idempotency key is required');
    }
    const ttl = Number(ttlSeconds);
    if (!Number.isSafeInteger(ttl) || ttl <= 0) {
      throw new TypeError('TTL must be a positive integer in seconds');
    }

    const normalizedKey = key.trim();
    const now = new Date();
    const expiresAt = new Date(now.getTime() + ttl * 1000);

    const record = {
      key: normalizedKey,
      provider: typeof metadata.provider === 'string' ? metadata.provider : null,
      eventType: typeof metadata.eventType === 'string' ? metadata.eventType : null,
      contactId: typeof metadata.contactId === 'string' ? metadata.contactId : null,
      payload: metadata.payload && typeof metadata.payload === 'object' ? metadata.payload : {},
      expiresAt: expiresAt.toISOString(),
    };

    if (usePostgres) {
      try {
        await pool.query(
          `INSERT INTO webhook_idempotency (key, provider, event_type, contact_id, expires_at, payload)
           VALUES ($1, $2, $3, $4, $5, $6::jsonb)
           ON CONFLICT (key) DO NOTHING`,
          [normalizedKey, record.provider, record.eventType, record.contactId, record.expiresAt, JSON.stringify(record.payload)],
        );
        return;
      } catch {
        // Fall back to memory on database errors
      }
    }

    memoryStore.set(normalizedKey, record);
  }

  async function cleanExpired() {
    if (usePostgres) {
      try {
        await pool.query('DELETE FROM webhook_idempotency WHERE expires_at <= now()');
      } catch {
        // Ignore cleanup errors
      }
    }

    const now = Date.now();
    for (const [key, record] of memoryStore) {
      if (new Date(record.expiresAt).getTime() <= now) {
        memoryStore.delete(key);
      }
    }
  }

  async function getStats() {
    let postgresCount = 0;
    let memoryCount = memoryStore.size;

    if (usePostgres) {
      try {
        const result = await pool.query('SELECT count(*) AS count FROM webhook_idempotency');
        postgresCount = Number(result.rows[0]?.count || 0);
      } catch {
        // ignore
      }
    }

    return {
      postgres: postgresCount,
      memory: memoryCount,
      total: postgresCount + memoryCount,
    };
  }

  return Object.freeze({
    check,
    mark,
    cleanExpired,
    getStats,
  });
}
