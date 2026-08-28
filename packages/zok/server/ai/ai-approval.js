const UUID_PATTERN = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;

export function createAiApproval(pool, options = {}) {
  if (!pool || typeof pool.connect !== 'function') {
    throw new TypeError('pg Pool is required');
  }

  const defaultTtlMs = options.defaultTtlMs ?? 24 * 60 * 60 * 1000;

  async function create(tenantId, requestId, actionType, riskLevel, payload = {}, ttlMs = defaultTtlMs) {
    if (!UUID_PATTERN.test(tenantId)) {
      throw new TypeError('tenantId is required and must be a UUID');
    }
    if (!requestId || typeof requestId !== 'string') {
      throw new TypeError('requestId is required');
    }
    if (!actionType || typeof actionType !== 'string') {
      throw new TypeError('actionType is required');
    }
    const normalizedRiskLevel = typeof riskLevel === 'string' ? riskLevel.toLowerCase().trim() : 'low';
    if (!['low', 'medium', 'high'].includes(normalizedRiskLevel)) {
      throw new TypeError('riskLevel must be low, medium, or high');
    }

    const safeTtl = Number.isSafeInteger(ttlMs) && ttlMs > 0 ? ttlMs : defaultTtlMs;
    const expiresAt = new Date(Date.now() + safeTtl).toISOString();

    const client = await pool.connect();
    try {
      const result = await client.query(
        `INSERT INTO ai_approvals (tenant_id, request_id, action_type, risk_level, payload, expires_at)
         VALUES ($1, $2, $3, $4, $5::jsonb, $6)
         RETURNING id, request_id, action_type, risk_level, status, payload, expires_at, created_at AS "createdAt"`,
        [tenantId, requestId, actionType, normalizedRiskLevel, JSON.stringify(payload), expiresAt],
      );
      return result.rows[0];
    } finally {
      client.release();
    }
  }

  async function getPending(tenantId) {
    if (!UUID_PATTERN.test(tenantId)) {
      throw new TypeError('tenantId is required and must be a UUID');
    }

    const client = await pool.connect();
    try {
      const result = await client.query(
        `SELECT id, request_id, action_type, risk_level, status, payload, expires_at, created_at AS "createdAt"
         FROM ai_approvals
         WHERE tenant_id = $1 AND status = 'pending' AND expires_at > now()
         ORDER BY created_at DESC`,
        [tenantId],
      );
      return result.rows;
    } finally {
      client.release();
    }
  }

  async function getById(tenantId, approvalId) {
    if (!UUID_PATTERN.test(tenantId)) {
      throw new TypeError('tenantId is required and must be a UUID');
    }
    if (!approvalId || typeof approvalId !== 'string') {
      throw new TypeError('approvalId is required');
    }

    const client = await pool.connect();
    try {
      const result = await client.query(
        `SELECT id, request_id, action_type, risk_level, status, payload, approved_by, approved_at, rejected_by, rejected_at, expires_at, created_at AS "createdAt"
         FROM ai_approvals
         WHERE id = $1 AND tenant_id = $2
         LIMIT 1`,
        [approvalId, tenantId],
      );
      return result.rows[0] || null;
    } finally {
      client.release();
    }
  }

  async function approve(tenantId, approvalId, userId) {
    if (!UUID_PATTERN.test(tenantId)) {
      throw new TypeError('tenantId is required and must be a UUID');
    }
    if (!approvalId || typeof approvalId !== 'string') {
      throw new TypeError('approvalId is required');
    }
    if (!userId || typeof userId !== 'string') {
      throw new TypeError('userId is required');
    }

    const client = await pool.connect();
    try {
      const result = await client.query(
        `UPDATE ai_approvals
         SET status = 'approved', approved_by = $1, approved_at = now()
         WHERE id = $2 AND tenant_id = $3 AND status = 'pending' AND expires_at > now()
         RETURNING id, request_id, action_type, risk_level, status, payload, expires_at, created_at AS "createdAt"`,
        [userId, approvalId, tenantId],
      );
      return result.rows[0] || null;
    } finally {
      client.release();
    }
  }

  async function reject(tenantId, approvalId, userId) {
    if (!UUID_PATTERN.test(tenantId)) {
      throw new TypeError('tenantId is required and must be a UUID');
    }
    if (!approvalId || typeof approvalId !== 'string') {
      throw new TypeError('approvalId is required');
    }
    if (!userId || typeof userId !== 'string') {
      throw new TypeError('userId is required');
    }

    const client = await pool.connect();
    try {
      const result = await client.query(
        `UPDATE ai_approvals
         SET status = 'rejected', rejected_by = $1, rejected_at = now()
         WHERE id = $2 AND tenant_id = $3 AND status = 'pending' AND expires_at > now()
         RETURNING id, request_id, action_type, risk_level, status, payload, expires_at, created_at AS "createdAt"`,
        [userId, approvalId, tenantId],
      );
      return result.rows[0] || null;
    } finally {
      client.release();
    }
  }

  async function expireStale() {
    const client = await pool.connect();
    try {
      const result = await client.query(
        `UPDATE ai_approvals
         SET status = 'expired'
         WHERE status = 'pending' AND expires_at <= now()
         RETURNING id`,
      );
      return result.rowCount;
    } finally {
      client.release();
    }
  }

  return Object.freeze({
    create,
    getPending,
    getById,
    approve,
    reject,
    expireStale,
  });
}
