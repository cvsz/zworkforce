const UUID_PATTERN = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;
const PERSONAS = new Set(['sales', 'support', 'lead']);

export function createAiConfigRepository(tx) {
  if (
    !tx ||
    typeof tx.query !== 'function' ||
    typeof tx.tenantId !== 'string' ||
    !UUID_PATTERN.test(tx.tenantId)
  ) {
    throw new TypeError('Tenant transaction context is required');
  }

  async function get() {
    const result = await tx.query(`
      SELECT id, agent_name AS "agentName", persona, knowledge_base AS "knowledgeBase",
        qa_pairs AS "qaPairs", created_at AS "createdAt", updated_at AS "updatedAt"
      FROM ai_config
      WHERE tenant_id = $1 AND deleted_at IS NULL
      LIMIT 1
    `, [tx.tenantId]);
    return result.rows[0] || null;
  }

  async function replace(input = {}) {
    const agentName = typeof input.agentName === 'string' ? input.agentName.trim() : '';
    if (!agentName) throw new TypeError('agentName is required');
    if (agentName.length > 120) throw new TypeError('agentName exceeds 120 characters');

    const persona = typeof input.persona === 'string' ? input.persona.trim().toLowerCase() : '';
    if (!PERSONAS.has(persona)) throw new TypeError('persona must be sales, support, or lead');

    const knowledgeBase = typeof input.knowledgeBase === 'string' ? input.knowledgeBase.trim() : '';
    if (!knowledgeBase) throw new TypeError('knowledgeBase is required');
    if (knowledgeBase.length > 10000) throw new TypeError('knowledgeBase exceeds 10000 characters');

    const qaPairs = Array.isArray(input.qaPairs) ? input.qaPairs : [];
    if (qaPairs.length > 100) throw new TypeError('qaPairs must contain at most 100 items');
    const validatedQaPairs = qaPairs.map(pair => {
      if (!pair || typeof pair !== 'object') {
        throw new TypeError('qaPairs must contain valid question/answer pairs');
      }
      const q = typeof pair.q === 'string' ? pair.q.trim() : '';
      const a = typeof pair.a === 'string' ? pair.a.trim() : '';
      if (!q) throw new TypeError('question is required');
      if (q.length > 500) throw new TypeError('question exceeds 500 characters');
      if (!a) throw new TypeError('answer is required');
      if (a.length > 2000) throw new TypeError('answer exceeds 2000 characters');
      return { q, a };
    });

    await tx.query(`DELETE FROM ai_config WHERE tenant_id = $1`, [tx.tenantId]);
    const result = await tx.query(`
      INSERT INTO ai_config (tenant_id, agent_name, persona, knowledge_base, qa_pairs)
      VALUES ($1, $2, $3, $4, $5::jsonb)
      RETURNING id, agent_name AS "agentName", persona, knowledge_base AS "knowledgeBase",
        qa_pairs AS "qaPairs", created_at AS "createdAt", updated_at AS "updatedAt"
    `, [tx.tenantId, agentName, persona, knowledgeBase, JSON.stringify(validatedQaPairs)]);
    return result.rows[0];
  }

  return Object.freeze({ get, replace });
}
