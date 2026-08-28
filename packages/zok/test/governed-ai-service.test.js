import test from 'node:test';
import assert from 'node:assert/strict';
import { createGovernedAIService } from '../server/ai/governed-ai-service.js';

const tenantId = 'bbbbbbbb-2222-4222-8222-bbbbbbbbbbbb';

function createMockPool() {
  const calls = [];
  const tx = {
    tenantId,
    async query(text, values = []) {
      calls.push({ text, values });
      if (text.trimStart().startsWith('BEGIN')) return { rowCount: 0 };
      if (text.trimStart().startsWith('COMMIT')) return { rowCount: 0 };
      if (text.trimStart().startsWith('ROLLBACK')) return { rowCount: 0 };
      if (text.includes('ai_config_versions') && text.includes('MAX(version)')) {
        return { rows: [{ next_version: 1 }], rowCount: 1 };
      }
      if (text.includes('ai_config_versions') && text.includes('ORDER BY version DESC')) {
        return {
          rows: [
            {
              id: 'cfg-1',
              version: 1,
              config: { model: 'gpt-4', temperature: 0.7, max_tokens: 1024, system_prompt: 'You are helpful.' },
              risk_level: 'high',
              createdAt: new Date().toISOString(),
            },
          ],
          rowCount: 1,
        };
      }
      if (text.includes('ai_config_versions') && text.includes('INSERT')) {
        return {
          rows: [
            {
              id: 'cfg-1',
              version: 1,
              config: { model: 'gpt-4', temperature: 0.7, max_tokens: 1024, system_prompt: 'You are helpful.' },
              risk_level: 'low',
              createdAt: new Date().toISOString(),
            },
          ],
          rowCount: 1,
        };
      }
      if (text.includes('ai_telemetry') && text.includes('INSERT')) {
        return {
          rows: [
            {
              id: 'tel-1',
              request_id: 'req-1',
              model: 'gpt-4',
              latency_ms: 100,
              tokens_used: 50,
              approval_status: 'auto_approved',
              createdAt: new Date().toISOString(),
            },
          ],
          rowCount: 1,
        };
      }
      if (text.includes('ai_approvals') && text.includes('INSERT')) {
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

test('governed AI service validates config against schema', async () => {
  const { pool } = createMockPool();
  const telemetry = { emit: async () => ({}) };
  const approval = { create: async () => ({}) };
  const service = createGovernedAIService({ telemetry, approval, pool });

  await assert.rejects(() => service.validateConfig(null), /AI config must be a non-null object/);
  await assert.rejects(() => service.validateConfig([]), /AI config must be a non-null object/);
  await assert.rejects(() => service.validateConfig({}), /model is required/);
  await assert.rejects(() => service.validateConfig({ model: '' }), /model is required/);
  await assert.rejects(() => service.validateConfig({ model: 'A'.repeat(121) }), /model exceeds the 120-character limit/);
  await assert.rejects(() => service.validateConfig({ model: 'gpt-4', temperature: 3 }), /temperature must be at most 2/);
  await assert.rejects(() => service.validateConfig({ model: 'gpt-4', temperature: -1 }), /temperature must be at least 0/);
  await assert.rejects(() => service.validateConfig({ model: 'gpt-4', temperature: 0.7, max_tokens: 0 }), /max_tokens must be at least 1/);
  await assert.rejects(() => service.validateConfig({ model: 'gpt-4', temperature: 0.7, max_tokens: 100001 }), /max_tokens must be at most 100000/);
  await assert.rejects(() => service.validateConfig({ model: 'gpt-4', temperature: 0.7, max_tokens: 100, system_prompt: '' }), /system_prompt is required/);
  await assert.rejects(() => service.validateConfig({ model: 'gpt-4', temperature: 0.7, max_tokens: 100, system_prompt: 'A'.repeat(8001) }), /system_prompt exceeds the 8000-character limit/);

  const validConfig = { model: 'gpt-4', temperature: 0.7, max_tokens: 1024, system_prompt: 'You are helpful.' };
  assert.ok(await service.validateConfig(validConfig));
});

test('governed AI service rejects invalid risk levels', async () => {
  const { pool } = createMockPool();
  const telemetry = { emit: async () => ({}) };
  const approval = { create: async () => ({}) };
  const service = createGovernedAIService({ telemetry, approval, pool });

  await assert.rejects(
    () => service.setConfig(tenantId, { model: 'gpt-4', temperature: 0.7, max_tokens: 1024, system_prompt: 'Hi' }, 'invalid'),
    /risk_level must be low, medium, or high/,
  );
});

test('governed AI service sets versioned config', async () => {
  const { pool, calls } = createMockPool();
  const telemetry = { emit: async () => ({}) };
  const approval = { create: async () => ({}) };
  const service = createGovernedAIService({ telemetry, approval, pool });

  const config = { model: 'gpt-4', temperature: 0.7, max_tokens: 1024, system_prompt: 'You are helpful.' };
  const result = await service.setConfig(tenantId, config, 'low');
  assert.equal(result.version, 1);
  assert.equal(result.risk_level, 'low');

  const insertCall = calls.find(c => c.text.includes('INSERT INTO ai_config_versions'));
  assert.ok(insertCall, 'expected INSERT call');
  assert.equal(insertCall.values[0], tenantId);
  assert.equal(insertCall.values[1], 1);
});

test('governed AI service chat returns approval_required for high risk', async () => {
  const { pool } = createMockPool();
  const telemetry = { emit: async () => ({}) };
  const approval = { create: async () => ({ id: 'appr-1', request_id: 'req-1' }) };
  const service = createGovernedAIService({ telemetry, approval, pool });

  const response = await service.chat(tenantId, 'user-1', [{ content: 'Hello' }]);
  assert.equal(response.status, 'approval_required');
  assert.equal(response.riskLevel, 'high');
  assert.ok(response.approvalId);
});

test('governed AI service chat completes for low risk with skipGovernance', async () => {
  const { pool } = createMockPool();
  const telemetry = { emit: async () => ({}) };
  const approval = { create: async () => ({}) };
  const service = createGovernedAIService({ telemetry, approval, pool });

  const response = await service.chat(tenantId, 'user-1', [{ content: 'Hello' }], { skipGovernance: true });
  assert.equal(response.status, 'completed');
  assert.ok(response.content);
  assert.equal(response.metadata.approvalStatus, 'auto_approved');
});

test('governed AI service requires tenant transaction context', async () => {
  const telemetry = { emit: async () => ({}) };
  const approval = { create: async () => ({}) };
  const service = createGovernedAIService({ telemetry, approval, pool: null });

  await assert.rejects(() => service.getActiveConfig(tenantId), /pg Pool is required/);
});
