import test from 'node:test';
import assert from 'node:assert/strict';
import { createContactsRepository } from '../server/storage/postgres/contacts-repository.js';

test('contacts repository scopes reads and inserts to the transaction tenant', async () => {
  const calls = [];
  const tx = {
    tenantId: 'bbbbbbbb-2222-4222-8222-bbbbbbbbbbbb',
    async query(text, values = []) {
      calls.push({ text, values });
      if (text.trimStart().startsWith('SELECT')) {
        return { rows: [{ id: 'c1', name: 'Contact A', email: 'a@example.test' }] };
      }
      return { rows: [{ id: 'c2', name: 'Contact B', email: 'b@example.test' }] };
    },
  };
  const repository = createContactsRepository(tx);

  assert.deepEqual(await repository.list(), [{ id: 'c1', name: 'Contact A', email: 'a@example.test' }]);
  assert.deepEqual(
    await repository.create({ name: ' Contact B ', email: 'B@Example.Test' }),
    { id: 'c2', name: 'Contact B', email: 'b@example.test' },
  );

  assert.match(calls[0].text, /FROM contacts/i);
  assert.equal(calls[1].values[0], tx.tenantId);
  assert.equal(calls[1].values[1], 'Contact B');
  assert.equal(calls[1].values[2], 'b@example.test');
});

test('contacts repository fails closed without transaction tenant context or invalid input', async () => {
  assert.throws(
    () => createContactsRepository({ query: async () => ({ rows: [] }) }),
    /tenant transaction context is required/i,
  );

  const repository = createContactsRepository({
    tenantId: 'bbbbbbbb-2222-4222-8222-bbbbbbbbbbbb',
    query: async () => ({ rows: [] }),
  });
  await assert.rejects(() => repository.create({ name: '' }), /contact name is required/i);
  await assert.rejects(() => repository.create({ name: 'A', email: 'not-email' }), /valid contact email/i);
});
