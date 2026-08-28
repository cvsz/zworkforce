import { randomUUID } from 'node:crypto';

const DEFAULT_RETENTION = {
  messages: 90,
  conversations: 180,
  contacts: 365,
  campaigns: 365,
  integrations: 365,
  aiConfig: 365,
  flowNodes: 365,
  sessions: 30,
  consentRecords: 365,
  users: 365,
};

const RETENTION_TABLES = [
  { key: 'messages', table: 'messages', dateColumn: 'sent_at' },
  { key: 'conversations', table: 'conversations', dateColumn: 'created_at' },
  { key: 'contacts', table: 'contacts', dateColumn: 'created_at' },
  { key: 'campaigns', table: 'campaigns', dateColumn: 'created_at' },
  { key: 'integrations', table: 'integrations', dateColumn: 'created_at' },
  { key: 'aiConfig', table: 'ai_config', dateColumn: 'created_at' },
  { key: 'flowNodes', table: 'flow_nodes', dateColumn: 'created_at' },
  { key: 'sessions', table: 'sessions', dateColumn: 'created_at' },
  { key: 'consentRecords', table: 'consent_records', dateColumn: 'recorded_at' },
  { key: 'users', table: 'users', dateColumn: 'created_at' },
];

export function createRetentionPolicy({ postgresPool, auditService }) {
  if (!postgresPool) {
    throw new TypeError('postgresPool is required');
  }

  async function emitAudit(tenantId, action, metadata = {}) {
    if (!auditService) return;
    try {
      await auditService.emit({
        tenant_id: tenantId,
        actor_user_id: null,
        action,
        resource_type: 'privacy',
        resource_id: tenantId,
        request_id: randomUUID(),
        occurred_at: new Date().toISOString(),
        metadata,
      });
    } catch {
      // audit is best-effort
    }
  }

  function getDefaultRetention(type) {
    return DEFAULT_RETENTION[type] || 365;
  }

  async function getRetentionStatus(tenantId) {
    if (!tenantId || typeof tenantId !== 'string') {
      throw new TypeError('tenantId is required');
    }

    const status = {};

    if (postgresPool) {
      const client = await postgresPool.connect();
      try {
        for (const { key, table, dateColumn } of RETENTION_TABLES) {
          const retentionDays = getDefaultRetention(key);
          const [totalResult, expiredResult, softDeletedResult] = await Promise.all([
            client.query(`SELECT COUNT(*) AS count FROM ${table} WHERE tenant_id = $1 AND deleted_at IS NULL`, [tenantId]),
            client.query(
              `SELECT COUNT(*) AS count FROM ${table} WHERE tenant_id = $1 AND deleted_at IS NULL AND ${dateColumn} < now() - interval '1 day' * $2`,
              [tenantId, retentionDays]
            ),
            client.query(`SELECT COUNT(*) AS count FROM ${table} WHERE tenant_id = $1 AND deleted_at IS NOT NULL`, [tenantId]),
          ]);

          status[key] = {
            total: Number(totalResult.rows[0]?.count || 0),
            expired: Number(expiredResult.rows[0]?.count || 0),
            softDeleted: Number(softDeletedResult.rows[0]?.count || 0),
            retentionDays,
          };
        }

        const auditResult = await client.query('SELECT COUNT(*) AS count FROM audit_events WHERE tenant_id = $1', [tenantId]);
        status.auditEvents = {
          total: Number(auditResult.rows[0]?.count || 0),
          expired: 0,
          softDeleted: 0,
          retentionDays: 'infinite',
          immutable: true,
        };
      } finally {
        client.release();
      }
    }

    return {
      tenantId,
      generatedAt: new Date().toISOString(),
      policies: DEFAULT_RETENTION,
      status,
    };
  }

  async function purgeExpired(tenantId, customRetention = {}) {
    if (!tenantId || typeof tenantId !== 'string') {
      throw new TypeError('tenantId is required');
    }

    const purged = {};

    if (postgresPool) {
      const client = await postgresPool.connect();
      try {
        for (const { key, table, dateColumn } of RETENTION_TABLES) {
          const retentionDays = customRetention[key] || getDefaultRetention(key);
          const result = await client.query(
            `DELETE FROM ${table} WHERE tenant_id = $1 AND deleted_at IS NOT NULL AND deleted_at < now() - interval '1 day' * $2`,
            [tenantId, retentionDays]
          );
          purged[key] = result.rowCount;
        }
      } finally {
        client.release();
      }
    }

    await emitAudit(tenantId, 'privacy.retention_purge', {
      purged,
      customRetention,
    });

    return {
      tenantId,
      purged,
      timestamp: new Date().toISOString(),
    };
  }

  let schedulerInterval = null;

  function startScheduler(intervalMs = 24 * 60 * 60 * 1000) {
    if (schedulerInterval) {
      clearInterval(schedulerInterval);
    }
    schedulerInterval = setInterval(async () => {
      console.log('[retention] scheduled purge tick - no tenant context in scheduler; use endpoint for targeted purge');
    }, intervalMs);
  }

  function stopScheduler() {
    if (schedulerInterval) {
      clearInterval(schedulerInterval);
      schedulerInterval = null;
    }
  }

  return Object.freeze({
    getRetentionStatus,
    purgeExpired,
    getDefaultRetention,
    startScheduler,
    stopScheduler,
  });
}
