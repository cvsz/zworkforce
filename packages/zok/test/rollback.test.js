import test from 'node:test';
import assert from 'node:assert/strict';
import { createRollbackManager } from '../server/edge/rollback.js';

function createMockPool() {
  const store = new Map();

  const client = {
    async query(text, values = []) {
      if (text.includes('INSERT INTO feature_flags') && text.includes('ON CONFLICT')) {
        const key = `${values[0]}:${values[1]}`;
        store.set(key, {
          tenant_id: values[0],
          flag_name: values[1],
          enabled: values[2],
          rollback_percentage: values[3],
          rollback_reason: values[4],
          rolled_back_at: values[5],
          updated_at: values[6],
        });
        return { rowCount: 1 };
      }
      if (text.includes('SELECT') && text.includes('feature_flags')) {
        const rows = Array.from(store.values());
        return { rows, rowCount: rows.length };
      }
      return { rows: [], rowCount: 0 };
    },
    release() {},
  };

  const pool = {
    async connect() {
      return client;
    },
  };

  return { pool, client, store };
}

function createMockLogger() {
  return {
    info() {
      // noop
    },
  };
}

test('rollback manager creates a rollback record', async () => {
  const { pool } = createMockPool();
  const manager = createRollbackManager({ pool, logger: createMockLogger(), tenantId: 'tenant-1' });

  const record = await manager.rollbackFeature('new-checkout', 50, 'performance issue');
  assert.equal(record.flagName, 'new-checkout');
  assert.equal(record.enabled, true);
  assert.equal(record.rollbackPercentage, 50);
  assert.equal(record.reason, 'performance issue');
  assert.ok(record.id);
  assert.ok(record.rolledBackAt);
  assert.equal(record.tenantId, 'tenant-1');
});

test('rollback manager supports percentage-based rollback', async () => {
  const manager = createRollbackManager({ logger: createMockLogger() });

  await manager.rollbackFeature('feature-a', 25, 'testing');
  const status = await manager.getStatus('feature-a');
  assert.equal(status.rollbackPercentage, 25);
  assert.equal(status.enabled, true);
});

test('rollback manager clamps percentage between 0 and 100', async () => {
  const manager = createRollbackManager({ logger: createMockLogger() });

  const record = await manager.rollbackFeature('feature-a', -10, 'bad input');
  assert.equal(record.rollbackPercentage, 0);

  const record2 = await manager.rollbackFeature('feature-a', 150, 'bad input');
  assert.equal(record2.rollbackPercentage, 100);
});

test('rollback manager emergency rollback disables the feature', async () => {
  const manager = createRollbackManager({ logger: createMockLogger() });

  const record = await manager.emergencyRollback('critical-feature', 'outage');
  assert.equal(record.enabled, false);
  assert.equal(record.rollbackPercentage, 100);
  assert.equal(record.reason, 'outage');
});

test('rollback manager restore feature re-enables the flag', async () => {
  const manager = createRollbackManager({ logger: createMockLogger() });

  await manager.emergencyRollback('feature-x', 'outage');
  const afterEmergency = await manager.getStatus('feature-x');
  assert.equal(afterEmergency.enabled, false);

  await manager.restoreFeature('feature-x', 'fixed');
  const afterRestore = await manager.getStatus('feature-x');
  assert.equal(afterRestore.enabled, true);
  assert.equal(afterRestore.rollbackPercentage, 0);
  assert.equal(afterRestore.reason, 'fixed');
});

test('rollback manager returns default status for unknown flag', async () => {
  const manager = createRollbackManager({ logger: createMockLogger() });

  const status = await manager.getStatus('unknown-flag');
  assert.equal(status.flagName, 'unknown-flag');
  assert.equal(status.enabled, true);
  assert.equal(status.rollbackPercentage, 0);
  assert.equal(status.reason, 'default');
});

test('rollback manager getAllStatuses returns all recorded flags', async () => {
  const manager = createRollbackManager({ logger: createMockLogger() });

  await manager.rollbackFeature('flag-1', 10, 'test');
  await manager.rollbackFeature('flag-2', 100, 'test');

  const statuses = await manager.getAllStatuses();
  assert.ok(statuses.length >= 2, 'expected at least 2 statuses');
  assert.ok(statuses.some(s => s.flagName === 'flag-1'));
  assert.ok(statuses.some(s => s.flagName === 'flag-2'));
});

test('rollback manager persists to postgres when pool is provided', async () => {
  const { pool, store } = createMockPool();
  const manager = createRollbackManager({ pool, logger: createMockLogger(), tenantId: 'tenant-1' });

  await manager.rollbackFeature('db-flag', 30, 'db test');
  assert.equal(store.size, 1);
  assert.equal(store.get('tenant-1:db-flag').flag_name, 'db-flag');
});

test('rollback manager falls back to memory when postgres fails', async () => {
  const badPool = {
    async connect() {
      throw new Error('db down');
    },
  };

  const manager = createRollbackManager({ pool: badPool, logger: createMockLogger() });
  const record = await manager.rollbackFeature('fallback-flag', 20, 'memory test');
  assert.equal(record.flagName, 'fallback-flag');
  const status = await manager.getStatus('fallback-flag');
  assert.equal(status.rollbackPercentage, 20);
});

test('rollback manager isRolledBack returns true for rolled back features', async () => {
  const manager = createRollbackManager({ logger: createMockLogger() });

  assert.ok(!(await manager.isRolledBack('active-feature')));

  await manager.emergencyRollback('broken-feature', 'outage');
  assert.ok(await manager.isRolledBack('broken-feature'));

  await manager.rollbackFeature('partial-feature', 50, 'test');
  assert.ok(await manager.isRolledBack('partial-feature'));
});
