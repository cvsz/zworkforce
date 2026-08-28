import test from 'node:test';
import assert from 'node:assert/strict';
import { createHealthCheck } from '../server/edge/health-check.js';

function createMockPool() {
  const client = {
    async query() {
      return { rowCount: 1 };
    },
    release() {},
  };

  const pool = {
    async connect() {
      return client;
    },
  };

  return { pool, client };
}

function createMockSessionStore() {
  return {
    async get() {
      return null;
    },
  };
}

function createMockRateLimitStore() {
  return {
    async check() {
      return { allowed: true, remaining: 100, retryAfter: 0 };
    },
  };
}

function createMockAuditService() {
  return {
    async emit() {
      return {};
    },
  };
}

function createMockAdapterFactory() {
  return {
    mode: 'simulated',
    async healthChecks() {
      return { whatsapp: 'ok', line: 'ok' };
    },
  };
}

function createMockCampaignWorker() {
  return {
    isHealthy() {
      return true;
    },
    getActiveCount() {
      return 0;
    },
    getQueueDepth() {
      return 0;
    },
  };
}

function createMockJsonStorage() {
  return {
    async read() {
      return { chats: [], flowNodes: [], campaigns: [], integrations: [], syncLogs: [], aiConfig: {} };
    },
  };
}

test('health check liveness returns healthy with all dependencies ok', async () => {
  const healthCheck = createHealthCheck({
    jsonStorage: createMockJsonStorage(),
    postgresPool: createMockPool().pool,
    sessionStore: createMockSessionStore(),
    rateLimitStore: createMockRateLimitStore(),
    auditService: createMockAuditService(),
    adapterFactory: createMockAdapterFactory(),
    campaignWorker: createMockCampaignWorker(),
  });

  const result = await healthCheck.liveness();
  assert.equal(result.status, 'healthy');
  assert.ok(result.checks.database);
  assert.ok(result.checks.postgres);
});

test('health check liveness returns unhealthy when database fails', async () => {
  const badStorage = {
    async read() {
      throw new Error('db read failed');
    },
  };

  const healthCheck = createHealthCheck({
    jsonStorage: badStorage,
  });

  const result = await healthCheck.liveness();
  assert.equal(result.status, 'unhealthy');
  assert.equal(result.checks.database.status, 'error');
});

test('health check readiness returns ready when all dependencies are ok', async () => {
  const healthCheck = createHealthCheck({
    jsonStorage: createMockJsonStorage(),
    postgresPool: createMockPool().pool,
    sessionStore: createMockSessionStore(),
    rateLimitStore: createMockRateLimitStore(),
    auditService: createMockAuditService(),
    adapterFactory: createMockAdapterFactory(),
    campaignWorker: createMockCampaignWorker(),
  });

  const result = await healthCheck.readiness();
  assert.equal(result.status, 'ready');
  assert.equal(result.checks.sessionStore.status, 'ok');
  assert.equal(result.checks.rateLimitStore.status, 'ok');
  assert.equal(result.checks.auditService.status, 'ok');
  assert.equal(result.checks.adapterHealth.status, 'ok');
});

test('health check readiness returns degraded when a non-critical dependency fails', async () => {
  const badRateLimit = {
    async check() {
      throw new Error('rate limit down');
    },
  };

  const healthCheck = createHealthCheck({
    jsonStorage: createMockJsonStorage(),
    postgresPool: createMockPool().pool,
    sessionStore: createMockSessionStore(),
    rateLimitStore: badRateLimit,
    auditService: createMockAuditService(),
    adapterFactory: createMockAdapterFactory(),
    campaignWorker: createMockCampaignWorker(),
  });

  const result = await healthCheck.readiness();
  assert.equal(result.status, 'degraded');
  assert.equal(result.checks.rateLimitStore.status, 'error');
});

test('health check readiness returns not_ready when database fails', async () => {
  const badStorage = {
    async read() {
      throw new Error('db read failed');
    },
  };

  const healthCheck = createHealthCheck({
    jsonStorage: badStorage,
  });

  const result = await healthCheck.readiness();
  assert.equal(result.status, 'not_ready');
  assert.equal(result.checks.database.status, 'error');
});

test('health check returns disabled status for missing optional dependencies', async () => {
  const healthCheck = createHealthCheck({
    jsonStorage: createMockJsonStorage(),
  });

  const result = await healthCheck.readiness();
  assert.equal(result.checks.postgres.status, 'disabled');
  assert.equal(result.checks.sessionStore.status, 'disabled');
  assert.equal(result.checks.auditService.status, 'disabled');
  assert.equal(result.checks.adapterHealth.status, 'disabled');
  assert.equal(result.checks.campaignWorker.status, 'disabled');
});

test('health check includes timestamp in results', async () => {
  const healthCheck = createHealthCheck({
    jsonStorage: createMockJsonStorage(),
  });

  const result = await healthCheck.liveness();
  assert.ok(result.timestamp);
  assert.ok(new Date(result.timestamp).getTime());
});
