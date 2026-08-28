const UUID_PATTERN = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;
const VALID_APPROVAL_STATUSES = new Set(['pending', 'approved', 'rejected', 'auto_approved']);

export function createAiTelemetry(pool) {
  if (!pool || typeof pool.connect !== 'function') {
    throw new TypeError('pg Pool is required');
  }

  async function emit(event = {}) {
    if (!event || typeof event !== 'object') {
      throw new TypeError('telemetry event must be an object');
    }

    const {
      tenantId,
      requestId,
      userId,
      model,
      promptHash,
      responseHash,
      latencyMs,
      tokensUsed,
      approvalStatus = 'approved',
      metadata = {},
    } = event;

    if (!UUID_PATTERN.test(tenantId)) {
      throw new TypeError('tenantId is required and must be a UUID');
    }
    if (!requestId || typeof requestId !== 'string') {
      throw new TypeError('requestId is required');
    }
    if (!userId && userId !== null && userId !== undefined) {
      throw new TypeError('userId must be a UUID or null');
    }
    if (!model || typeof model !== 'string') {
      throw new TypeError('model is required');
    }
    if (!promptHash || typeof promptHash !== 'string') {
      throw new TypeError('promptHash is required');
    }
    if (!responseHash || typeof responseHash !== 'string') {
      throw new TypeError('responseHash is required');
    }
    const parsedLatency = Number(latencyMs);
    if (!Number.isSafeInteger(parsedLatency) || parsedLatency < 0) {
      throw new TypeError('latencyMs must be a non-negative integer');
    }
    const parsedTokens = Number(tokensUsed);
    if (!Number.isSafeInteger(parsedTokens) || parsedTokens < 0) {
      throw new TypeError('tokensUsed must be a non-negative integer');
    }
    const normalizedStatus = typeof approvalStatus === 'string' ? approvalStatus.trim().toLowerCase() : 'approved';
    if (!VALID_APPROVAL_STATUSES.has(normalizedStatus)) {
      throw new TypeError('approvalStatus must be pending, approved, rejected, or auto_approved');
    }

    const client = await pool.connect();
    try {
      const result = await client.query(
        `INSERT INTO ai_telemetry (tenant_id, request_id, user_id, model, prompt_hash, response_hash, latency_ms, tokens_used, approval_status, metadata)
         VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10::jsonb)
         RETURNING id, request_id, model, latency_ms, tokens_used, approval_status, created_at AS "createdAt"`,
        [tenantId, requestId, userId, model, promptHash, responseHash, parsedLatency, parsedTokens, normalizedStatus, JSON.stringify(metadata)],
      );
      return result.rows[0];
    } finally {
      client.release();
    }
  }

  async function list(tenantId, options = {}) {
    if (!UUID_PATTERN.test(tenantId)) {
      throw new TypeError('tenantId is required and must be a UUID');
    }

    const limit = options.limit && Number.isSafeInteger(options.limit) ? Math.min(options.limit, 200) : 50;
    const offset = options.offset && Number.isSafeInteger(options.offset) ? options.offset : 0;

    const conditions = ['tenant_id = $1'];
    const values = [tenantId];

    if (options.requestId) {
      conditions.push(`request_id = $${values.length + 1}`);
      values.push(String(options.requestId));
    }
    if (options.approvalStatus && VALID_APPROVAL_STATUSES.has(options.approvalStatus)) {
      conditions.push(`approval_status = $${values.length + 1}`);
      values.push(options.approvalStatus);
    }
    if (options.model) {
      conditions.push(`model = $${values.length + 1}`);
      values.push(String(options.model));
    }

    const whereClause = conditions.join(' AND ');
    const client = await pool.connect();
    try {
      const result = await client.query(
        `SELECT id, request_id, user_id, model, prompt_hash, response_hash, latency_ms, tokens_used, approval_status, metadata, created_at AS "createdAt"
         FROM ai_telemetry
         WHERE ${whereClause}
         ORDER BY created_at DESC
         LIMIT $${values.length + 1} OFFSET $${values.length + 2}`,
        [...values, limit, offset],
      );
      return result.rows;
    } finally {
      client.release();
    }
  }

  return Object.freeze({ emit, list });
}
