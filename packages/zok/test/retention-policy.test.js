import test from 'node:test';
import assert from 'node:assert/strict';
import { createRetentionPolicy } from '../server/privacy/retention-policy.js';

function createFakePool(countsByTable = {}) {
  const clients = [];
  const client = {
    async query(text, values) {
      clients.push({ text, values });
      const tableMatch = text.match(/from (\w+)/i);
      const table = tableMatch ? tableMatch[1].toLowerCase() : null;
      const isCount = text.trim().toLowerCase().startsWith('select count');
      if (isCount) {
        return { rows: [{ count: countsByTable[table] || 0 }] };
      }
      if (text.trim().toLowerCase().startsWith('delete')) {
        return { rowCount: countsByTable[table] || 0 };
      }
      return { rows: [] };
    },
    release() {},
  };

  return {
    pool: {
      async connect() { return client; },
    },
    clients,
  };
}

test('createRetentionPolicy requires postgresPool', () => {
  assert.throws(() => createRetentionPolicy({}), /postgresPool is required/);
});

test('getRetentionStatus validates tenantId', async () => {
  const policy = createRetentionPolicy({ postgresPool: createFakePool() });
  await assert.rejects(() => policy.getRetentionStatus(null), /tenantId is required/);
  await assert.rejects(() => policy.getRetentionStatus(''), /tenantId is required/);
});

test('getRetentionStatus returns default policies and counts', async () => {
  const fake = createFakePool({
    messages: 10,
    conversations: 5,
    contacts: 20,
    campaigns: 3,
    integrations: 2,
    ai_config: 1,
    flow_nodes: 15,
    sessions: 8,
    consent_records: 4,
    users: 2,
    audit_events: 50,
  });

  const policy = createRetentionPolicy({ postgresPool: fake.pool });
  const status = await policy.getRetentionStatus('tenant-1');

  assert.equal(status.tenantId, 'tenant-1');
  assert.ok(status.generatedAt);
  assert.equal(status.policies.messages, 90);
  assert.equal(status.policies.conversations, 180);
  assert.equal(status.policies.contacts, 365);
  assert.equal(status.status.messages.total, 10);
  assert.equal(status.status.conversations.total, 5);
  assert.equal(status.status.auditEvents.total, 50);
  assert.equal(status.status.auditEvents.retentionDays, 'infinite');
  assert.equal(status.status.auditEvents.immutable, true);
});

test('getDefaultRetention returns configured periods', async () => {
  const policy = createRetentionPolicy({ postgresPool: createFakePool() });
  assert.equal(policy.getDefaultRetention('messages'), 90);
  assert.equal(policy.getDefaultRetention('conversations'), 180);
  assert.equal(policy.getDefaultRetention('contacts'), 365);
  assert.equal(policy.getDefaultRetention('unknown_type'), 365);
});

test('purgeExpired validates tenantId', async () => {
  const policy = createRetentionPolicy({ postgresPool: createFakePool() });
  await assert.rejects(() => policy.purgeExpired(null), /tenantId is required/);
  await assert.rejects(() => policy.purgeExpired(''), /tenantId is required/);
});

test('purgeExpired deletes soft-deleted rows older than retention period', async () => {
  const fake = createFakePool({
    messages: 3,
    conversations: 1,
    contacts: 0,
    campaigns: 0,
    integrations: 0,
    ai_config: 0,
    flow_nodes: 0,
    sessions: 0,
    consent_records: 0,
    users: 0,
  });

  const auditCalls = [];
  const auditService = {
    async emit(event) { auditCalls.push(event); },
  };

  const policy = createRetentionPolicy({ postgresPool: fake.pool, auditService });
  const result = await policy.purgeExpired('tenant-1');

  assert.equal(result.tenantId, 'tenant-1');
  assert.ok(result.timestamp);
  assert.equal(result.purged.messages, 3);
  assert.equal(result.purged.conversations, 1);
  assert.equal(auditCalls.length, 1);
  assert.equal(auditCalls[0].action, 'privacy.retention_purge');
});

test('purgeExpired respects custom retention periods', async () => {
  const fake = createFakePool({
    messages: 0,
    conversations: 0,
    contacts: 0,
    campaigns: 0,
    integrations: 0,
    ai_config: 0,
    flow_nodes: 0,
    sessions: 0,
    consent_records: 0,
    users: 0,
  });

  const policy = createRetentionPolicy({ postgresPool: fake.pool });
  await policy.purgeExpired('tenant-1', { messages: 60, contacts: 180 });

  assert.ok(fake.clients.some(call => call.values.includes(60)));
  assert.ok(fake.clients.some(call => call.values.includes(180)));
});

test('retention scheduler can be started and stopped', async () => {
  const policy = createRetentionPolicy({ postgresPool: createFakePool() });
  policy.startScheduler(1000);
  assert.ok(policy.getDefaultRetention('messages') === 90);
  policy.stopScheduler();
});

test('retention status never purges audit_events', async () => {
  const fake = createFakePool({
    messages: 0,
    conversations: 0,
    contacts: 0,
    campaigns: 0,
    integrations: 0,
    ai_config: 0,
    flow_nodes: 0,
    sessions: 0,
    consent_records: 0,
    users: 0,
    audit_events: 100,
  });

  const policy = createRetentionPolicy({ postgresPool: fake.pool });
  const status = await policy.getRetentionStatus('tenant-1');

  assert.equal(status.status.auditEvents.immutable, true);
  assert.equal(status.status.auditEvents.retentionDays, 'infinite');
});
