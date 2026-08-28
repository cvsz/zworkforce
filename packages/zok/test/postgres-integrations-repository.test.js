import test from 'node:test';
import assert from 'node:assert/strict';
import { createIntegrationsRepository } from '../server/storage/postgres/integrations-repository.js';

const tenantId = 'bbbbbbbb-2222-4222-8222-bbbbbbbbbbbb';

test('integrations repository lists integrations and toggles status by id', async () => {
  const calls = [];
  const tx = {
    tenantId,
    async query(text, values = []) {
      calls.push({ text, values });
      if (text.includes('RETURNING id, provider')) {
        return { rows: [{
          id: 'i1', provider: 'shopify', externalId: 'shop-1', status: 'connected',
          config: {}, apiKeyPrefix: 'pk_live_1', hasCredentials: true,
          createdAt: '2026-01-01T00:00:00.000Z', updatedAt: '2026-01-01T00:00:00.000Z',
        }] };
      }
      if (text.includes('WHERE id = $1')) {
        return { rows: [{ id: 'i1', provider: 'shopify', status: 'disconnected' }] };
      }
      if (text.includes('FROM integrations')) {
        return { rows: [{
          id: 'i1', provider: 'shopify', externalId: 'shop-1', status: 'disconnected',
          config: {}, apiKeyPrefix: null, hasCredentials: false,
          createdAt: '2026-01-01T00:00:00.000Z', updatedAt: '2026-01-01T00:00:00.000Z',
        }] };
      }
      return { rows: [] };
    },
  };
  const repository = createIntegrationsRepository(tx);

  assert.deepEqual(await repository.list(), [{
    id: 'i1', provider: 'shopify', externalId: 'shop-1', status: 'disconnected',
    config: {}, apiKey: null, hasCredentials: false,
    createdAt: '2026-01-01T00:00:00.000Z', updatedAt: '2026-01-01T00:00:00.000Z',
  }]);
  assert.deepEqual(
    await repository.toggleStatus('i1'),
    {
      id: 'i1', provider: 'shopify', externalId: 'shop-1', status: 'connected',
      config: {}, apiKey: 'pk_live_1…••••', hasCredentials: true,
      createdAt: '2026-01-01T00:00:00.000Z', updatedAt: '2026-01-01T00:00:00.000Z',
    },
  );

  assert.ok(calls[0].text.includes('FROM integrations'));
  assert.ok(calls[1].text.includes('WHERE id = $1'));
  assert.equal(calls[1].values[0], 'i1');
  assert.ok(calls[2].text.includes('UPDATE integrations'));
});

test('integrations repository validates tenant transaction context and inputs', async () => {
  assert.throws(
    () => createIntegrationsRepository({ query: async () => ({ rows: [] }) }),
    /tenant transaction context is required/i,
  );

  const repository = createIntegrationsRepository({ tenantId, query: async () => ({ rows: [] }) });
  await assert.rejects(() => repository.findByProvider(''), /valid provider is required/i);
  await assert.rejects(() => repository.findByProvider('a'.repeat(121)), /provider exceeds 120 characters/i);
  await assert.rejects(() => repository.toggleStatus(''), /valid integration id is required/i);
  assert.equal(await repository.toggleStatus('i1'), null);
});
