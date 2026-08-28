import test from 'node:test';
import assert from 'node:assert/strict';
import { withRequestTransaction } from '../server/storage/request-transaction.js';

test('request transaction binds the authenticated principal to storage identity context', async () => {
  const calls = [];
  const storage = {
    async withIdentityTransaction(identity, operation) {
      calls.push(identity);
      return operation({ query: async () => ({ rows: [{ ok: true }] }) });
    },
  };
  const request = {
    user: {
      email: 'owner@example.test',
      role: 'owner',
      tenantId: 'bbbbbbbb-2222-4222-8222-bbbbbbbbbbbb',
    },
  };

  const result = await withRequestTransaction(storage, request, async tx => {
    const query = await tx.query('SELECT true AS ok');
    return query.rows[0].ok;
  });

  assert.equal(result, true);
  assert.deepEqual(calls, [request.user]);
});

test('request transaction fails closed without authenticated tenant identity', async () => {
  const storage = {
    async withIdentityTransaction() {
      throw new Error('must not acquire transaction');
    },
  };

  await assert.rejects(
    () => withRequestTransaction(storage, {}, async () => undefined),
    /authenticated tenant identity is required/i,
  );
  await assert.rejects(
    () => withRequestTransaction(storage, { user: { email: 'x@example.test' } }, async () => undefined),
    /authenticated tenant identity is required/i,
  );
});
