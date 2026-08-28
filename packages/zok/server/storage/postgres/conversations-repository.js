const UUID_PATTERN = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;
const CHANNELS = new Set(['line', 'whatsapp', 'messenger', 'tiktok', 'shopify']);
const DIRECTIONS = new Set(['inbound', 'outbound']);
const SENDERS = new Set(['customer', 'agent', 'system', 'ai']);

export function createConversationsRepository(tx) {
  if (
    !tx ||
    typeof tx.query !== 'function' ||
    typeof tx.tenantId !== 'string' ||
    !UUID_PATTERN.test(tx.tenantId)
  ) {
    throw new TypeError('Tenant transaction context is required');
  }

  async function create(input = {}) {
    if (typeof input.contactId !== 'string' || !UUID_PATTERN.test(input.contactId)) {
      throw new TypeError('Valid contact id is required');
    }
    if (typeof input.channel !== 'string' || !CHANNELS.has(input.channel)) {
      throw new TypeError('Supported channel is required');
    }
    const externalThreadId = typeof input.externalThreadId === 'string' && input.externalThreadId.trim()
      ? input.externalThreadId.trim().slice(0, 255)
      : null;

    const result = await tx.query(`
      INSERT INTO conversations (tenant_id, contact_id, channel, external_thread_id)
      VALUES ($1, $2, $3, $4)
      RETURNING id, contact_id AS "contactId", channel, external_thread_id AS "externalThreadId", status,
        created_at AS "createdAt", updated_at AS "updatedAt"
    `, [tx.tenantId, input.contactId, input.channel, externalThreadId]);
    return result.rows[0];
  }

  async function addMessage(conversationId, input = {}) {
    if (typeof conversationId !== 'string' || !UUID_PATTERN.test(conversationId)) {
      throw new TypeError('Valid conversation id is required');
    }
    if (typeof input.direction !== 'string' || !DIRECTIONS.has(input.direction)) {
      throw new TypeError('Valid message direction is required');
    }
    if (typeof input.senderType !== 'string' || !SENDERS.has(input.senderType)) {
      throw new TypeError('Valid sender type is required');
    }
    const body = typeof input.body === 'string' ? input.body.trim() : '';
    if (!body) throw new TypeError('Message body is required');
    if (body.length > 20_000) throw new TypeError('Message body exceeds 20000 characters');
    const externalMessageId = typeof input.externalMessageId === 'string' && input.externalMessageId.trim()
      ? input.externalMessageId.trim().slice(0, 255)
      : null;
    const metadata = input.metadata && typeof input.metadata === 'object' && !Array.isArray(input.metadata)
      ? input.metadata
      : {};

    const result = await tx.query(`
      INSERT INTO messages (tenant_id, conversation_id, direction, sender_type, body, external_message_id, metadata)
      VALUES ($1, $2, $3, $4, $5, $6, $7::jsonb)
      RETURNING id, conversation_id AS "conversationId", direction, sender_type AS "senderType",
        body, external_message_id AS "externalMessageId", metadata, sent_at AS "sentAt"
    `, [tx.tenantId, conversationId, input.direction, input.senderType, body, externalMessageId, JSON.stringify(metadata)]);
    return result.rows[0];
  }

  async function list() {
    const result = await tx.query(`
      SELECT c.id, c.contact_id AS "contactId", c.channel, c.external_thread_id AS "externalThreadId",
        c.status, c.created_at AS "createdAt", c.updated_at AS "updatedAt"
      FROM conversations c
      WHERE c.deleted_at IS NULL
      ORDER BY c.updated_at DESC, c.id ASC
    `);
    return result.rows;
  }

  async function findByExternalThreadId(externalThreadId) {
    if (typeof externalThreadId !== 'string' || !externalThreadId.trim()) {
      throw new TypeError('External thread id is required');
    }
    const normalizedExternalThreadId = externalThreadId.trim();
    if (normalizedExternalThreadId.length > 255) {
      throw new TypeError('External thread id exceeds 255 characters');
    }

    const result = await tx.query(`
      SELECT c.id, c.contact_id AS "contactId", c.channel, c.external_thread_id AS "externalThreadId",
        c.status, c.created_at AS "createdAt", c.updated_at AS "updatedAt"
      FROM conversations c
      WHERE c.external_thread_id = $1 AND c.deleted_at IS NULL
      LIMIT 1
    `, [normalizedExternalThreadId]);
    return result.rows[0] || null;
  }

  async function listMessages(conversationId) {
    if (typeof conversationId !== 'string' || !UUID_PATTERN.test(conversationId)) {
      throw new TypeError('Valid conversation id is required');
    }

    const result = await tx.query(`
      SELECT m.id, m.conversation_id AS "conversationId", m.direction, m.sender_type AS "senderType",
        m.body, m.external_message_id AS "externalMessageId", m.metadata, m.sent_at AS "sentAt"
      FROM messages m
      WHERE m.conversation_id = $1 AND m.deleted_at IS NULL
      ORDER BY m.sent_at ASC, m.id ASC
    `, [conversationId]);
    return result.rows;
  }

  return Object.freeze({ create, addMessage, list, findByExternalThreadId, listMessages });
}
