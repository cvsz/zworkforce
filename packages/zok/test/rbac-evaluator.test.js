import test from 'node:test';
import assert from 'node:assert/strict';
import { createRbacEvaluator } from '../server/storage/postgres/rbac-evaluator.js';

const tenantId = 'bbbbbbbb-2222-4222-8222-bbbbbbbbbbbb';
const userId = 'eeeeeeee-5555-4555-8555-eeeeeeeeeeee';

function createTx(rows) {
  const calls = [];
  return {
    tenantId,
    async query(text, values = []) {
      calls.push({ text, values });
      return { rows: rows || [] };
    },
    calls,
  };
}

test('rbac evaluator rejects invalid transaction context', () => {
  assert.throws(() => createRbacEvaluator(null), /tenant transaction context is required/i);
  assert.throws(() => createRbacEvaluator({ query: async () => ({}) }), /tenant transaction context is required/i);
  assert.throws(
    () => createRbacEvaluator({ query: async () => ({}), tenantId: 'bad' }),
    /tenant transaction context is required/i
  );
});

test('rbac evaluator loads user roles from user_roles and roles tables', async () => {
  const permissions = { 'chats:write': true, 'campaigns:delete': true };
  const tx = createTx([{ permissions }]);
  const evaluator = createRbacEvaluator(tx);

  const roles = await evaluator.loadUserRoles(userId);
  assert.deepEqual(roles, [permissions]);
  assert.equal(tx.calls[0].values[0], tenantId);
  assert.equal(tx.calls[0].values[1], userId);
  assert.match(tx.calls[0].text, /FROM user_roles ur/i);
  assert.match(tx.calls[0].text, /JOIN roles r/i);
});

test('rbac evaluator returns false for invalid user id', async () => {
  const tx = createTx([]);
  const evaluator = createRbacEvaluator(tx);
  await assert.rejects(() => evaluator.loadUserRoles('bad'), /valid user id is required/i);
});

test('rbac evaluator denies by default when no roles match', async () => {
  const tx = createTx([]);
  const evaluator = createRbacEvaluator(tx);

  assert.equal(await evaluator.evaluate(userId, 'chats:write'), false);
  assert.equal(await evaluator.evaluate(userId, 'admin:*'), false);
});

test('rbac evaluator grants exact permission', async () => {
  const tx = createTx([{ permissions: { 'chats:write': true } }]);
  const evaluator = createRbacEvaluator(tx);

  assert.equal(await evaluator.evaluate(userId, 'chats:write'), true);
  assert.equal(await evaluator.evaluate(userId, 'chats:read'), false);
});

test('rbac evaluator grants wildcard permission for resource', async () => {
  const tx = createTx([{ permissions: { 'chats:*': true } }]);
  const evaluator = createRbacEvaluator(tx);

  assert.equal(await evaluator.evaluate(userId, 'chats:write'), true);
  assert.equal(await evaluator.evaluate(userId, 'chats:read'), true);
  assert.equal(await evaluator.evaluate(userId, 'campaigns:write'), false);
});

test('rbac evaluator grants admin wildcard', async () => {
  const tx = createTx([{ permissions: { 'admin:*': true } }]);
  const evaluator = createRbacEvaluator(tx);

  assert.equal(await evaluator.evaluate(userId, 'chats:write'), true);
  assert.equal(await evaluator.evaluate(userId, 'campaigns:delete'), true);
  assert.equal(await evaluator.evaluate(userId, 'users:manage'), true);
});

test('rbac evaluator combines multiple role permissions', async () => {
  const tx = createTx([
    { permissions: { 'chats:write': true } },
    { permissions: { 'campaigns:write': true } },
  ]);
  const evaluator = createRbacEvaluator(tx);

  assert.equal(await evaluator.evaluate(userId, 'chats:write'), true);
  assert.equal(await evaluator.evaluate(userId, 'campaigns:write'), true);
  assert.equal(await evaluator.evaluate(userId, 'campaigns:delete'), false);
});

test('rbac evaluator caches results per request', async () => {
  const tx = createTx([{ permissions: { 'chats:write': true } }]);
  const evaluator = createRbacEvaluator(tx);

  const cache = { tenantId, entries: new Map() };
  assert.equal(await evaluator.evaluate(userId, 'chats:write', cache), true);
  assert.equal(cache.entries.size, 1);
  assert.equal(await evaluator.evaluate(userId, 'chats:write', cache), true);
  assert.equal(cache.entries.size, 1);
});

test('rbac evaluator skips cache for mismatched tenant', async () => {
  const tx = createTx([{ permissions: { 'chats:write': true } }]);
  const evaluator = createRbacEvaluator(tx);

  const cache = { tenantId: 'wrong-tenant', entries: new Map() };
  assert.equal(await evaluator.evaluate(userId, 'chats:write', cache), true);
  assert.equal(cache.entries.size, 0);
});

test('rbac evaluator rejects empty permission string', async () => {
  const tx = createTx([]);
  const evaluator = createRbacEvaluator(tx);

  assert.equal(await evaluator.evaluate(userId, ''), false);
  assert.equal(await evaluator.evaluate(userId, '   '), false);
});
