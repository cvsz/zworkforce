import { PROVIDERS } from './channel-contracts.js';

export function createConsentChecker(pool) {
  const usePostgres = pool != null && typeof pool.query === 'function';
  const memoryStore = new Map();

  async function resolveContactId(tenantId, contactId) {
    if (!usePostgres) return contactId;

    try {
      const result = await pool.query(
        'SELECT id FROM contacts WHERE tenant_id = $1 AND id = $2 LIMIT 1',
        [tenantId, contactId],
      );
      if (result.rows[0]) return result.rows[0].id;

      const externalResult = await pool.query(
        'SELECT id FROM contacts WHERE tenant_id = $1 AND external_id = $2 LIMIT 1',
        [tenantId, contactId],
      );
      return externalResult.rows[0]?.id || contactId;
    } catch {
      return contactId;
    }
  }

  async function isAllowed(contactId, channel, tenantId) {
    if (typeof contactId !== 'string' || !contactId.trim()) {
      throw new TypeError('contactId is required');
    }
    if (typeof channel !== 'string' || !PROVIDERS.includes(channel)) {
      throw new TypeError(`Invalid channel: ${channel}`);
    }

    const normalizedChannel = channel.trim().toLowerCase();
    const resolvedContactId = tenantId ? await resolveContactId(tenantId, contactId) : contactId;
    const storeKey = `${resolvedContactId}:${normalizedChannel}`;

    if (usePostgres && tenantId) {
      try {
        const result = await pool.query(
          `SELECT status FROM consent_records
           WHERE tenant_id = $1 AND contact_id = $2 AND channel = $3
           ORDER BY recorded_at DESC LIMIT 1`,
          [tenantId, resolvedContactId, normalizedChannel],
        );
        const row = result.rows[0];
        if (!row) return false;
        return row.status === 'granted';
      } catch {
        // Fall back to memory on database errors
      }
    }

    const record = memoryStore.get(storeKey);
    if (!record) return false;
    if (record.expiresAt && new Date(record.expiresAt).getTime() <= Date.now()) {
      memoryStore.delete(storeKey);
      return false;
    }
    return record.status === 'granted';
  }

  async function setConsent(contactId, channel, status, tenantId, source = 'api') {
    if (typeof contactId !== 'string' || !contactId.trim()) {
      throw new TypeError('contactId is required');
    }
    if (typeof channel !== 'string' || !PROVIDERS.includes(channel)) {
      throw new TypeError(`Invalid channel: ${channel}`);
    }
    if (typeof status !== 'string' || !['granted', 'revoked'].includes(status)) {
      throw new TypeError("Consent status must be 'granted' or 'revoked'");
    }

    const normalizedChannel = channel.trim().toLowerCase();
    const resolvedContactId = tenantId ? await resolveContactId(tenantId, contactId) : contactId;
    const storeKey = `${resolvedContactId}:${normalizedChannel}`;

    const record = {
      contactId: resolvedContactId,
      channel: normalizedChannel,
      status,
      source,
      recordedAt: new Date().toISOString(),
    };

    if (usePostgres && tenantId) {
      try {
        await pool.query(
          `INSERT INTO consent_records (tenant_id, contact_id, channel, status, source)
           VALUES ($1, $2, $3, $4, $5)`,
          [tenantId, resolvedContactId, normalizedChannel, status, source],
        );
        return record;
      } catch {
        // Fall back to memory on database errors
      }
    }

    memoryStore.set(storeKey, record);
    return record;
  }

  async function getConsent(contactId, channel, tenantId) {
    if (typeof contactId !== 'string' || !contactId.trim()) {
      throw new TypeError('contactId is required');
    }
    if (typeof channel !== 'string' || !PROVIDERS.includes(channel)) {
      throw new TypeError(`Invalid channel: ${channel}`);
    }

    const normalizedChannel = channel.trim().toLowerCase();
    const resolvedContactId = tenantId ? await resolveContactId(tenantId, contactId) : contactId;
    const storeKey = `${resolvedContactId}:${normalizedChannel}`;

    if (usePostgres && tenantId) {
      try {
        const result = await pool.query(
          `SELECT id, tenant_id AS "tenantId", contact_id AS "contactId", channel, status, source, recorded_at AS "recordedAt"
           FROM consent_records
           WHERE tenant_id = $1 AND contact_id = $2 AND channel = $3
           ORDER BY recorded_at DESC LIMIT 1`,
          [tenantId, resolvedContactId, normalizedChannel],
        );
        if (result.rows[0]) return result.rows[0];
      } catch {
        // ignore
      }
    }

    const record = memoryStore.get(storeKey);
    if (!record) return null;
    return {
      ...record,
      tenantId: tenantId || null,
      contactId: resolvedContactId,
      id: null,
    };
  }

  return Object.freeze({
    isAllowed,
    setConsent,
    getConsent,
  });
}
