import { createHash } from 'node:crypto';

const KEY_HASH_ALGORITHM = 'sha256';

function hashKey(key) {
  return createHash(KEY_HASH_ALGORITHM).update(key).digest('hex');
}

function extractApiKey(req) {
  const header = req.get('x-api-key');
  if (typeof header === 'string' && header.trim()) {
    return header.trim();
  }
  const authorization = req.get('authorization');
  if (typeof authorization === 'string' && authorization.startsWith('Bearer ')) {
    return authorization.slice(7).trim();
  }
  return null;
}

/**
 * Middleware that authenticates requests via a tenant API key.
 * Runs before session auth. When a valid key is present it populates
 * req.tenantId / req.userId / req.user so downstream handlers and the
 * existing requireAuth guard treat the request as authenticated.
 */
export function createApiKeyMiddleware(postgresPool) {
  if (!postgresPool || typeof postgresPool.connect !== 'function') {
    return (req, res, next) => next();
  }

  return async function apiKeyMiddleware(req, res, next) {
    const apiKey = extractApiKey(req);
    if (!apiKey) {
      return next();
    }
    if (req.user) {
      return next();
    }

    const keyHash = hashKey(apiKey);
    const client = await postgresPool.connect();
    try {
      const result = await client.query(
        `SELECT id, tenant_id, name, status, expires_at, grace_period_ends_at
         FROM api_keys
         WHERE key_hash = $1 AND deleted_at IS NULL
         LIMIT 1`,
        [keyHash],
      );
      const record = result.rows[0];
      if (!record) {
        return res.status(401).json({ error: 'Invalid API key' });
      }

      const now = Date.now();
      const expired = record.expires_at && new Date(record.expires_at).getTime() <= now;
      const inGracePeriod =
        record.status === 'rotated' &&
        record.grace_period_ends_at &&
        new Date(record.grace_period_ends_at).getTime() > now;

      if ((expired && !inGracePeriod) || record.status === 'revoked' || record.status === 'expired') {
        return res.status(401).json({ error: 'Invalid API key' });
      }
      if (record.status === 'rotated' && !inGracePeriod) {
        return res.status(401).json({ error: 'Invalid API key' });
      }

      req.apiKey = { id: record.id, name: record.name };
      req.tenantId = record.tenant_id;
      req.userId = record.tenant_id;
      req.user = {
        id: record.tenant_id,
        tenantId: record.tenant_id,
        authMethod: 'api-key',
      };

      try {
        await client.query(
          `UPDATE api_keys SET last_used_at = now(), updated_at = now() WHERE id = $1`,
          [record.id],
        );
      } catch {
        // Usage tracking must never block the request.
      }

      return next();
    } catch {
      return res.status(500).json({ error: 'API key validation failed' });
    } finally {
      client.release();
    }
  };
}
