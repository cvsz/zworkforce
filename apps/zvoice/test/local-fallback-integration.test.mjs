import assert from 'node:assert/strict';
import test from 'node:test';
import {
  createZarvisCommand,
  healthSnapshot,
  ZARVIS_OWNER_GITHUB_ID,
} from '../server.mjs';

const EDGE_SECRET = 'edge-secret-0123456789-012345678901';
const OWNER_ENV = {
  ZVOICE_ZARVIS_MODE: 'true',
  ZARVIS_EDGE_SHARED_SECRET: EDGE_SECRET,
  ZARVIS_ORCHESTRATOR_URL: 'http://zarvis-orchestrator:8094',
  ZARVIS_ORCHESTRATOR_SERVICE_TOKEN: 'orchestrator-token-0123456789-012345',
  ZARVIS_LOCAL_LLM_BASE_URL: 'http://ollama:11434/v1',
  ZARVIS_LOCAL_LLM_MODEL: 'qwen3:8b',
  ZARVIS_LOCAL_LLM_API_KEY: 'local-ollama-token',
};

const REQUEST = {
  headers: {
    'x-zarvis-owner-id': ZARVIS_OWNER_GITHUB_ID,
    'x-zarvis-edge-secret': EDGE_SECRET,
  },
};

test('health reports configured local-only conversation without exposing credentials', () => {
  const health = healthSnapshot(OWNER_ENV);
  assert.equal(health.local_conversation_configured, true);
  assert.equal(health.local_llm_only, true);
  assert.equal(health.local_llm_model, 'qwen3:8b');
  assert.equal(JSON.stringify(health).includes(EDGE_SECRET), false);
  assert.equal(JSON.stringify(health).includes('local-ollama-token'), false);
});

test('unsupported read-only conversation falls back to local Ollama', async () => {
  const calls = [];
  const result = await createZarvisCommand({
    command_id: 'command-local-1',
    session_id: 'session-local-1',
    transcript: 'ช่วยอธิบาย zero trust แบบสั้น',
    locale: 'th-TH',
  }, REQUEST, OWNER_ENV, async (url, options) => {
    calls.push({ url: String(url), options });
    if (calls.length === 1) {
      return new Response(JSON.stringify({
        error: { code: 'unsupported_intent', message: 'No tool intent resolved.' },
      }), { status: 400, headers: { 'content-type': 'application/json' } });
    }
    return new Response(JSON.stringify({
      choices: [{ message: { content: 'Zero Trust คือการตรวจสอบทุกคำขอและไม่เชื่อถือโดยอัตโนมัติ' } }],
    }), { status: 200, headers: { 'content-type': 'application/json' } });
  });

  assert.equal(calls.length, 2);
  assert.equal(calls[0].url, 'http://zarvis-orchestrator:8094/v1/commands');
  assert.equal(calls[1].url, 'http://ollama:11434/v1/chat/completions');
  assert.equal(result.status, 'completed');
  assert.equal(result.intent.source, 'local_fallback');
  assert.equal(result.result.local_only, true);
});

test('unsupported mutating speech requires approval and never calls Ollama', async () => {
  const calls = [];
  const result = await createZarvisCommand({
    command_id: 'command-local-2',
    session_id: 'session-local-1',
    transcript: 'ช่วยรีสตาร์ตเซิร์ฟเวอร์ให้หน่อย',
    locale: 'th-TH',
  }, REQUEST, OWNER_ENV, async (url) => {
    calls.push(String(url));
    return new Response(JSON.stringify({
      error: { code: 'unsupported_intent', message: 'No tool intent resolved.' },
    }), { status: 400, headers: { 'content-type': 'application/json' } });
  });

  assert.deepEqual(calls, ['http://zarvis-orchestrator:8094/v1/commands']);
  assert.equal(result.status, 'approval_required');
  assert.equal(result.safety.owner_approval_required, true);
  assert.equal(result.safety.mutation_executed, false);
});
