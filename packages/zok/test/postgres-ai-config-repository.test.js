import test from 'node:test';
import assert from 'node:assert/strict';
import { createAiConfigRepository } from '../server/storage/postgres/ai-config-repository.js';

const tenantId = 'bbbbbbbb-2222-4222-8222-bbbbbbbbbbbb';

test('ai-config repository replaces tenant config and returns camelCase object', async () => {
  const calls = [];
  const tx = {
    tenantId,
    async query(text, values = []) {
      calls.push({ text, values });
      if (text.trimStart().startsWith('DELETE')) {
        return { rowCount: 1 };
      }
      return {
        rows: [
          {
            id: 'a1',
            agentName: 'Zok AI',
            persona: 'sales',
            knowledgeBase: 'KB content',
            qaPairs: [{ q: 'Q?', a: 'A.' }],
          },
        ],
      };
    },
  };
  const repository = createAiConfigRepository(tx);

  const config = await repository.replace({
    agentName: 'Zok AI',
    persona: 'sales',
    knowledgeBase: 'KB content',
    qaPairs: [{ q: 'Q?', a: 'A.' }],
  });
  assert.deepEqual(config, {
    id: 'a1',
    agentName: 'Zok AI',
    persona: 'sales',
    knowledgeBase: 'KB content',
    qaPairs: [{ q: 'Q?', a: 'A.' }],
  });

  assert.match(calls[0].text, /DELETE FROM ai_config WHERE tenant_id = \$1/i);
  assert.equal(calls[0].values[0], tenantId);
  assert.match(calls[1].text, /INSERT INTO ai_config/i);
  assert.equal(calls[1].values[0], tenantId);
  assert.equal(calls[1].values[1], 'Zok AI');
  assert.equal(calls[1].values[2], 'sales');
});

test('ai-config repository fails closed without tenant context or invalid input', async () => {
  assert.throws(
    () => createAiConfigRepository({ query: async () => ({ rows: [] }) }),
    /tenant transaction context is required/i,
  );

  const repository = createAiConfigRepository({ tenantId, query: async () => ({ rows: [] }) });
  await assert.rejects(() => repository.replace({}), /agentName is required/i);
  await assert.rejects(() => repository.replace({ agentName: 'A'.repeat(121) }), /agentName exceeds 120 characters/i);
  await assert.rejects(() => repository.replace({ agentName: 'A', persona: 'invalid' }), /persona must be sales, support, or lead/i);
  await assert.rejects(() => repository.replace({ agentName: 'A', persona: 'sales', knowledgeBase: '' }), /knowledgeBase is required/i);
  await assert.rejects(() => repository.replace({ agentName: 'A', persona: 'sales', knowledgeBase: 'A'.repeat(10001) }), /knowledgeBase exceeds 10000 characters/i);
  await assert.rejects(() => repository.replace({ agentName: 'A', persona: 'sales', knowledgeBase: 'KB', qaPairs: [{ q: '', a: 'A' }] }), /question is required/i);
  await assert.rejects(() => repository.replace({ agentName: 'A', persona: 'sales', knowledgeBase: 'KB', qaPairs: [{ q: 'Q', a: 'A'.repeat(2001) }] }), /answer exceeds 2000 characters/i);
  await assert.rejects(() => repository.replace({ agentName: 'A', persona: 'sales', knowledgeBase: 'KB', qaPairs: new Array(101).fill({ q: 'Q', a: 'A' }) }), /qaPairs must contain at most 100 items/i);
});
