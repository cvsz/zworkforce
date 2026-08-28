const inMemoryStore = new Map();

function nowIso() {
  return new Date().toISOString();
}

function generateId() {
  return `rb_${Date.now()}_${Math.random().toString(36).slice(2, 9)}`;
}

async function persistRollbackPostgres(pool, tenantId, flagName, enabled, rollbackPercentage, reason) {
  const client = await pool.connect();
  try {
    await client.query(
      `INSERT INTO feature_flags (tenant_id, flag_name, enabled, rollback_percentage, rollback_reason, rolled_back_at, updated_at)
       VALUES ($1, $2, $3, $4, $5, $6, $7)
       ON CONFLICT (tenant_id, flag_name)
       DO UPDATE SET enabled = $3, rollback_percentage = $4, rollback_reason = $5, rolled_back_at = $6, updated_at = $7`,
      [tenantId, flagName, enabled, rollbackPercentage, reason, nowIso(), nowIso()],
    );
  } finally {
    client.release();
  }
}

async function loadRollbackPostgres(pool, tenantId) {
  const client = await pool.connect();
  try {
    const result = await client.query(
      'SELECT flag_name, enabled, rollback_percentage, rollback_reason, rolled_back_at, updated_at FROM feature_flags WHERE tenant_id = $1',
      [tenantId],
    );
    return result.rows;
  } finally {
    client.release();
  }
}

export function createRollbackManager(options = {}) {
  const pool = options.pool || null;
  const logger = options.logger || null;
  const defaultTenantId = options.tenantId || 'default';

  function logAction(action, details) {
    if (logger && typeof logger.info === 'function') {
      logger.info(action, details);
    }
  }

  async function rollbackFeature(flagName, percentage, reason = 'manual rollback') {
    const boundedPercentage = Math.max(0, Math.min(100, Number(percentage) || 0));
    const enabled = boundedPercentage < 100;

    const record = {
      id: generateId(),
      flagName: String(flagName),
      enabled,
      rollbackPercentage: boundedPercentage,
      reason: String(reason),
      rolledBackAt: nowIso(),
      updatedAt: nowIso(),
      tenantId: defaultTenantId,
    };

    if (pool) {
      try {
        await persistRollbackPostgres(pool, defaultTenantId, flagName, enabled, boundedPercentage, reason);
      } catch (error) {
        inMemoryStore.set(`${defaultTenantId}:${flagName}`, record);
        logAction('rollback-fallback-to-memory', { flagName, error: error.message });
      }
    } else {
      inMemoryStore.set(`${defaultTenantId}:${flagName}`, record);
    }

    logAction('rollback-feature', { flagName, percentage: boundedPercentage, reason, tenantId: defaultTenantId });
    return record;
  }

  async function emergencyRollback(flagName, reason = 'emergency rollback') {
    return rollbackFeature(flagName, 100, reason);
  }

  async function restoreFeature(flagName, reason = 'restored') {
    return rollbackFeature(flagName, 0, reason);
  }

  async function getStatus(flagName) {
    if (pool) {
      try {
        const rows = await loadRollbackPostgres(pool, defaultTenantId);
        const row = rows.find(r => r.flag_name === flagName);
        if (row) {
          return {
            flagName: row.flag_name,
            enabled: row.enabled,
            rollbackPercentage: row.rollback_percentage,
            reason: row.rollback_reason,
            rolledBackAt: row.rolled_back_at,
            updatedAt: row.updated_at,
          };
        }
      } catch {
        // fall through to in-memory
      }
    }

    const record = inMemoryStore.get(`${defaultTenantId}:${flagName}`);
    if (record) {
      return {
        flagName: record.flagName,
        enabled: record.enabled,
        rollbackPercentage: record.rollbackPercentage,
        reason: record.reason,
        rolledBackAt: record.rolledBackAt,
        updatedAt: record.updatedAt,
      };
    }

    return {
      flagName,
      enabled: true,
      rollbackPercentage: 0,
      reason: 'default',
      rolledBackAt: null,
      updatedAt: null,
    };
  }

  async function getAllStatuses() {
    const statuses = new Map();

    if (pool) {
      try {
        const rows = await loadRollbackPostgres(pool, defaultTenantId);
        for (const row of rows) {
          statuses.set(row.flag_name, {
            flagName: row.flag_name,
            enabled: row.enabled,
            rollbackPercentage: row.rollback_percentage,
            reason: row.rollback_reason,
            rolledBackAt: row.rolled_back_at,
            updatedAt: row.updated_at,
          });
        }
      } catch {
        // fall through to in-memory
      }
    }

    for (const [, record] of inMemoryStore.entries()) {
      if (!statuses.has(record.flagName)) {
        statuses.set(record.flagName, {
          flagName: record.flagName,
          enabled: record.enabled,
          rollbackPercentage: record.rollbackPercentage,
          reason: record.reason,
          rolledBackAt: record.rolledBackAt,
          updatedAt: record.updatedAt,
        });
      }
    }

    return Array.from(statuses.values());
  }

  async function isRolledBack(flagName) {
    const status = await getStatus(flagName);
    return !status.enabled || status.rollbackPercentage > 0;
  }

  return Object.freeze({
    rollbackFeature,
    emergencyRollback,
    restoreFeature,
    getStatus,
    getAllStatuses,
    isRolledBack,
  });
}
