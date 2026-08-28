import { createCipheriv, createDecipheriv, randomBytes, scryptSync } from 'node:crypto';

const UUID_PATTERN = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;
const ENCRYPTION_ALGORITHM = 'aes-256-gcm';
const IV_BYTE_LENGTH = 16;
const AUTH_TAG_BYTE_LENGTH = 16;
const KEY_DERIVATION_LENGTH = 32;
const KEY_ID = 'master-v1';

function resolveMasterKey(masterKey) {
  if (masterKey instanceof Buffer && masterKey.length === KEY_DERIVATION_LENGTH) {
    return masterKey;
  }
  if (typeof masterKey === 'string' && masterKey.trim()) {
    return scryptSync(masterKey, 'zok-secrets-vault', KEY_DERIVATION_LENGTH);
  }
  const envKey = process.env.ZOK_SECRETS_MASTER_KEY;
  if (typeof envKey === 'string' && envKey.trim()) {
    return scryptSync(envKey, 'zok-secrets-vault', KEY_DERIVATION_LENGTH);
  }
  throw new Error(
    'ZOK_SECRETS_MASTER_KEY environment variable is required for secrets encryption',
  );
}

function encrypt(plaintext, masterKey) {
  const iv = randomBytes(IV_BYTE_LENGTH);
  const cipher = createCipheriv(ENCRYPTION_ALGORITHM, masterKey, iv);
  const encrypted = Buffer.concat([cipher.update(plaintext, 'utf8'), cipher.final()]);
  const authTag = cipher.getAuthTag();
  return {
    ciphertext: encrypted.toString('base64'),
    iv: iv.toString('base64'),
    authTag: authTag.toString('base64'),
  };
}

function decrypt(ciphertext, iv, authTag, masterKey) {
  const decipher = createDecipheriv(
    ENCRYPTION_ALGORITHM,
    masterKey,
    Buffer.from(iv, 'base64'),
  );
  decipher.setAuthTag(Buffer.from(authTag, 'base64'));
  const decrypted = Buffer.concat([
    decipher.update(Buffer.from(ciphertext, 'base64')),
    decipher.final(),
  ]);
  return decrypted.toString('utf8');
}

function serializeSecretValue(value) {
  return JSON.stringify({ value, encryptedAt: new Date().toISOString() });
}

function deserializeSecretValue(json) {
  try {
    const parsed = JSON.parse(json);
    if (parsed && typeof parsed === 'object' && 'value' in parsed) {
      return parsed.value;
    }
    return json;
  } catch {
    return json;
  }
}

