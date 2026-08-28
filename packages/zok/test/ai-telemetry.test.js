import test from 'node:test';
import assert from 'node:assert/strict';
import { createAiTelemetry } from '../server/ai/ai-telemetry.js';

const tenantId = 'bbbbbbbb-2222-4222-8222-bbbbbbbbbbbb';

function createMockPool(rows = []) {
  const calls = [];
  const tx = {
    async query(text, values = []) {
      calls.push({ text, values });
      if (text.trimStart().startsWith('INSERT')) {
        return {
          rows: [
            {
              id: 'tel-1',
              request_id: values[1],
              model: values[3],
              latency_ms: values[6],
              tokens_used: values[7],
              approval_status: values[8],
              createdAt: new Date().toISOString(),
            },
          ],
          rowCount: 1,
        };
      }
      return { rows, rowCount: rows.length };
    },
    release() {},
  };
  const pool = {
    connect: async () => tx,
  };
  return { pool, calls, tx };
}

test('ai telemetry emits events with required fields', async () => {
  const { pool, calls } = createMockPool();
  const telemetry = createAiTelemetry(pool);

  const event = await telemetry.emit({
    tenantId,
    requestId: 'req-1',
    userId: 'user-1',
    model: 'gpt-4',
    promptHash: 'hash1',
    responseHash: 'hash2',
    latencyMs: 150,
    tokensUsed: 42,
    approvalStatus: 'approved',
    metadata: { riskLevel: 'low' },
  });

  assert.ok(event.id);
  assert.equal(event.request_id, 'req-1');
  assert.equal(event.model, 'gpt-4');
  assert.equal(event.latency_ms, 150);
  assert.equal(event.tokens_used, 42);
  assert.equal(event.approval_status, 'approved');

  const insertCall = calls.find(c => c.text.includes('INSERT INTO ai_telemetry'));
  assert.ok(insertCall, 'expected INSERT call');
  assert.equal(insertCall.values[0], tenantId);
});

test('ai telemetry rejects invalid tenant and fields', async () => {
  const { pool } = createMockPool();
  const telemetry = createAiTelemetry(pool);

  await assert.rejects(() => telemetry.emit({}), /tenantId is required and must be a UUID/);
  await assert.rejects(() => telemetry.emit({ tenantId }), /requestId is required/);
  await assert.rejects(() => telemetry.emit({ tenantId, requestId: 'r1' }), /model is required/);
  await assert.rejects(() => telemetry.emit({ tenantId, requestId: 'r1', model: 'gpt' }), /promptHash is required/);
  await assert.rejects(() => telemetry.emit({ tenantId, requestId: 'r1', model: 'gpt', promptHash: 'h' }), /responseHash is required/);
  await assert.rejects(() => telemetry.emit({ tenantId, requestId: 'r1', model: 'gpt', promptHash: 'h', responseHash: 'h' }), /latencyMs must be a non-negative integer/);
  await assert.rejects(() => telemetry.emit({ tenantId, requestId: 'r1', model: 'gpt', promptHash: 'h', responseHash: 'h', latencyMs: 10 }), /tokensUsed must be a non-negative integer/);
});

test('ai telemetry lists events with filters', async () => {
  const { pool, calls } = createMockPool([
    {
      id: 'tel-1',
      request_id: 'req-1',
      model: 'gpt-4',
      latency_ms: 150,
      tokens_used: 42,
      approval_status: 'approved',
      createdAt: new Date().toISOString(),
    },
  ]);
  const telemetry = createAiTelemetry(pool);

  const events = await telemetry.list(tenantId, { model: 'gpt-4', limit: 10, offset: 5 });
  assert.ok(Array.isArray(events));

  const listCall = calls.find(c => c.text.includes('SELECT') && c.text.includes('ai_telemetry'));
  assert.ok(listCall, 'expected SELECT call');
  assert.equal(listCall.values[0], tenantId);
  assert.equal(listCall.values[1], 'gpt-4');
  assert.equal(listCall.values[2], 10);
  assert.equal(listCall.values[3], 5);
});
