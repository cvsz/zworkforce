import { createHash, randomBytes } from 'node:crypto';

const UUID_PATTERN = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;
const KEY_STATUSES = new Set(['active', 'rotated', 'revoked', 'expired']);
const DEFAULT_KEY_TTL_DAYS = 90;
const MAX_KEY_TTL_DAYS = 365 * 2;
const MIN_KEY_TTL_DAYS = 1;
const KEY_BYTE_LENGTH = 32;
const KEY_PREFIX_LENGTH = 8;
const KEY_HASH_ALGORITHM = 'sha256';

function hashKey(key) {
  return createHash(KEY_HASH_ALGORITHM).update(key).digest('hex');
}

function generateKey() {
  const raw = randomBytes(KEY_BYTE_LENGTH).toString('base64url');
  const prefix = raw.slice(0, KEY_PREFIX_LENGTH);
  return { raw, prefix };
}

function normalizeStatus(status) {
  return KEY_STATUSES.has(status) ? status : 'active';
}

function resolveExpiresAt(expiresInDays, now = new Date()) {
  if (expiresInDays === null || expiresInDays === undefined) {
    const expiresAt = new Date(now.getTime() + DEFAULT_KEY_TTL_DAYS * 24 * 60 * 60 * 1000);
    return expiresAt.toISOString();
  }
  if (!Number.isSafeInteger(expiresInDays)) {
    throw new TypeError('expiresInDays must be an integer or null');
  }
  if (expiresInDays < MIN_KEY_TTL_DAYS || expiresInDays > MAX_KEY_TTL_DAYS) {
    throw new RangeError(
      `expiresInDays must be between ${MIN_KEY_TTL_DAYS} and ${MAX_KEY_TTL_DAYS}`,
    );
  }
  const expiresAt = new Date(now.getTime() + expiresInDays * 24 * 60 * 60 * 1000);
  return expiresAt.toISOString();
}

function maskRecord(record) {
  if (!record) return null;
  return {
    id: record.id,
    name: record.name,
    prefix: record.prefix,
    status: record.status,
    expiresAt: record.expires_at,
    gracePeriodEndsAt: record.grace_period_ends_at,
    lastUsedAt: record.last_used_at,
    rotatedFromId: record.rotated_from_id,
    createdAt: record.created_at,
    updatedAt: record.updated_at,
  };
}

/**
 * @param {object} tx - tenant transaction context { tenantId, query }
 *        For verify(), tenantId may be null (cross-tenant hash lookup).
 */
