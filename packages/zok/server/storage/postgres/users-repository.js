import { createPasswordHash, verifyPassword } from '../../utils/password.js';

const UUID_PATTERN = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;
const EMAIL_PATTERN = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
const MAX_DISPLAY_NAME = 240;
const MAX_EMAIL_LENGTH = 254;
const VALID_STATUSES = new Set(['active', 'disabled']);

export function createUsersRepository(tx) {
  if (
    !tx ||
    typeof tx.query !== 'function' ||
    typeof tx.tenantId !== 'string' ||
    !UUID_PATTERN.test(tx.tenantId)
  ) {
    throw new TypeError('Tenant transaction context is required');
  }

  function sanitizeUser(row) {
    if (!row || typeof row !== 'object') return null;
    const { passwordHash, ...rest } = row;
    return rest;
  }

  async function create(input = {}) {
    const email = typeof input.email === 'string' ? input.email.trim().toLowerCase() : '';
    if (!EMAIL_PATTERN.test(email) || email.length > MAX_EMAIL_LENGTH) {
      throw new TypeError('Valid email is required');
    }

    const displayName = typeof input.displayName === 'string' && input.displayName.trim()
      ? input.displayName.trim().slice(0, MAX_DISPLAY_NAME)
      : null;
    const passwordHash = typeof input.password === 'string' && input.password.length >= 12
      ? createPasswordHash(input.password)
      : null;
    const status = VALID_STATUSES.has(input.status) ? input.status : 'active';

    const result = await tx.query(`
      INSERT INTO users (tenant_id, email, display_name, password_hash, status)
      VALUES ($1, $2, $3, $4, $5)
      RETURNING id, tenant_id AS "tenantId", email, display_name AS "displayName",
        password_hash AS "passwordHash", status, created_at AS "createdAt", updated_at AS "updatedAt"
    `, [tx.tenantId, email, displayName, passwordHash, status]);
    return sanitizeUser(result.rows[0]);
  }

  async function findById(id) {
    if (typeof id !== 'string' || !UUID_PATTERN.test(id)) {
      throw new TypeError('Valid user id is required');
    }
    const result = await tx.query(`
      SELECT id, tenant_id AS "tenantId", email, display_name AS "displayName",
        status, created_at AS "createdAt", updated_at AS "updatedAt"
      FROM users
      WHERE id = $1 AND deleted_at IS NULL
      LIMIT 1
    `, [id]);
    return result.rows[0] || null;
  }

  async function findByEmail(email) {
    if (typeof email !== 'string' || !email.trim()) {
      throw new TypeError('Valid email is required');
    }
    const normalizedEmail = email.trim().toLowerCase();
    const result = await tx.query(`
      SELECT id, tenant_id AS "tenantId", email, display_name AS "displayName",
        status, created_at AS "createdAt", updated_at AS "updatedAt"
      FROM users
      WHERE tenant_id = $1 AND email = $2 AND deleted_at IS NULL
      LIMIT 1
    `, [tx.tenantId, normalizedEmail]);
    return result.rows[0] || null;
  }

  async function list() {
    const result = await tx.query(`
      SELECT id, tenant_id AS "tenantId", email, display_name AS "displayName",
        status, created_at AS "createdAt", updated_at AS "updatedAt"
      FROM users
      WHERE deleted_at IS NULL
      ORDER BY created_at ASC, id ASC
    `);
    return result.rows;
  }

  async function update(id, input = {}) {
    if (typeof id !== 'string' || !UUID_PATTERN.test(id)) {
      throw new TypeError('Valid user id is required');
    }

    const updates = [];
    const values = [];
    let parameterIndex = 1;

    if ('email' in input) {
      const email = typeof input.email === 'string' ? input.email.trim().toLowerCase() : '';
      if (!EMAIL_PATTERN.test(email) || email.length > MAX_EMAIL_LENGTH) {
        throw new TypeError('Valid email is required');
      }
      updates.push(`email = $${parameterIndex++}`);
      values.push(email);
    }

    if ('displayName' in input) {
      const displayName = typeof input.displayName === 'string' && input.displayName.trim()
        ? input.displayName.trim().slice(0, MAX_DISPLAY_NAME)
        : null;
      updates.push(`display_name = $${parameterIndex++}`);
      values.push(displayName);
    }

    if ('status' in input) {
      if (!VALID_STATUSES.has(input.status)) throw new TypeError('Status must be active or disabled');
      updates.push(`status = $${parameterIndex++}`);
      values.push(input.status);
    }

    if ('password' in input) {
      const passwordHash = typeof input.password === 'string' && input.password.length >= 12
        ? createPasswordHash(input.password)
        : null;
      updates.push(`password_hash = $${parameterIndex++}`);
      values.push(passwordHash);
    }

    if (updates.length === 0) {
      return findById(id);
    }

    updates.push(`updated_at = now()`);
    values.push(tx.tenantId, id);

    const result = await tx.query(`
      UPDATE users
      SET ${updates.join(', ')}
      WHERE tenant_id = $${parameterIndex++} AND id = $${parameterIndex++} AND deleted_at IS NULL
      RETURNING id, tenant_id AS "tenantId", email, display_name AS "displayName",
        status, created_at AS "createdAt", updated_at AS "updatedAt"
    `, values);
    return result.rows[0] || null;
  }

  async function removeUser(id) {
    if (typeof id !== 'string' || !UUID_PATTERN.test(id)) {
      throw new TypeError('Valid user id is required');
    }
    const result = await tx.query(`
      DELETE FROM users
      WHERE tenant_id = $1 AND id = $2
    `, [tx.tenantId, id]);
    return result.rowCount > 0;
  }

  async function authenticate(email, password) {
    if (typeof email !== 'string' || typeof password !== 'string') {
      return null;
    }
    const result = await tx.query(`
      SELECT id, email, display_name AS "displayName", password_hash AS "passwordHash",
        status, created_at AS "createdAt", updated_at AS "updatedAt"
      FROM users
      WHERE tenant_id = $1 AND email = $2 AND deleted_at IS NULL
      LIMIT 1
    `, [tx.tenantId, email.trim().toLowerCase()]);

    const user = result.rows[0];
    if (!user || user.status !== 'active') return null;
    if (!user.passwordHash) return null;

    if (verifyPassword(password, user.passwordHash)) {
      const { passwordHash, ...safeUser } = user;
      return safeUser;
    }
    return null;
  }

  return Object.freeze({ create, findById, findByEmail, list, update, removeUser, authenticate });
}
