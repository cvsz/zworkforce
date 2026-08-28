import pg from 'pg';

const DEFAULT_CLEANUP_INTERVAL_MS = 5 * 60 * 1000;
const DEFAULT_RETENTION_MS = 10 * 60 * 1000;

export function createRateLimitStore(pool, options = {}) {
  if (!pool || typeof pool.connect !== 'function') {
    throw new TypeError('pg Pool is required');
  }

  const cleanupIntervalMs = options.cleanupIntervalMs ?? DEFAULT_CLEANUP_INTERVAL_MS;
  const retentionMs = options.retentionMs ?? DEFAULT_RETENTION_MS;

  let cleanupTimer = null;

  async function check(key, windowMs, max) {
    if (typeof key !== 'string' || key.length === 0) {
      throw new TypeError('key must be a non-empty string');
    }
    if (!Number.isSafeInteger(windowMs) || windowMs <= 0) {
      throw new TypeError('windowMs must be a positive integer');
    }
    if (!Number.isSafeInteger(max) || max <= 0) {
      throw new TypeError('max must be a positive integer');
    }

    const now = new Date();
    const windowStart = new Date(now.getTime() - windowMs);

    const client = await pool.connect();
    try {
      await client.query(
        'DELETE FROM rate_limit_records WHERE key = $1 AND requested_at < $2',
        [key, windowStart],
      );

      const countResult = await client.query(
        'SELECT count(*) AS count FROM rate_limit_records WHERE key = $1',
        [key],
      );
      const count = Number(countResult.rows[0]?.count ?? 0);

      if (count >= max) {
        const oldestResult = await client.query(
          'SELECT requested_at FROM rate_limit_records WHERE key = $1 ORDER BY requested_at ASC LIMIT 1',
          [key],
        );
        const oldest = oldestResult.rows[0]?.requested_at
          ? new Date(oldestResult.rows[0].requested_at)
          : now;
        const retryAfter = Math.max(
          0,
          Math.ceil((oldest.getTime() + windowMs - now.getTime()) / 1000),
        );
        return { allowed: false, remaining: 0, retryAfter };
      }

      await client.query(
        'INSERT INTO rate_limit_records (key, requested_at) VALUES ($1, $2)',
        [key, now],
      );

      const remaining = max - count - 1;
      return { allowed: true, remaining: Math.max(0, remaining), retryAfter: 0 };
    } finally {
      client.release();
    }
  }

  async function cleanupExpired() {
    const client = await pool.connect();
    try {
      const cutoff = new Date(Date.now() - retentionMs);
      await client.query(
        'DELETE FROM rate_limit_records WHERE requested_at < $1',
        [cutoff],
      );
    } finally {
      client.release();
    }
  }

  function startCleanup() {
    if (cleanupTimer) return;
    cleanupTimer = setInterval(() => {
      void cleanupExpired().catch((error) => {
        console.error('[rate-limit] cleanup failed:', error.message);
      });
    }, cleanupIntervalMs);
  }

  function stopCleanup() {
    if (cleanupTimer) {
      clearInterval(cleanupTimer);
      cleanupTimer = null;
    }
  }

  return Object.freeze({
    check,
    startCleanup,
    stopCleanup,
  });
}
