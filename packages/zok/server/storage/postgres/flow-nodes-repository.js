const UUID_PATTERN = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;

export function createFlowNodesRepository(tx) {
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
      SELECT id, type, title, description, x, y, details,
        created_at AS "createdAt", updated_at AS "updatedAt"
      FROM flow_nodes
      WHERE deleted_at IS NULL
      ORDER BY created_at ASC, id ASC
    `);
    return result.rows;
  }

  async function replace(nodes = []) {
    if (!Array.isArray(nodes) || nodes.length > 200) {
      throw new TypeError('Nodes must be an array of at most 200 items');
    }
    for (const node of nodes) {
      if (!node || typeof node !== 'object') {
        throw new TypeError('Each node must be an object');
      }
    }

    await tx.query(`DELETE FROM flow_nodes WHERE tenant_id = $1`, [tx.tenantId]);

    const inserted = [];
    for (const node of nodes) {
      const result = await tx.query(`
        INSERT INTO flow_nodes (tenant_id, id, type, title, description, x, y, details)
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8::jsonb)
        RETURNING id, type, title, description, x, y, details,
          created_at AS "createdAt", updated_at AS "updatedAt"
      `, [
        tx.tenantId,
        String(node.id),
        String(node.type),
        String(node.title),
        node.description || null,
        Number(node.x) || 0,
        Number(node.y) || 0,
        JSON.stringify(node.details || {}),
      ]);
      inserted.push(result.rows[0]);
    }
    return inserted;
  }

  return Object.freeze({ list, replace });
}
