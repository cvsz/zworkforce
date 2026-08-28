import test from 'node:test';
import assert from 'node:assert/strict';
import { createAiApproval } from '../server/ai/ai-approval.js';

const tenantId = 'bbbbbbbb-2222-4222-8222-bbbbbbbbbbbb';

function createMockPool() {
  const calls = [];
  const tx = {
    async query(text, values = []) {
      calls.push({ text, values });
      if (text.trimStart().startsWith('INSERT')) {
        return {
          rows: [
            {
              id: 'appr-1',
              request_id: values[1],
              action_type: values[2],
              risk_level: values[3],
              status: 'pending',
              payload: values[4],
              expires_at: values[5],
              createdAt: new Date().toISOString(),
            },
          ],
          rowCount: 1,
        };
      }
      if (text.includes('UPDATE') && text.includes("status = 'approved'")) {
        return {
          rows: [
            {
              id: 'appr-1',
              request_id: 'req-1',
              action_type: 'ai_chat',
              risk_level: 'high',
              status: 'approved',
              payload: {},
              expires_at: new Date(Date.now() + 86400000).toISOString(),
              createdAt: new Date().toISOString(),
            },
          ],
          rowCount: 1,
        };
      }
      if (text.includes('UPDATE') && text.includes("status = 'rejected'")) {
        return {
          rows: [
            {
              id: 'appr-1',
              request_id: 'req-1',
              action_type: 'ai_chat',
              risk_level: 'high',
              status: 'rejected',
              payload: {},
              expires_at: new Date(Date.now() + 86400000).toISOString(),
              createdAt: new Date().toISOString(),
            },
          ],
          rowCount: 1,
        };
      }
      if (text.includes('UPDATE') && text.includes("status = 'expired'")) {
        return { rows: [], rowCount: 0 };
      }
      if (text.includes('ai_approvals') && text.includes('LIMIT 1')) {
        return { rows: [], rowCount: 0 };
      }
      if (text.includes('ai_approvals') && text.includes("status = 'pending'")) {
        return {
          rows: [
            {
              id: 'appr-1',
              request_id: 'req-1',
              action_type: 'ai_chat',
              risk_level: 'high',
              status: 'pending',
              payload: {},
              expires_at: new Date(Date.now() + 86400000).toISOString(),
              createdAt: new Date().toISOString(),
            },
          ],
          rowCount: 1,
        };
      }
      return { rows: [], rowCount: 0 };
    },
    release() {},
  };
  const pool = {
    connect: async () => tx,
  };
  return { pool, calls };
}

test('ai approval creates pending approval with expiry', async () => {
  const { pool, calls } = createMockPool();
  const approval = createAiApproval(pool, { defaultTtlMs: 3600000 });

  const result = await approval.create(tenantId, 'req-1', 'ai_chat', 'high', { summary: 'Send marketing email' });
  assert.ok(result.id);
  assert.equal(result.status, 'pending');
  assert.ok(result.expires_at);

  const insertCall = calls.find(c => c.text.includes('INSERT INTO ai_approvals'));
  assert.ok(insertCall, 'expected INSERT call');
  assert.equal(insertCall.values[0], tenantId);
  assert.equal(insertCall.values[2], 'ai_chat');
  assert.equal(insertCall.values[3], 'high');
});

test('ai approval rejects invalid risk levels', async () => {
  const { pool } = createMockPool();
  const approval = createAiApproval(pool);

  await assert.rejects(
    () => approval.create(tenantId, 'req-1', 'ai_chat', 'invalid'),
    /riskLevel must be low, medium, or high/,
  );
});

test('ai approval gets pending approvals', async () => {
  const { pool } = createMockPool();
  const approval = createAiApproval(pool);

  const pending = await approval.getPending(tenantId);
  assert.ok(Array.isArray(pending));
  assert.equal(pending.length, 1);
  assert.equal(pending[0].status, 'pending');
});

test('ai approval approves and rejects', async () => {
  const { pool } = createMockPool();
  const approval = createAiApproval(pool);

  const approved = await approval.approve(tenantId, 'appr-1', 'user-1');
  assert.ok(approved);
  assert.equal(approved.status, 'approved');

  const rejected = await approval.reject(tenantId, 'appr-1', 'user-1');
  assert.ok(rejected);
  assert.equal(rejected.status, 'rejected');
});

test('ai approval expires stale entries', async () => {
  const { pool } = createMockPool();
  const approval = createAiApproval(pool);

  const expiredCount = await approval.expireStale();
  assert.ok(Number.isSafeInteger(expiredCount));
});

test('ai approval getById returns null for missing', async () => {
  const { pool } = createMockPool();
  const approval = createAiApproval(pool);

  const result = await approval.getById(tenantId, 'missing-id');
  assert.equal(result, null);
});
