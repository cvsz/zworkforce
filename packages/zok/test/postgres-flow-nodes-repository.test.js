import test from 'node:test';
import assert from 'node:assert/strict';
import { createFlowNodesRepository } from '../server/storage/postgres/flow-nodes-repository.js';

const tenantId = 'bbbbbbbb-2222-4222-8222-bbbbbbbbbbbb';

test('flow-nodes repository replaces nodes and returns camelCase objects', async () => {
  const calls = [];
  const tx = {
    tenantId,
    async query(text, values = []) {
      calls.push({ text, values });
      if (text.includes('DELETE FROM flow_nodes')) {
        return { rowCount: 1 };
      }
      if (text.includes('INSERT INTO flow_nodes')) {
        return {
          rows: [
            { id: 'node-1', type: 'trigger', title: 'T1', description: 'D1', x: 10, y: 20, details: { k: 'v' } },
          ],
        };
      }
      return { rows: [] };
    },
  };
  const repository = createFlowNodesRepository(tx);

  const nodes = await repository.replace([
    { id: 'node-1', type: 'trigger', title: 'T1', description: 'D1', x: 10, y: 20, details: { k: 'v' } },
  ]);
  assert.deepEqual(nodes, [
    { id: 'node-1', type: 'trigger', title: 'T1', description: 'D1', x: 10, y: 20, details: { k: 'v' } },
  ]);

  assert.ok(calls[0].text.includes('DELETE FROM flow_nodes WHERE tenant_id = $1'));
  assert.equal(calls[0].values[0], tenantId);
  assert.ok(calls[1].text.includes('INSERT INTO flow_nodes'));
  assert.equal(calls[1].values[0], tenantId);
  assert.equal(calls[1].values[1], 'node-1');
  assert.equal(calls[1].values[5], 10);
});

test('flow-nodes repository validates tenant transaction context and inputs', async () => {
  assert.throws(
    () => createFlowNodesRepository({ query: async () => ({ rows: [] }) }),
    /tenant transaction context is required/i,
  );

  const repository = createFlowNodesRepository({ tenantId, query: async () => ({ rows: [] }) });
  await assert.rejects(() => repository.replace('not-array'), /nodes must be an array/i);
  await assert.rejects(() => repository.replace(new Array(201).fill({ id: 1 })), /nodes must be an array of at most 200 items/i);
  await assert.rejects(() => repository.replace([null]), /each node must be an object/i);
});
