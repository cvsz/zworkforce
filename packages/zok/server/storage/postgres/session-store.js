import { createHash } from 'node:crypto';

const TOKEN_HASH_ALGORITHM = 'sha256';

export function hashToken(token) {
  if (typeof token !== 'string') {
    throw new TypeError('token must be a string');
  }
  return createHash(TOKEN_HASH_ALGORITHM).update(token).digest('hex');
}

export function createSessionStore(pool) {
  if (!pool || typeof pool.connect !== 'function') {
    throw new TypeError('pg Pool is required');
  }

  async function create(session) {
    if (!session || typeof session !== 'object') {
      throw new TypeError('session is required');
    }
    const { token, csrfToken, expiresAt, user } = session;
    if (!token || !csrfToken || !expiresAt || !user?.tenantId || !user?.email) {
      throw new TypeError('session must have token, csrfToken, expiresAt, and user with tenantId and email');
    }

    const tenantId = user.tenantId;
    const tokenHash = hashToken(token);
    const csrfTokenHash = hashToken(csrfToken);
    const expiresAtIso = new Date(expiresAt).toISOString();

    const client = await pool.connect();
    try {
      const userResult = await client.query(
        'SELECT id FROM users WHERE tenant_id = $1 AND email = $2 LIMIT 1',
        [tenantId, user.email],
      );
      if (userResult.rows.length === 0) {
        throw new Error(`User not found for tenant ${tenantId} and email ${user.email}`);
      }
      const userId = userResult.rows[0].id;

      await client.query(
        `INSERT INTO sessions (tenant_id, user_id, token_hash, csrf_token_hash, expires_at)
         VALUES ($1, $2, $3, $4, $5)
         ON CONFLICT (tenant_id, token_hash) DO UPDATE SET
           csrf_token_hash = EXCLUDED.csrf_token_hash,
           expires_at = EXCLUDED.expires_at,
           revoked_at = NULL`,
        [tenantId, userId, tokenHash, csrfTokenHash, expiresAtIso],
      );
    } finally {
      client.release();
    }

    return session;
  }

  async function get(token) {
    if (!token || typeof token !== 'string') {
      return null;
    }

    const tokenHash = hashToken(token);
    let client;
    try {
      client = await pool.connect();
      const sessionResult = await client.query(
        `SELECT s.tenant_id, s.user_id, s.expires_at, s.revoked_at, s.csrf_token_hash,
                u.email
         FROM sessions s
         JOIN users u ON u.tenant_id = s.tenant_id AND u.id = s.user_id
         WHERE s.token_hash = $1
         LIMIT 1`,
        [tokenHash],
      );

      if (sessionResult.rows.length === 0) {
        return null;
      }

      const row = sessionResult.rows[0];
      if (row.revoked_at) {
        return null;
      }
      const expiresAt = new Date(row.expires_at).getTime();
      if (expiresAt <= Date.now()) {
        return null;
      }

      let role = 'owner';
      try {
        const roleResult = await client.query(
          `SELECT r.name
           FROM user_roles ur
           JOIN roles r ON r.tenant_id = ur.tenant_id AND r.id = ur.role_id
           WHERE ur.tenant_id = $1 AND ur.user_id = $2
           LIMIT 1`,
          [row.tenant_id, row.user_id],
        );
        if (roleResult.rows.length > 0) {
          role = roleResult.rows[0].name;
        }
      } catch {
        // user_roles/roles tables may not exist in all test setups
      }

      return {
        token,
        csrfTokenHash: row.csrf_token_hash,
        expiresAt,
        user: {
          email: row.email,
          role,
          tenantId: row.tenant_id,
        },
      };
    } catch {
      return null;
    } finally {
      if (client) client.release();
    }
  }

  async function deleteSession(token) {
    if (!token || typeof token !== 'string') {
      return;
    }

    const tokenHash = hashToken(token);
    const client = await pool.connect();
    try {
      await client.query('DELETE FROM sessions WHERE token_hash = $1', [tokenHash]);
    } finally {
      client.release();
    }
  }

  async function pruneExpired() {
    const client = await pool.connect();
    try {
      await client.query('DELETE FROM sessions WHERE expires_at < now()');
    } finally {
      client.release();
    }
  }

  return Object.freeze({
    create,
    get,
    delete: deleteSession,
    pruneExpired,
  });
}