export function createApiKeyManager(tx) {
  if (!tx || typeof tx.query !== 'function') {
    throw new TypeError('Transaction context with query() is required');
  }

  async function create({ name, expiresInDays = DEFAULT_KEY_TTL_DAYS } = {}) {
    if (typeof name !== 'string' || !name.trim()) {
      throw new TypeError('Key name is required');
    }
    const normalizedName = name.trim();
    if (normalizedName.length > 120) {
      throw new TypeError('Key name exceeds 120 characters');
    }
    const { raw, prefix } = generateKey();
    const keyHash = hashKey(raw);
    const expiresAt = resolveExpiresAt(expiresInDays);

    const result = await tx.query(
      `INSERT INTO api_keys (tenant_id, name, key_hash, key_prefix, status, expires_at)
       VALUES ($1, $2, $3, $4, $5, $6)
       RETURNING id, name, key_prefix AS prefix, status, expires_at AS "expiresAt",
                 grace_period_ends_at AS "gracePeriodEndsAt", last_used_at AS "lastUsedAt",
                 rotated_from_id AS "rotatedFromId", created_at AS "createdAt", updated_at AS "updatedAt"`,
      [tx.tenantId, normalizedName, keyHash, prefix, 'active', expiresAt],
    );
    const record = result.rows[0];
    return { key: raw, record };
  }

  async function list() {
    const result = await tx.query(
      `SELECT id, name, key_prefix AS prefix, status, expires_at AS "expiresAt",
              grace_period_ends_at AS "gracePeriodEndsAt", last_used_at AS "lastUsedAt",
              rotated_from_id AS "rotatedFromId", created_at AS "createdAt", updated_at AS "updatedAt"
       FROM api_keys
       WHERE tenant_id = $1 AND deleted_at IS NULL
       ORDER BY created_at ASC, id ASC`,
      [tx.tenantId],
    );
    return result.rows;
  }

  async function getById(id) {
    if (typeof id !== 'string' || !UUID_PATTERN.test(id)) {
      throw new TypeError('Valid key id is required');
    }
    const result = await tx.query(
      `SELECT id, name, key_prefix AS prefix, status, expires_at AS "expiresAt",
              grace_period_ends_at AS "gracePeriodEndsAt", last_used_at AS "lastUsedAt",
              rotated_from_id AS "rotatedFromId", created_at AS "createdAt", updated_at AS "updatedAt"
       FROM api_keys
       WHERE tenant_id = $1 AND id = $2 AND deleted_at IS NULL
       LIMIT 1`,
      [tx.tenantId, id],
    );
    return result.rows[0] || null;
  }

  async function verify(rawKey) {
    if (typeof rawKey !== 'string' || !rawKey.trim()) {
      return null;
    }
    const keyHash = hashKey(rawKey);
    const result = await tx.query(
      `SELECT id, tenant_id AS "tenantId", name, key_prefix AS prefix, status,
              expires_at AS "expiresAt", grace_period_ends_at AS "gracePeriodEndsAt",
              last_used_at AS "lastUsedAt", created_at AS "createdAt", updated_at AS "updatedAt"
       FROM api_keys
       WHERE key_hash = $1 AND deleted_at IS NULL
       LIMIT 1`,
      [keyHash],
    );
    const record = result.rows[0];
    if (!record) return null;

    const now = Date.now();
    const expired = record.expiresAt && new Date(record.expiresAt).getTime() <= now;
    const inGracePeriod =
      record.status === 'rotated' &&
      record.gracePeriodEndsAt &&
      new Date(record.gracePeriodEndsAt).getTime() > now;

    if (expired && !inGracePeriod) {
      return null;
    }
    if (record.status === 'revoked') {
      return null;
    }
    if (record.status === 'rotated' && !inGracePeriod) {
      return null;
    }

    try {
      await tx.query(
        `UPDATE api_keys SET last_used_at = now(), updated_at = now() WHERE id = $1`,
        [record.id],
      );
    } catch {
      // Usage tracking must never block authentication.
    }
    record.lastUsedAt = new Date().toISOString();
    return record;
  }

  async function rotate(id, { gracePeriodDays = 7, expiresInDays = DEFAULT_KEY_TTL_DAYS } = {}) {
    if (typeof id !== 'string' || !UUID_PATTERN.test(id)) {
      throw new TypeError('Valid key id is required');
    }
    if (!Number.isSafeInteger(gracePeriodDays) || gracePeriodDays < 0 || gracePeriodDays > 90) {
      throw new RangeError('gracePeriodDays must be an integer between 0 and 90');
    }
    const existing = await getById(id);
    if (!existing) return null;

    const { raw, prefix } = generateKey();
    const keyHash = hashKey(raw);
    const expiresAt = resolveExpiresAt(expiresInDays);
    const graceEndsAt = new Date(Date.now() + gracePeriodDays * 24 * 60 * 60 * 1000).toISOString();

    await tx.query(
      `UPDATE api_keys
       SET status = 'rotated', grace_period_ends_at = $2, updated_at = now()
       WHERE tenant_id = $1 AND id = $3`,
      [tx.tenantId, graceEndsAt, id],
    );

    const result = await tx.query(
      `INSERT INTO api_keys (tenant_id, name, key_hash, key_prefix, status, expires_at, rotated_from_id)
       VALUES ($1, $2, $3, $4, $5, $6, $7)
       RETURNING id, name, key_prefix AS prefix, status, expires_at AS "expiresAt",
                 grace_period_ends_at AS "gracePeriodEndsAt", last_used_at AS "lastUsedAt",
                 rotated_from_id AS "rotatedFromId", created_at AS "createdAt", updated_at AS "updatedAt"`,
      [tx.tenantId, existing.name, keyHash, prefix, 'active', expiresAt, id],
    );
    return { key: raw, record: result.rows[0] };
  }

  async function revoke(id) {
    if (typeof id !== 'string' || !UUID_PATTERN.test(id)) {
      throw new TypeError('Valid key id is required');
    }
    const result = await tx.query(
      `UPDATE api_keys
       SET status = 'revoked', updated_at = now()
       WHERE tenant_id = $1 AND id = $2 AND deleted_at IS NULL
       RETURNING id, name, key_prefix AS prefix, status, expires_at AS "expiresAt",
                 grace_period_ends_at AS "gracePeriodEndsAt", last_used_at AS "lastUsedAt",
                 rotated_from_id AS "rotatedFromId", created_at AS "createdAt", updated_at AS "updatedAt"`,
      [tx.tenantId, id],
    );
    return result.rows[0] || null;
  }

  async function purgeExpired() {
    const result = await tx.query(
      `UPDATE api_keys
       SET status = 'expired', updated_at = now()
       WHERE tenant_id = $1 AND status = 'active' AND expires_at <= now() AND deleted_at IS NULL
       RETURNING id`,
      [tx.tenantId],
    );
    return result.rows.length;
  }

  return Object.freeze({
    create,
    list,
    getById,
    verify,
    rotate,
    revoke,
    purgeExpired,
    maskRecord,
  });
}
