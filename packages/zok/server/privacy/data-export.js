import ADMZip from 'adm-zip';
import { randomUUID } from 'node:crypto';

export function createDataExport({ jsonStorage, postgresPool, auditService }) {
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

  async function exportTenant(tenantId) {
    if (!tenantId || typeof tenantId !== 'string') {
      throw new TypeError('tenantId is required');
    }

    let exportData;

    if (jsonStorage) {
      const db = await jsonStorage.read();
      exportData = {
        exportedAt: new Date().toISOString(),
        tenantId,
        chats: Array.isArray(db.chats) ? db.chats : [],
        campaigns: Array.isArray(db.campaigns) ? db.campaigns : [],
        integrations: Array.isArray(db.integrations) ? db.integrations : [],
        aiConfig: db.aiConfig && typeof db.aiConfig === 'object' && !Array.isArray(db.aiConfig) ? db.aiConfig : {},
        flowNodes: Array.isArray(db.flowNodes) ? db.flowNodes : [],
        contacts: Array.isArray(db.contacts) ? db.contacts : [],
      };
    } else if (postgresPool) {
      const client = await postgresPool.connect();
      try {
        const [
          contacts,
          conversations,
          messages,
          campaigns,
          integrations,
          aiConfig,
          flowNodes,
        ] = await Promise.all([
          client.query('SELECT * FROM contacts WHERE tenant_id = $1 AND deleted_at IS NULL ORDER BY created_at ASC, id ASC', [tenantId]),
          client.query('SELECT * FROM conversations WHERE tenant_id = $1 AND deleted_at IS NULL ORDER BY created_at ASC, id ASC', [tenantId]),
          client.query('SELECT * FROM messages WHERE tenant_id = $1 AND deleted_at IS NULL ORDER BY sent_at ASC, id ASC', [tenantId]),
          client.query('SELECT * FROM campaigns WHERE tenant_id = $1 AND deleted_at IS NULL ORDER BY created_at ASC, id ASC', [tenantId]),
          client.query('SELECT * FROM integrations WHERE tenant_id = $1 AND deleted_at IS NULL ORDER BY created_at ASC, id ASC', [tenantId]),
          client.query('SELECT * FROM ai_config WHERE tenant_id = $1 AND deleted_at IS NULL LIMIT 1', [tenantId]),
          client.query('SELECT * FROM flow_nodes WHERE tenant_id = $1 AND deleted_at IS NULL ORDER BY created_at ASC, id ASC', [tenantId]),
        ]);

        exportData = {
          exportedAt: new Date().toISOString(),
          tenantId,
          contacts: contacts.rows,
          conversations: conversations.rows,
          messages: messages.rows,
          campaigns: campaigns.rows,
          integrations: integrations.rows,
          aiConfig: aiConfig.rows[0] || null,
          flowNodes: flowNodes.rows,
        };
      } finally {
        client.release();
      }
    }

    const jsonContent = JSON.stringify(exportData, null, 2);
    const zip = new ADMZip();
    zip.addFile('export.json', Buffer.from(jsonContent, 'utf-8'));
    const buffer = zip.toBuffer();

    const recordCount = {
      chats: Array.isArray(exportData.chats) ? exportData.chats.length : 0,
      messages: (Array.isArray(exportData.messages) ? exportData.messages.length : 0)
        + (Array.isArray(exportData.chats)
          ? exportData.chats.reduce((sum, chat) => sum + (Array.isArray(chat.messages) ? chat.messages.length : 0), 0)
          : 0),
      contacts: Array.isArray(exportData.contacts) ? exportData.contacts.length : 0,
      conversations: Array.isArray(exportData.conversations) ? exportData.conversations.length : 0,
      campaigns: Array.isArray(exportData.campaigns) ? exportData.campaigns.length : 0,
      integrations: Array.isArray(exportData.integrations) ? exportData.integrations.length : 0,
      aiConfig: exportData.aiConfig ? 1 : 0,
      flowNodes: Array.isArray(exportData.flowNodes) ? exportData.flowNodes.length : 0,
    };

    await emitAudit(tenantId, 'privacy.export', {
      recordCount,
      sizeBytes: buffer.length,
    });

    return {
      buffer,
      filename: `zok-export-${tenantId}-${new Date().toISOString().split('T')[0]}.zip`,
      contentType: 'application/zip',
      recordCount,
    };
  }

  return Object.freeze({ exportTenant });
}
