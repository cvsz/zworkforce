const UUID_PATTERN = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;
const INTEGRATION_STATUSES = new Set(['disconnected', 'connected', 'error', 'disabled']);

function maskKey(prefix) {
  if (typeof prefix === 'string' && prefix.length > 0) {
    return `${prefix}…••••`;
  }
  return null;
}

function maskRow(row) {
  if (!row) return row;
  return {
    id: row.id,
    provider: row.provider,
    externalId: row.externalId,
    status: row.status,
    config: row.config,
    apiKey: maskKey(row.apiKeyPrefix),
    hasCredentials: row.hasCredentials,
    createdAt: row.createdAt,
    updatedAt: row.updatedAt,
  };
}

export function createIntegrationsRepository(tx) {
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
      SELECT id, provider, external_id AS "externalId", status, config,
        api_key_prefix AS "apiKeyPrefix",
        (credentials_encrypted IS NOT NULL) AS "hasCredentials",
        created_at AS "createdAt", updated_at AS "updatedAt"
      FROM integrations
      WHERE deleted_at IS NULL
      ORDER BY created_at ASC, id ASC
    `);
    return result.rows.map(maskRow);
  }

  async function findByProvider(provider) {
    if (typeof provider !== 'string' || !provider.trim()) {
      throw new TypeError('Valid provider is required');
    }
    const normalizedProvider = provider.trim();
    if (normalizedProvider.length > 120) {
      throw new TypeError('Provider exceeds 120 characters');
    }

    const result = await tx.query(`
      SELECT id, provider, external_id AS "externalId", status, config,
        api_key_prefix AS "apiKeyPrefix",
        (credentials_encrypted IS NOT NULL) AS "hasCredentials",
        created_at AS "createdAt", updated_at AS "updatedAt"
      FROM integrations
      WHERE provider = $1 AND deleted_at IS NULL
      LIMIT 1
    `, [normalizedProvider]);
    return maskRow(result.rows[0] || null);
  }

  async function toggleStatus(id) {
    if (typeof id !== 'string' || !id.trim()) {
      throw new TypeError('Valid integration id is required');
    }
    const current = await tx.query(`
      SELECT id, status FROM integrations WHERE id = $1 LIMIT 1
    `, [id]);
    const row = current.rows[0];
    if (!row) return null;

    const nextStatus = row.status === 'connected' ? 'disconnected' : 'connected';
    const result = await tx.query(`
      UPDATE integrations
      SET status = $2, updated_at = now()
      WHERE id = $1
      RETURNING id, provider, external_id AS "externalId", status, config,
        api_key_prefix AS "apiKeyPrefix",
        (credentials_encrypted IS NOT NULL) AS "hasCredentials",
        created_at AS "createdAt", updated_at AS "updatedAt"
    `, [id, nextStatus]);
    return maskRow(result.rows[0]);
  }

  async function storeApiKey(id, keyHash, keyPrefix) {
    if (typeof id !== 'string' || !id.trim()) {
      throw new TypeError('Valid integration id is required');
    }
    if (typeof keyHash !== 'string' || !keyHash.trim()) {
      throw new TypeError('API key hash is required');
    }
    if (typeof keyPrefix !== 'string' || !keyPrefix.trim()) {
      throw new TypeError('API key prefix is required');
    }
    const result = await tx.query(`
      UPDATE integrations
      SET api_key_hash = $2, api_key_prefix = $3, updated_at = now()
      WHERE id = $1 AND deleted_at IS NULL
      RETURNING id
    `, [id, keyHash, keyPrefix]);
    return Boolean(result.rows[0]);
  }

  async function storeEncryptedCredentials(id, encryptedPayload) {
    if (typeof id !== 'string' || !id.trim()) {
      throw new TypeError('Valid integration id is required');
    }
    if (typeof encryptedPayload !== 'string' || !encryptedPayload.trim()) {
      throw new TypeError('Encrypted credentials payload is required');
    }
    const result = await tx.query(`
      UPDATE integrations
      SET credentials_encrypted = $2, updated_at = now()
      WHERE id = $1 AND deleted_at IS NULL
      RETURNING id
    `, [id, encryptedPayload]);
    return Boolean(result.rows[0]);
  }

  async function getApiKeyHash(id) {
    if (typeof id !== 'string' || !id.trim()) {
      throw new TypeError('Valid integration id is required');
    }
    const result = await tx.query(`
      SELECT api_key_hash AS "apiKeyHash" FROM integrations
      WHERE id = $1 AND deleted_at IS NULL
      LIMIT 1
    `, [id]);
    const row = result.rows[0];
    return row ? row.apiKeyHash : null;
  }

  async function rotateApiKey(id, keyHash, keyPrefix) {
    if (typeof id !== 'string' || !id.trim()) {
      throw new TypeError('Valid integration id is required');
    }
    if (typeof keyHash !== 'string' || !keyHash.trim()) {
      throw new TypeError('API key hash is required');
    }
    if (typeof keyPrefix !== 'string' || !keyPrefix.trim()) {
      throw new TypeError('API key prefix is required');
    }
    const result = await tx.query(`
      UPDATE integrations
      SET api_key_hash = $2, api_key_prefix = $3, updated_at = now()
      WHERE id = $1 AND deleted_at IS NULL
      RETURNING id, provider, external_id AS "externalId", status, config,
        api_key_prefix AS "apiKeyPrefix",
        (credentials_encrypted IS NOT NULL) AS "hasCredentials",
        created_at AS "createdAt", updated_at AS "updatedAt"
    `, [id, keyHash, keyPrefix]);
    return maskRow(result.rows[0] || null);
  }

  async function clearCredentials(id) {
    if (typeof id !== 'string' || !id.trim()) {
      throw new TypeError('Valid integration id is required');
    }
    const result = await tx.query(`
      UPDATE integrations
      SET credentials_encrypted = NULL, updated_at = now()
      WHERE id = $1 AND deleted_at IS NULL
      RETURNING id
    `, [id]);
    return Boolean(result.rows[0]);
  }

  return Object.freeze({
    list,
    findByProvider,
    toggleStatus,
    storeApiKey,
    storeEncryptedCredentials,
    getApiKeyHash,
    rotateApiKey,
    clearCredentials,
  });
}
