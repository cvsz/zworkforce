import test from 'node:test';
import assert from 'node:assert/strict';
import { createCampaignsRepository } from '../server/storage/postgres/campaigns-repository.js';

const tenantId = 'bbbbbbbb-2222-4222-8222-bbbbbbbbbbbb';

test('campaigns repository scopes inserts to the transaction tenant and lists campaigns', async () => {
  const calls = [];
  const tx = {
    tenantId,
    async query(text, values = []) {
      calls.push({ text, values });
      if (text.trimStart().startsWith('SELECT')) {
        return {
          rows: [
            { id: 'c1', name: 'Campaign A', status: 'draft', channel: 'line', target: 'Leads' },
          ],
        };
      }
      return {
        rows: [
          { id: 'c2', name: 'Campaign B', status: 'draft', channel: 'whatsapp', target: 'VIP' },
        ],
      };
    },
  };
  const repository = createCampaignsRepository(tx);

  assert.deepEqual(await repository.list(), [
    { id: 'c1', name: 'Campaign A', status: 'draft', channel: 'line', target: 'Leads' },
  ]);
  assert.deepEqual(
    await repository.create({ name: ' Campaign B ', channel: 'whatsapp', target: 'VIP' }),
    { id: 'c2', name: 'Campaign B', status: 'draft', channel: 'whatsapp', target: 'VIP' },
  );

  assert.match(calls[0].text, /FROM campaigns/i);
  assert.equal(calls[1].values[0], tenantId);
  assert.equal(calls[1].values[1], 'Campaign B');
  assert.equal(calls[1].values[2], 'whatsapp');
  assert.equal(calls[1].values[3], JSON.stringify('VIP'));
});

test('campaigns repository fails closed without transaction tenant context or invalid input', async () => {
  assert.throws(
    () => createCampaignsRepository({ query: async () => ({ rows: [] }) }),
    /tenant transaction context is required/i,
  );

  const repository = createCampaignsRepository({
    tenantId,
    query: async () => ({ rows: [] }),
  });
  await assert.rejects(() => repository.create({ name: '', channel: 'line', target: 'x' }), /campaign name is required/i);
  await assert.rejects(() => repository.create({ name: 'A', channel: 'line', target: '' }), /campaign target is required/i);
  await assert.rejects(() => repository.create({ name: 'A', channel: 'sms', target: 'x' }), /invalid campaign channel/i);
  await assert.rejects(
    () => repository.create({ name: 'A', channel: 'line', target: 'x'.repeat(121) }),
    /campaign target exceeds 120 characters/i,
  );
});
