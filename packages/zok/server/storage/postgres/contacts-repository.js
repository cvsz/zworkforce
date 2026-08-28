const UUID_PATTERN = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;
const EMAIL_PATTERN = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

export function createContactsRepository(tx) {
  if (
    !tx ||
    typeof tx.query !== 'function' ||
    typeof tx.tenantId !== 'string' ||
    !UUID_PATTERN.test(tx.tenantId)
  ) {
    throw new TypeError('Tenant transaction context is required');
  }

  async function list() {
    const result = await tx.query(`
      SELECT id, name, email, phone, external_id AS "externalId", metadata, created_at AS "createdAt", updated_at AS "updatedAt"
      FROM contacts
      WHERE deleted_at IS NULL
      ORDER BY created_at ASC, id ASC
    `);
    return result.rows;
  }

  async function create(input = {}) {
    const name = typeof input.name === 'string' ? input.name.trim() : '';
    if (!name) throw new TypeError('Contact name is required');
    if (name.length > 240) throw new TypeError('Contact name exceeds 240 characters');

    let email = null;
    if (input.email !== undefined && input.email !== null && input.email !== '') {
      if (typeof input.email !== 'string') throw new TypeError('Valid contact email is required');
      email = input.email.trim().toLowerCase();
      if (!EMAIL_PATTERN.test(email) || email.length > 254) {
        throw new TypeError('Valid contact email is required');
      }
    }

    const phone = typeof input.phone === 'string' && input.phone.trim()
      ? input.phone.trim().slice(0, 80)
      : null;
    const externalId = typeof input.externalId === 'string' && input.externalId.trim()
      ? input.externalId.trim().slice(0, 255)
      : null;
    const metadata = input.metadata && typeof input.metadata === 'object' && !Array.isArray(input.metadata)
      ? input.metadata
      : {};

    const result = await tx.query(`
      INSERT INTO contacts (tenant_id, name, email, phone, external_id, metadata)
      VALUES ($1, $2, $3, $4, $5, $6::jsonb)
      RETURNING id, name, email, phone, external_id AS "externalId", metadata, created_at AS "createdAt", updated_at AS "updatedAt"
    `, [tx.tenantId, name, email, phone, externalId, JSON.stringify(metadata)]);
    return result.rows[0];
  }

  async function findById(id) {
    if (typeof id !== 'string' || !UUID_PATTERN.test(id)) {
      throw new TypeError('Valid contact id is required');
    }
    const result = await tx.query(`
      SELECT id, name, email, phone, external_id AS "externalId", metadata, created_at AS "createdAt", updated_at AS "updatedAt"
      FROM contacts
      WHERE id = $1 AND deleted_at IS NULL
      LIMIT 1
    `, [id]);
    return result.rows[0] || null;
  }

  async function replaceMetadata(id, metadata) {
    if (typeof id !== 'string' || !UUID_PATTERN.test(id)) {
      throw new TypeError('Valid contact id is required');
    }
    if (!metadata || typeof metadata !== 'object' || Array.isArray(metadata)) {
      throw new TypeError('Contact metadata must be an object');
    }
    const result = await tx.query(`
      UPDATE contacts
      SET metadata = $2::jsonb, updated_at = now()
      WHERE id = $1
      RETURNING id, name, email, phone, external_id AS "externalId", metadata, created_at AS "createdAt", updated_at AS "updatedAt"
    `, [id, JSON.stringify(metadata)]);
    return result.rows[0] || null;
  }

  return Object.freeze({ list, create, findById, replaceMetadata });
}