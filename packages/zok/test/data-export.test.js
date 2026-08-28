import test from 'node:test';
import assert from 'node:assert/strict';
import { createDataExport } from '../server/privacy/data-export.js';

function createFakeJsonStorage(data) {
  const current = JSON.parse(JSON.stringify(data));
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

function createFakePool(rowsByTable = {}) {
  const clients = [];
  const client = {
    async query(text, values) {
      clients.push({ text, values });
      const tableMatch = text.match(/from (\w+)/i);
      const table = tableMatch ? tableMatch[1].toLowerCase() : null;
      const rows = rowsByTable[table] || [];
      return { rows: [...rows] };
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

test('createDataExport requires jsonStorage or postgresPool', () => {
  assert.throws(() => createDataExport({}), /jsonStorage or postgresPool is required/);
});

test('exportTenant validates tenantId', async () => {
  const exportService = createDataExport({ jsonStorage: createFakeJsonStorage({}) });
  await assert.rejects(() => exportService.exportTenant(null), /tenantId is required/);
  await assert.rejects(() => exportService.exportTenant(''), /tenantId is required/);
});

test('exportTenant produces complete JSON snapshot in JSON mode', async () => {
  const db = {
    chats: [{ id: 1, name: 'Test Chat', messages: [{ sender: 'customer', text: 'Hello' }] }],
    campaigns: [{ id: 1, name: 'Test Campaign' }],
    integrations: [{ id: 'shopify', name: 'Shopify' }],
    aiConfig: { agentName: 'Test AI' },
    flowNodes: [{ id: 'node-1', type: 'trigger' }],
    contacts: [{ id: 'c1', name: 'Contact' }],
  };
  const exportService = createDataExport({ jsonStorage: createFakeJsonStorage(db) });
  const result = await exportService.exportTenant('tenant-1');

  assert.equal(result.contentType, 'application/zip');
  assert.ok(result.filename.includes('tenant-1'));
  assert.ok(result.buffer instanceof Buffer);
  assert.equal(result.recordCount.chats, 1);
  assert.equal(result.recordCount.messages, 1);
  assert.equal(result.recordCount.campaigns, 1);
  assert.equal(result.recordCount.integrations, 1);
  assert.equal(result.recordCount.aiConfig, 1);
  assert.equal(result.recordCount.flowNodes, 1);
  assert.equal(result.recordCount.contacts, 1);
});

test('exportTenant handles missing optional collections in JSON mode', async () => {
  const db = { chats: [], campaigns: [], integrations: [], aiConfig: {}, flowNodes: [] };
  const exportService = createDataExport({ jsonStorage: createFakeJsonStorage(db) });
  const result = await exportService.exportTenant('tenant-1');
  assert.ok(result.buffer instanceof Buffer);
  assert.equal(result.recordCount.chats, 0);
  assert.equal(result.recordCount.messages, 0);
});

test('exportTenant produces ZIP with JSON content in JSON mode', async () => {
  const db = {
    chats: [{ id: 1, name: 'Chat', messages: [] }],
    campaigns: [],
    integrations: [],
    aiConfig: {},
    flowNodes: [],
    contacts: [],
  };
  const exportService = createDataExport({ jsonStorage: createFakeJsonStorage(db) });
  const result = await exportService.exportTenant('tenant-1');

  // Verify it's a valid ZIP by checking magic bytes
  assert.ok(result.buffer[0] === 0x50 && result.buffer[1] === 0x4b, 'should be a ZIP file');
});

test('exportTenant produces snapshot in Postgres mode', async () => {
  const fake = createFakePool({
    contacts: [{ id: 'c1', name: 'Contact' }],
    conversations: [{ id: 'conv1' }],
    messages: [{ id: 'msg1' }],
    campaigns: [{ id: 'camp1' }],
    integrations: [{ id: 'int1' }],
    ai_config: [{ id: 'ai1', agent_name: 'AI' }],
    flow_nodes: [{ id: 'node1' }],
  });
  const auditCalls = [];
  const auditService = {
    async emit(event) { auditCalls.push(event); },
  };

  const exportService = createDataExport({ postgresPool: fake.pool, auditService });
  const result = await exportService.exportTenant('tenant-1');

  assert.ok(result.buffer instanceof Buffer);
  assert.equal(result.recordCount.contacts, 1);
  assert.equal(result.recordCount.conversations, 1);
  assert.equal(result.recordCount.messages, 1);
  assert.equal(result.recordCount.campaigns, 1);
  assert.equal(result.recordCount.integrations, 1);
  assert.equal(result.recordCount.aiConfig, 1);
  assert.equal(result.recordCount.flowNodes, 1);
  assert.equal(auditCalls.length, 1);
  assert.equal(auditCalls[0].action, 'privacy.export');
});

test('exportTenant logs audit event in JSON mode', async () => {
  const auditCalls = [];
  const auditService = {
    async emit(event) { auditCalls.push(event); },
  };
  const exportService = createDataExport({
    jsonStorage: createFakeJsonStorage({
      chats: [], campaigns: [], integrations: [], aiConfig: {}, flowNodes: [], contacts: [],
    }),
    auditService,
  });

  await exportService.exportTenant('tenant-1');
  assert.equal(auditCalls.length, 1);
  assert.equal(auditCalls[0].action, 'privacy.export');
  assert.equal(auditCalls[0].tenant_id, 'tenant-1');
  assert.equal(auditCalls[0].resource_type, 'privacy');
});
