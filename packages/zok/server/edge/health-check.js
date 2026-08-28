export function createHealthCheck(dependencies = {}) {
  const {
    jsonStorage = null,
    postgresPool = null,
    sessionStore = null,
    rateLimitStore = null,
    auditService = null,
    adapterFactory = null,
    campaignWorker = null,
  } = dependencies;

  async function checkDatabase() {
    if (!jsonStorage) {
      return { status: 'disabled', latencyMs: 0 };
    }

    const start = Date.now();
    try {
      await jsonStorage.read();
      return { status: 'ok', latencyMs: Date.now() - start };
    } catch (error) {
      return { status: 'error', error: error.message, latencyMs: Date.now() - start };
    }
  }

  async function checkPostgres() {
    if (!postgresPool) {
      return { status: 'disabled' };
    }

    const start = Date.now();
    try {
      const client = await postgresPool.connect();
      try {
        await client.query('SELECT 1');
        return { status: 'ok', latencyMs: Date.now() - start };
      } finally {
        client.release();
      }
    } catch (error) {
      return { status: 'error', error: error.message, latencyMs: Date.now() - start };
    }
  }

  async function checkSessionStore() {
    if (!sessionStore) {
      return { status: 'disabled' };
    }

    const start = Date.now();
    try {
      await sessionStore.get('__health_check__');
      return { status: 'ok', latencyMs: Date.now() - start };
    } catch (error) {
      return { status: 'error', error: error.message, latencyMs: Date.now() - start };
    }
  }

  async function checkRateLimitStore() {
    if (!rateLimitStore) {
      return { status: 'disabled' };
    }

    const start = Date.now();
    try {
      await rateLimitStore.check('__health__', 1000, 1);
      return { status: 'ok', latencyMs: Date.now() - start };
    } catch (error) {
      return { status: 'error', error: error.message, latencyMs: Date.now() - start };
    }
  }

  async function checkAuditService() {
    if (!auditService) {
      return { status: 'disabled' };
    }

    const start = Date.now();
    try {
      await auditService.emit({
        tenant_id: null,
        actor_user_id: null,
        action: 'health.check',
        resource_type: 'health',
        resource_id: null,
        request_id: 'health-check',
        occurred_at: new Date().toISOString(),
        metadata: { source: 'health-check' },
      });
      return { status: 'ok', latencyMs: Date.now() - start };
    } catch (error) {
      return { status: 'error', error: error.message, latencyMs: Date.now() - start };
    }
  }

  async function checkAdapterHealth() {
    if (!adapterFactory) {
      return { status: 'disabled' };
    }

    const start = Date.now();
    try {
      const health = await adapterFactory.healthChecks();
      return { status: 'ok', details: health, latencyMs: Date.now() - start };
    } catch (error) {
      return { status: 'error', error: error.message, latencyMs: Date.now() - start };
    }
  }

  async function checkCampaignWorker() {
    if (!campaignWorker) {
      return { status: 'disabled' };
    }

    return {
      status: campaignWorker.isHealthy() ? 'ok' : 'unhealthy',
      activeWorkers: campaignWorker.getActiveCount(),
      queueDepth: campaignWorker.getQueueDepth(),
    };
  }

  async function liveness() {
    const checks = {
      timestamp: new Date().toISOString(),
      checks: {
        database: await checkDatabase(),
        postgres: await checkPostgres(),
      },
    };

    const hasError = Object.values(checks.checks).some(
      check => check.status === 'error'
    );

    return {
      status: hasError ? 'unhealthy' : 'healthy',
      ...checks,
    };
  }

  async function readiness() {
    const checks = {
      timestamp: new Date().toISOString(),
      checks: {
        database: await checkDatabase(),
        postgres: await checkPostgres(),
        sessionStore: await checkSessionStore(),
        rateLimitStore: await checkRateLimitStore(),
        auditService: await checkAuditService(),
        adapterHealth: await checkAdapterHealth(),
        campaignWorker: await checkCampaignWorker(),
      },
    };

    const requiredChecks = ['database', 'postgres'];
    const hasRequiredError = requiredChecks.some(
      name => checks.checks[name]?.status === 'error'
    );

    if (hasRequiredError) {
      return { status: 'not_ready', ...checks };
    }

    const hasDegraded = Object.values(checks.checks).some(
      check => check.status === 'error'
    );

    return {
      status: hasDegraded ? 'degraded' : 'ready',
      ...checks,
    };
  }

  return Object.freeze({
    liveness,
    readiness,
  });
}
