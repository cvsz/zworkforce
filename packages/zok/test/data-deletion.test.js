import test from 'node:test';
import assert from 'node:assert/strict';
import { createDataDeletion } from '../server/privacy/data-deletion.js';

function createFakeJsonStorage(initialData) {
  const current = JSON.parse(JSON.stringify(initialData));
  return {
    async read() {
      return JSON.parse(JSON.stringify(current));
    },
    async update(mutator) {
      const cloned = JSON.parse(JSON.stringify(current));
      const result = await mutator(cloned);
      Object.assign(current, cloned);
      return result;
    },
  };
}

function createFakePool(affectedRowsByTable = {}) {
  const clients = [];
  const client = {
    async query(text, values) {
      clients.push({ text, values });
      const tableMatch = text.match(/update (\w+)/i);
      const table = tableMatch ? tableMatch[1].toLowerCase() : null;
      const rowCount = typeof affectedRowsByTable[table] === 'object' && affectedRowsByTable[table] !== null
        ? affectedRowsByTable[table].rowCount
        : (affectedRowsByTable[table] || 0);
      return { rowCount };
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

test('createDataDeletion requires jsonStorage or postgresPool', () => {
  assert.throws(() => createDataDeletion({}), /jsonStorage or postgresPool is required/);
});

test('deleteTenant validates tenantId', async () => {
  const deletionService = createDataDeletion({ jsonStorage: createFakeJsonStorage({}) });
  await assert.rejects(() => deletionService.deleteTenant(null), /tenantId is required/);
  await assert.rejects(() => deletionService.deleteTenant(''), /tenantId is required/);
});

test('deleteTenant requires explicit confirmation', async () => {
  const deletionService = createDataDeletion({ jsonStorage: createFakeJsonStorage({}) });
  await assert.rejects(
    () => deletionService.deleteTenant('tenant-1', { confirm: false }),
    /Explicit confirmation is required/
  );
});

test('deleteTenant rejects protected audit_events type', async () => {
  const deletionService = createDataDeletion({ jsonStorage: createFakeJsonStorage({}) });
  await assert.rejects(
    () => deletionService.deleteTenant('tenant-1', { confirm: true, types: ['audit_events'] }),
    /Cannot delete audit_events/
  );
});

test('deleteTenant rejects invalid deletion types', async () => {
  const deletionService = createDataDeletion({ jsonStorage: createFakeJsonStorage({}) });
  await assert.rejects(
    () => deletionService.deleteTenant('tenant-1', { confirm: true, types: ['invalid_type'] }),
    /Invalid deletion types/
  );
});

test('deleteTenant performs hard delete in JSON mode', async () => {
  const db = {
    chats: [{ id: 1 }, { id: 2 }],
    campaigns: [{ id: 1 }],
    integrations: [{ id: 'shopify' }],
    flowNodes: [{ id: 'node-1' }],
    aiConfig: { agentName: 'AI' },
    contacts: [{ id: 'c1' }],
  };
  const deletionService = createDataDeletion({ jsonStorage: createFakeJsonStorage(db) });
  const result = await deletionService.deleteTenant('tenant-1', { confirm: true });

  assert.equal(result.tenantId, 'tenant-1');
  assert.equal(result.deletedCounts.chats, 2);
  assert.equal(result.deletedCounts.campaigns, 1);
  assert.equal(result.deletedCounts.integrations, 1);
  assert.equal(result.deletedCounts.flowNodes, 1);
  assert.equal(result.deletedCounts.aiConfig, 1);
  assert.equal(result.deletedCounts.contacts, 1);
});

test('deleteTenant supports selective deletion by type in JSON mode', async () => {
  const db = {
    chats: [{ id: 1 }],
    campaigns: [{ id: 1 }],
    integrations: [],
    flowNodes: [],
    aiConfig: {},
    contacts: [],
  };
  const deletionService = createDataDeletion({ jsonStorage: createFakeJsonStorage(db) });
  const result = await deletionService.deleteTenant('tenant-1', { confirm: true, types: ['campaigns'] });

  assert.equal(result.deletedCounts.campaigns, 1);
  assert.equal(result.deletedCounts.chats, undefined);
});

test('deleteTenant performs soft delete in Postgres mode', async () => {
  const fake = createFakePool({
    messages: { rowCount: 2 },
    conversations: { rowCount: 1 },
    contacts: { rowCount: 1 },
    campaigns: { rowCount: 1 },
    integrations: { rowCount: 1 },
    ai_config: { rowCount: 1 },
    flow_nodes: { rowCount: 1 },
    sessions: { rowCount: 0 },
    consent_records: { rowCount: 0 },
    users: { rowCount: 0 },
  });

  const auditCalls = [];
  const auditService = {
    async emit(event) { auditCalls.push(event); },
  };

  const deletionService = createDataDeletion({ postgresPool: fake.pool, auditService });
  const result = await deletionService.deleteTenant('tenant-1', { confirm: true });

  assert.equal(result.tenantId, 'tenant-1');
  assert.equal(result.deletedCounts.messages, 2);
  assert.equal(result.deletedCounts.conversations, 1);
  assert.equal(result.deletedCounts.contacts, 1);
  assert.equal(auditCalls.length, 1);
  assert.equal(auditCalls[0].action, 'privacy.delete');
});

test('deleteTenant supports selective deletion by type in Postgres mode', async () => {
  const fake = createFakePool({
    messages: { rowCount: 5 },
    conversations: { rowCount: 0 },
    contacts: { rowCount: 0 },
    campaigns: { rowCount: 0 },
    integrations: { rowCount: 0 },
    ai_config: { rowCount: 0 },
    flow_nodes: { rowCount: 0 },
    sessions: { rowCount: 0 },
    consent_records: { rowCount: 0 },
    users: { rowCount: 0 },
  });

  const deletionService = createDataDeletion({ postgresPool: fake.pool });
  const result = await deletionService.deleteTenant('tenant-1', { confirm: true, types: ['messages'] });

  assert.equal(result.deletedCounts.messages, 5);
  assert.equal(result.deletedCounts.conversations, undefined);
});

test('deleteTenant supports date-based deletion in Postgres mode', async () => {
  const fake = createFakePool({
    messages: { rowCount: 3 },
    conversations: { rowCount: 0 },
    contacts: { rowCount: 0 },
    campaigns: { rowCount: 0 },
    integrations: { rowCount: 0 },
    ai_config: { rowCount: 0 },
    flow_nodes: { rowCount: 0 },
    sessions: { rowCount: 0 },
    consent_records: { rowCount: 0 },
    users: { rowCount: 0 },
  });

  const deletionService = createDataDeletion({ postgresPool: fake.pool });
  const outcome = await deletionService.deleteTenant('tenant-1', {
    confirm: true,
    types: ['messages'],
    beforeDate: '2024-01-01T00:00:00.000Z',
  });

  assert.equal(outcome.deletedCounts.messages, 3);
  assert.ok(fake.clients.some(call => call.values.includes('2024-01-01T00:00:00.000Z')));
});

test('deleteTenant does not delete audit_events even when types includes all', async () => {
  const fake = createFakePool({
    messages: { rowCount: 0 },
    conversations: { rowCount: 0 },
    contacts: { rowCount: 0 },
    campaigns: { rowCount: 0 },
    integrations: { rowCount: 0 },
    ai_config: { rowCount: 0 },
    flow_nodes: { rowCount: 0 },
    sessions: { rowCount: 0 },
    consent_records: { rowCount: 0 },
    users: { rowCount: 0 },
  });

  const auditCalls = [];
  const auditService = {
    async emit(event) { auditCalls.push(event); },
  };

  const deletionService = createDataDeletion({ postgresPool: fake.pool, auditService });
  await deletionService.deleteTenant('tenant-1', { confirm: true, types: ['all'] });

  assert.equal(auditCalls.length, 1);
  assert.equal(auditCalls[0].action, 'privacy.delete');
  assert.ok(!auditCalls[0].metadata.types.includes('audit_events'));
});

test('deleteTenant logs deletion in audit trail', async () => {
  const auditCalls = [];
  const auditService = {
    async emit(event) { auditCalls.push(event); },
  };
  const deletionService = createDataDeletion({
    jsonStorage: createFakeJsonStorage({ chats: [], campaigns: [], integrations: [], flowNodes: [], aiConfig: {}, contacts: [] }),
    auditService,
  });

  await deletionService.deleteTenant('tenant-1', { confirm: true });
  assert.equal(auditCalls.length, 1);
  assert.equal(auditCalls[0].action, 'privacy.delete');
  assert.equal(auditCalls[0].tenant_id, 'tenant-1');
  assert.equal(auditCalls[0].resource_type, 'privacy');
});