export function createSecretsVault({ tx, masterKey } = {}) {
  if (!tx || typeof tx.query !== 'function') {
    throw new TypeError('Transaction context with query() is required');
  }
  const key = resolveMasterKey(masterKey);

  async function storeSecret({ name, provider, secretValue, integrationId = null }) {
    if (typeof name !== 'string' || !name.trim()) {
      throw new TypeError('Secret name is required');
    }
    if (secretValue === undefined || secretValue === null) {
      throw new TypeError('Secret value is required');
    }
    if (integrationId !== null && (typeof integrationId !== 'string' || !UUID_PATTERN.test(integrationId))) {
      throw new TypeError('integrationId must be a valid UUID or null');
    }
    const normalizedName = name.trim();
    if (normalizedName.length > 120) {
      throw new TypeError('Secret name exceeds 120 characters');
    }
    const payload = typeof secretValue === 'string' ? secretValue : serializeSecretValue(secretValue);
    const { ciphertext, iv, authTag } = encrypt(payload, key);

    const result = await tx.query(
      `INSERT INTO secrets (tenant_id, integration_id, name, provider, ciphertext, iv, auth_tag, key_id)
       VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
       RETURNING id, name, provider, key_id AS "keyId", status,
                 created_at AS "createdAt", updated_at AS "updatedAt"`,
      [
        tx.tenantId,
        integrationId,
        normalizedName,
        provider ?? null,
        ciphertext,
        iv,
        authTag,
        KEY_ID,
      ],
    );
    return result.rows[0];
  }

  async function getSecret({ id, actorUserId = null, requestId = null, reason = 'access' }) {
    if (typeof id !== 'string' || !UUID_PATTERN.test(id)) {
      throw new TypeError('Valid secret id is required');
    }
    const result = await tx.query(
      `SELECT id, tenant_id, integration_id, name, provider, ciphertext, iv, auth_tag, key_id, status
       FROM secrets
       WHERE tenant_id = $1 AND id = $2 AND deleted_at IS NULL
       LIMIT 1`,
      [tx.tenantId, id],
    );
    const record = result.rows[0];
    if (!record) return null;

    let value = null;
    try {
      value = decrypt(record.ciphertext, record.iv, record.auth_tag, key);
      value = deserializeSecretValue(value);
    } catch {
      throw new Error('Failed to decrypt secret: data may be corrupted or the master key has changed');
    }

    await logAccess({ secretId: record.id, action: reason, actorUserId, requestId });
    return { id: record.id, name: record.name, provider: record.provider, value };
  }

  async function getSecretMetadata(id) {
    if (typeof id !== 'string' || !UUID_PATTERN.test(id)) {
      throw new TypeError('Valid secret id is required');
    }
    const result = await tx.query(
      `SELECT id, name, provider, key_id AS "keyId", status,
              created_at AS "createdAt", updated_at AS "updatedAt"
       FROM secrets
       WHERE tenant_id = $1 AND id = $2 AND deleted_at IS NULL
       LIMIT 1`,
      [tx.tenantId, id],
    );
    return result.rows[0] || null;
  }

  async function listSecrets() {
    const result = await tx.query(
      `SELECT id, name, provider, key_id AS "keyId", status,
              created_at AS "createdAt", updated_at AS "updatedAt"
       FROM secrets
       WHERE tenant_id = $1 AND deleted_at IS NULL
       ORDER BY created_at ASC, id ASC`,
      [tx.tenantId],
    );
    return result.rows;
  }

  async function rotateSecret({ id, newSecretValue, actorUserId = null, requestId = null }) {
    if (typeof id !== 'string' || !UUID_PATTERN.test(id)) {
      throw new TypeError('Valid secret id is required');
    }
    if (newSecretValue === undefined || newSecretValue === null) {
      throw new TypeError('New secret value is required');
    }
    const existing = await getSecretMetadata(id);
    if (!existing) return null;

    const payload = typeof newSecretValue === 'string' ? newSecretValue : serializeSecretValue(newSecretValue);
    const { ciphertext, iv, authTag } = encrypt(payload, key);

    const result = await tx.query(
      `UPDATE secrets
       SET ciphertext = $3, iv = $4, auth_tag = $5, key_id = $6, updated_at = now()
       WHERE tenant_id = $1 AND id = $2 AND deleted_at IS NULL
       RETURNING id, name, provider, key_id AS "keyId", status,
                 created_at AS "createdAt", updated_at AS "updatedAt"`,
      [tx.tenantId, id, ciphertext, iv, authTag, KEY_ID],
    );
    const record = result.rows[0];
    if (record) {
      await logAccess({ secretId: id, action: 'rotate', actorUserId, requestId });
    }
    return record;
  }

  async function deleteSecret({ id, actorUserId = null, requestId = null }) {
    if (typeof id !== 'string' || !UUID_PATTERN.test(id)) {
      throw new TypeError('Valid secret id is required');
    }
    const result = await tx.query(
      `UPDATE secrets
       SET deleted_at = now(), updated_at = now()
       WHERE tenant_id = $1 AND id = $2 AND deleted_at IS NULL
       RETURNING id`,
      [tx.tenantId, id],
    );
    if (result.rows[0]) {
      await logAccess({ secretId: id, action: 'delete', actorUserId, requestId });
    }
    return Boolean(result.rows[0]);
  }

  async function logAccess({ secretId, action, actorUserId = null, requestId = null }) {
    if (typeof secretId !== 'string' || !UUID_PATTERN.test(secretId)) {
      throw new TypeError('Valid secret id is required for audit logging');
    }
    if (typeof action !== 'string' || !action.trim()) {
      throw new TypeError('Audit action is required');
    }
    await tx.query(
      `INSERT INTO secret_access_logs (tenant_id, secret_id, action, actor_user_id, request_id)
       VALUES ($1, $2, $3, $4, $5)`,
      [tx.tenantId, secretId, action.trim(), actorUserId ?? null, requestId ?? null],
    );
  }

  async function listAccessLogs({ secretId = null } = {}) {
    if (secretId !== null && (typeof secretId !== 'string' || !UUID_PATTERN.test(secretId))) {
      throw new TypeError('secretId must be a valid UUID or null');
    }
    if (secretId) {
      const result = await tx.query(
        `SELECT id, secret_id AS "secretId", action, actor_user_id AS "actorUserId",
                request_id AS "requestId", accessed_at AS "accessedAt"
         FROM secret_access_logs
         WHERE tenant_id = $1 AND secret_id = $2
         ORDER BY accessed_at DESC, id DESC`,
        [tx.tenantId, secretId],
      );
      return result.rows;
    }
    const result = await tx.query(
      `SELECT id, secret_id AS "secretId", action, actor_user_id AS "actorUserId",
              request_id AS "requestId", accessed_at AS "accessedAt"
       FROM secret_access_logs
       WHERE tenant_id = $1
       ORDER BY accessed_at DESC, id DESC`,
      [tx.tenantId],
    );
    return result.rows;
  }

  return Object.freeze({
    storeSecret,
    getSecret,
    getSecretMetadata,
    listSecrets,
    rotateSecret,
    deleteSecret,
    logAccess,
    listAccessLogs,
  });
}
