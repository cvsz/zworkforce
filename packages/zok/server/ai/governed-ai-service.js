const UUID_PATTERN = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;

const AI_CONFIG_SCHEMA = Object.freeze({
  model: { type: 'string', required: true, maxLength: 120 },
  temperature: { type: 'number', required: true, min: 0, max: 2 },
  max_tokens: { type: 'integer', required: true, min: 1, max: 100000 },
  system_prompt: { type: 'string', required: true, maxLength: 8000 },
});

const VALID_RISK_LEVELS = new Set(['low', 'medium', 'high']);

function hashString(value) {
  if (typeof value !== 'string') return 'unknown';
  let hash = 0;
  for (let i = 0; i < value.length; i += 1) {
    const char = value.charCodeAt(i);
    hash = ((hash << 5) - hash) + char;
    hash = Math.trunc(hash);
  }
  return Math.abs(hash).toString(16).padStart(8, '0');
}

export function createGovernedAIService({ telemetry, approval, pool } = {}) {
  if (!telemetry || typeof telemetry.emit !== 'function') {
    throw new TypeError('telemetry service with emit() is required');
  }
  if (!approval || typeof approval.create !== 'function') {
    throw new TypeError('approval service with create() is required');
  }

  async function validateConfig(config = {}) {
    if (!config || typeof config !== 'object' || Array.isArray(config)) {
      throw new TypeError('AI config must be a non-null object');
    }

    const errors = [];
    for (const [field, rules] of Object.entries(AI_CONFIG_SCHEMA)) {
      const value = config[field];
      if (rules.required && (value === undefined || value === null || value === '')) {
        errors.push(`${field} is required`);
        continue;
      }
      if (value === undefined || value === null) continue;

      if (rules.type === 'string') {
        if (typeof value !== 'string') {
          errors.push(`${field} must be a string`);
          continue;
        }
        if (rules.maxLength && value.length > rules.maxLength) {
          errors.push(`${field} exceeds the ${rules.maxLength}-character limit`);
        }
      }

      if (rules.type === 'number' || rules.type === 'integer') {
        const num = Number(value);
        if (!Number.isFinite(num)) {
          errors.push(`${field} must be a ${rules.type}`);
          continue;
        }
        if (rules.type === 'integer' && !Number.isSafeInteger(num)) {
          errors.push(`${field} must be an integer`);
          continue;
        }
        if (rules.min !== undefined && num < rules.min) {
          errors.push(`${field} must be at least ${rules.min}`);
        }
        if (rules.max !== undefined && num > rules.max) {
          errors.push(`${field} must be at most ${rules.max}`);
        }
      }
    }

    if (errors.length > 0) {
      const error = new TypeError(errors.join('; '));
      error.status = 400;
      error.errors = errors;
      throw error;
    }

    return true;
  }

  async function getActiveConfig(tenantId) {
    if (!UUID_PATTERN.test(tenantId)) {
      throw new TypeError('tenantId is required and must be a UUID');
    }
    if (!pool || typeof pool.connect !== 'function') {
      throw new TypeError('pg Pool is required');
    }

    const client = await pool.connect();
    try {
      const result = await client.query(
        `SELECT id, version, config, risk_level, created_at AS "createdAt"
         FROM ai_config_versions
         WHERE tenant_id = $1
         ORDER BY version DESC
         LIMIT 1`,
        [tenantId],
      );
      return result.rows[0] || null;
    } finally {
      client.release();
    }
  }

  async function setConfig(tenantId, config, riskLevel = 'low') {
    if (!UUID_PATTERN.test(tenantId)) {
      throw new TypeError('tenantId is required and must be a UUID');
    }
    if (!pool || typeof pool.connect !== 'function') {
      throw new TypeError('pg Pool is required');
    }

    await validateConfig(config);

    const normalizedRiskLevel = typeof riskLevel === 'string' ? riskLevel.toLowerCase().trim() : 'low';
    if (!VALID_RISK_LEVELS.has(normalizedRiskLevel)) {
      throw new TypeError('risk_level must be low, medium, or high');
    }

    const client = await pool.connect();
    try {
      await client.query('BEGIN');

      const versionResult = await client.query(
        'SELECT COALESCE(MAX(version), 0) + 1 AS next_version FROM ai_config_versions WHERE tenant_id = $1',
        [tenantId],
      );
      const nextVersion = versionResult.rows[0].next_version;

      const result = await client.query(
        `INSERT INTO ai_config_versions (tenant_id, version, config, risk_level)
         VALUES ($1, $2, $3::jsonb, $4)
         RETURNING id, version, config, risk_level, created_at AS "createdAt"`,
        [tenantId, nextVersion, JSON.stringify(config), normalizedRiskLevel],
      );

      await client.query('COMMIT');
      return result.rows[0];
    } catch (error) {
      await client.query('ROLLBACK').catch(() => undefined);
      throw error;
    } finally {
      client.release();
    }
  }

  async function chat(tenantId, userId, messages, options = {}) {
    if (!UUID_PATTERN.test(tenantId)) {
      throw new TypeError('tenantId is required and must be a UUID');
    }
    if (!userId || typeof userId !== 'string') {
      throw new TypeError('userId is required');
    }
    if (!Array.isArray(messages) || messages.length === 0) {
      throw new TypeError('messages must be a non-empty array');
    }

    const startTime = Date.now();
    const requestId = options.requestId || `req-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;

    const activeConfig = await getActiveConfig(tenantId);
    if (!activeConfig) {
      throw new TypeError('No active AI configuration found');
    }

    const config = activeConfig.config;
    const riskLevel = activeConfig.risk_level || 'low';
    const model = config.model || 'zok-local-simulator';
    const systemPrompt = config.system_prompt || '';
    const promptHash = hashString(JSON.stringify(messages) + systemPrompt);

    let approvalStatus = 'auto_approved';
    let responseText = '';
    let tokensUsed = 0;

    if (riskLevel === 'high' && !options.skipGovernance) {
      approvalStatus = 'pending';
      const approvalId = await approval.create(tenantId, requestId, 'ai_chat', riskLevel, {
        messages,
        model,
        temperature: config.temperature,
        max_tokens: config.max_tokens,
      });

      return {
        status: 'approval_required',
        requestId,
        approvalId,
        riskLevel,
        message: 'High-risk AI action requires approval before execution',
        metadata: {
          model,
          latencyMs: Date.now() - startTime,
          tokensUsed: 0,
          approvalStatus,
          configVersion: activeConfig.version,
        },
      };
    }

    const lastMessage = messages[messages.length - 1]?.content || '';
    const lowerMessage = lastMessage.toLowerCase();
    if (lowerMessage.includes('order') || lowerMessage.includes('track')) {
      responseText = 'You can track all active orders directly in your customer profile page, or click: shopify.com/orders';
    } else if (lowerMessage.includes('price') || lowerMessage.includes('cost')) {
      responseText = 'Our standard pricing starts at $45/month (Basic) up to $97/month (Pro). Let us know if you\'d like a custom demo.';
    } else if (lowerMessage.includes('help') || lowerMessage.includes('support')) {
      responseText = 'Got it. I\'ve routed this conversation to our priority support desk. Alex Rivera will review this shortly!';
    } else {
      responseText = `Hi, thank you for your message! Our team will get back to you shortly.`;
    }

    tokensUsed = Math.max(1, Math.round(lastMessage.length / 4) + Math.round(responseText.length / 4));
    const latencyMs = Date.now() - startTime;
    const responseHash = hashString(responseText);

    telemetry.emit({
      tenantId,
      requestId,
      userId,
      model,
      promptHash,
      responseHash,
      latencyMs,
      tokensUsed,
      approvalStatus,
      metadata: {
        riskLevel,
        configVersion: activeConfig.version,
        messageCount: messages.length,
      },
    }).catch(() => {});

    return {
      status: 'completed',
      requestId,
      content: responseText,
      metadata: {
        model,
        latencyMs,
        tokensUsed,
        approvalStatus,
        riskLevel,
        configVersion: activeConfig.version,
        promptHash,
        responseHash,
      },
    };
  }

  async function getApprovals(tenantId) {
    if (!UUID_PATTERN.test(tenantId)) {
      throw new TypeError('tenantId is required and must be a UUID');
    }
    return approval.getPending(tenantId);
  }

  async function approveApproval(tenantId, approvalId, userId) {
    if (!UUID_PATTERN.test(tenantId)) {
      throw new TypeError('tenantId is required and must be a UUID');
    }
    if (!approvalId || typeof approvalId !== 'string') {
      throw new TypeError('approvalId is required');
    }
    if (!userId || typeof userId !== 'string') {
      throw new TypeError('userId is required');
    }
    return approval.approve(tenantId, approvalId, userId);
  }

  async function rejectApproval(tenantId, approvalId, userId) {
    if (!UUID_PATTERN.test(tenantId)) {
      throw new TypeError('tenantId is required and must be a UUID');
    }
    if (!approvalId || typeof approvalId !== 'string') {
      throw new TypeError('approvalId is required');
    }
    if (!userId || typeof userId !== 'string') {
      throw new TypeError('userId is required');
    }
    return approval.reject(tenantId, approvalId, userId);
  }

  async function getTelemetry(tenantId, options = {}) {
    if (!UUID_PATTERN.test(tenantId)) {
      throw new TypeError('tenantId is required and must be a UUID');
    }
    if (!telemetry.list) {
      throw new TypeError('telemetry list() is not supported');
    }
    return telemetry.list(tenantId, options);
  }

  return Object.freeze({
    validateConfig,
    getActiveConfig,
    setConfig,
    chat,
    getApprovals,
    approveApproval,
    rejectApproval,
    getTelemetry,
  });
}
