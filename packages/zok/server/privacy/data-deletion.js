import { randomUUID } from 'node:crypto';

const PROTECTED_TYPES = new Set(['audit_events', 'audit_events']);

const VALID_DELETION_TYPES = new Set([
  'all',
  'chats',
  'messages',
  'conversations',
  'contacts',
  'campaigns',
  'integrations',
  'ai_config',
  'flow_nodes',
  'sessions',
  'consent_records',
  'users',
]);

export function createDataDeletion({ jsonStorage, postgresPool, auditService }) {
  if (!jsonStorage && !postgresPool) {
    throw new TypeError('jsonStorage or postgresPool is required');
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

  async function deleteTenant(tenantId, options = {}) {
    if (!tenantId || typeof tenantId !== 'string') {
      throw new TypeError('tenantId is required');
    }

    const { confirm = false, types = ['all'], beforeDate = null } = options;

    if (!confirm) {
      throw new Error('Explicit confirmation is required for deletion');
    }

    if (types.includes('audit_events')) {
      throw new Error('Cannot delete audit_events (compliance requirement)');
    }

    const invalidTypes = types.filter(type => !VALID_DELETION_TYPES.has(type));
    if (invalidTypes.length > 0) {
      throw new Error(`Invalid deletion types: ${invalidTypes.join(', ')}`);
    }

    const deletedCounts = {};

    if (jsonStorage) {
      const db = await jsonStorage.read();
      if (types.includes('all') || types.includes('chats')) {
        deletedCounts.chats = Array.isArray(db.chats) ? db.chats.length : 0;
        db.chats = [];
      }
      if (types.includes('all') || types.includes('campaigns')) {
        deletedCounts.campaigns = Array.isArray(db.campaigns) ? db.campaigns.length : 0;
        db.campaigns = [];
      }
      if (types.includes('all') || types.includes('integrations')) {
        deletedCounts.integrations = Array.isArray(db.integrations) ? db.integrations.length : 0;
        db.integrations = [];
      }
      if (types.includes('all') || types.includes('flow_nodes')) {
        deletedCounts.flowNodes = Array.isArray(db.flowNodes) ? db.flowNodes.length : 0;
        db.flowNodes = [];
      }
      if (types.includes('all') || types.includes('ai_config')) {
        deletedCounts.aiConfig = db.aiConfig && typeof db.aiConfig === 'object' && !Array.isArray(db.aiConfig) ? 1 : 0;
        db.aiConfig = {};
      }
      if (Array.isArray(db.contacts) && (types.includes('all') || types.includes('contacts'))) {
        deletedCounts.contacts = db.contacts.length;
        db.contacts = [];
      }
      await jsonStorage.update(current => {
        Object.assign(current, db);
        return current;
      });
    }

    if (postgresPool) {
      const client = await postgresPool.connect();
      try {
        const deleteQueries = [];

        if (types.includes('all') || types.includes('messages')) {
          let sql = 'UPDATE messages SET deleted_at = now() WHERE tenant_id = $1 AND deleted_at IS NULL';
          const params = [tenantId];
          if (beforeDate) {
            sql += ` AND sent_at < $${params.length + 1}`;
            params.push(beforeDate);
          }
          deleteQueries.push({ sql, params, key: 'messages' });
        }

        if (types.includes('all') || types.includes('conversations')) {
          let sql = 'UPDATE conversations SET deleted_at = now() WHERE tenant_id = $1 AND deleted_at IS NULL';
          const params = [tenantId];
          if (beforeDate) {
            sql += ` AND created_at < $${params.length + 1}`;
            params.push(beforeDate);
          }
          deleteQueries.push({ sql, params, key: 'conversations' });
        }

        if (types.includes('all') || types.includes('contacts')) {
          let sql = 'UPDATE contacts SET deleted_at = now() WHERE tenant_id = $1 AND deleted_at IS NULL';
          const params = [tenantId];
          if (beforeDate) {
            sql += ` AND created_at < $${params.length + 1}`;
            params.push(beforeDate);
          }
          deleteQueries.push({ sql, params, key: 'contacts' });
        }

        if (types.includes('all') || types.includes('campaigns')) {
          let sql = 'UPDATE campaigns SET deleted_at = now() WHERE tenant_id = $1 AND deleted_at IS NULL';
          const params = [tenantId];
          if (beforeDate) {
            sql += ` AND created_at < $${params.length + 1}`;
            params.push(beforeDate);
          }
          deleteQueries.push({ sql, params, key: 'campaigns' });
        }

        if (types.includes('all') || types.includes('integrations')) {
          let sql = 'UPDATE integrations SET deleted_at = now() WHERE tenant_id = $1 AND deleted_at IS NULL';
          const params = [tenantId];
          if (beforeDate) {
            sql += ` AND created_at < $${params.length + 1}`;
            params.push(beforeDate);
          }
          deleteQueries.push({ sql, params, key: 'integrations' });
        }

        if (types.includes('all') || types.includes('ai_config')) {
          let sql = 'UPDATE ai_config SET deleted_at = now() WHERE tenant_id = $1 AND deleted_at IS NULL';
          const params = [tenantId];
          if (beforeDate) {
            sql += ` AND created_at < $${params.length + 1}`;
            params.push(beforeDate);
          }
          deleteQueries.push({ sql, params, key: 'aiConfig' });
        }

        if (types.includes('all') || types.includes('flow_nodes')) {
          let sql = 'UPDATE flow_nodes SET deleted_at = now() WHERE tenant_id = $1 AND deleted_at IS NULL';
          const params = [tenantId];
          if (beforeDate) {
            sql += ` AND created_at < $${params.length + 1}`;
            params.push(beforeDate);
          }
          deleteQueries.push({ sql, params, key: 'flowNodes' });
        }

        if (types.includes('all') || types.includes('sessions')) {
          let sql = 'UPDATE sessions SET deleted_at = now() WHERE tenant_id = $1 AND deleted_at IS NULL';
          const params = [tenantId];
          if (beforeDate) {
            sql += ` AND created_at < $${params.length + 1}`;
            params.push(beforeDate);
          }
          deleteQueries.push({ sql, params, key: 'sessions' });
        }

        if (types.includes('all') || types.includes('consent_records')) {
          let sql = 'UPDATE consent_records SET deleted_at = now() WHERE tenant_id = $1 AND deleted_at IS NULL';
          const params = [tenantId];
          if (beforeDate) {
            sql += ` AND recorded_at < $${params.length + 1}`;
            params.push(beforeDate);
          }
          deleteQueries.push({ sql, params, key: 'consentRecords' });
        }

        if (types.includes('all') || types.includes('users')) {
          let sql = 'UPDATE users SET deleted_at = now() WHERE tenant_id = $1 AND deleted_at IS NULL';
          const params = [tenantId];
          if (beforeDate) {
            sql += ` AND created_at < $${params.length + 1}`;
            params.push(beforeDate);
          }
          deleteQueries.push({ sql, params, key: 'users' });
        }

        for (const { sql, params, key } of deleteQueries) {
          const result = await client.query(sql, params);
          deletedCounts[key] = result.rowCount;
        }
      } finally {
        client.release();
      }
    }

    await emitAudit(tenantId, 'privacy.delete', {
      types,
      beforeDate: beforeDate || null,
      counts: deletedCounts,
    });

    return {
      tenantId,
      deletedCounts,
      timestamp: new Date().toISOString(),
    };
  }

  return Object.freeze({ deleteTenant });
}
