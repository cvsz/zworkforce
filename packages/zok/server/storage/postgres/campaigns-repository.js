const UUID_PATTERN = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;
const CAMPAIGN_CHANNELS = new Set(['whatsapp', 'line', 'messenger', 'tiktok', 'shopify']);

export function createCampaignsRepository(tx) {
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
      SELECT id, name, status, channel, target, scheduled_at AS "scheduledAt",
        created_at AS "createdAt", updated_at AS "updatedAt"
      FROM campaigns
      WHERE deleted_at IS NULL
      ORDER BY created_at ASC, id ASC
    `);
    return result.rows;
  }

  async function create(input = {}) {
    const name = typeof input.name === 'string' ? input.name.trim() : '';
    if (!name) throw new TypeError('Campaign name is required');
    if (name.length > 160) throw new TypeError('Campaign name exceeds 160 characters');

    const target = typeof input.target === 'string' ? input.target.trim() : '';
    if (!target) throw new TypeError('Campaign target is required');
    if (target.length > 120) throw new TypeError('Campaign target exceeds 120 characters');

    const channel = typeof input.channel === 'string' ? input.channel.trim().toLowerCase() : '';
    if (!CAMPAIGN_CHANNELS.has(channel)) {
      throw new TypeError('Invalid campaign channel');
    }

    const result = await tx.query(`
      INSERT INTO campaigns (tenant_id, name, channel, target)
      VALUES ($1, $2, $3, $4::jsonb)
      RETURNING id, name, status, channel, target, scheduled_at AS "scheduledAt",
        created_at AS "createdAt", updated_at AS "updatedAt"
    `, [tx.tenantId, name, channel, JSON.stringify(target)]);
    return result.rows[0];
  }

  async function updateStatus(id, status) {
    const result = await tx.query(`
      UPDATE campaigns
      SET status = $2, updated_at = now()
      WHERE id = $1 AND tenant_id = $3 AND deleted_at IS NULL
      RETURNING id, name, status, channel, target, scheduled_at AS "scheduledAt",
        created_at AS "createdAt", updated_at AS "updatedAt"
    `, [id, status, tx.tenantId]);
    return result.rows[0] || null;
  }

  return Object.freeze({ list, create, updateStatus });
}
