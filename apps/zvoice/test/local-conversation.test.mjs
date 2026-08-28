import assert from 'node:assert/strict';
import test from 'node:test';
import {
  classifyLocalConversation,
  executeLocalConversation,
  LocalConversationError,
  validateLocalLlmBaseUrl,
} from '../local-conversation.mjs';

test('local LLM URL accepts only allowlisted local HTTP hosts', () => {
  assert.equal(validateLocalLlmBaseUrl('http://ollama:11434/v1').hostname, 'ollama');
  assert.equal(validateLocalLlmBaseUrl('http://127.0.0.1:11434/v1').hostname, '127.0.0.1');
  assert.throws(
    () => validateLocalLlmBaseUrl('https://api.openai.com/v1'),
    (error) => error instanceof LocalConversationError && error.code === 'non_local_llm_denied',
  );
  assert.throws(
    () => validateLocalLlmBaseUrl('http://example.com/v1'),
    (error) => error instanceof LocalConversationError && error.code === 'non_local_llm_denied',
  );
});

test('Thai and English mutation requests are classified before inference', () => {
  assert.equal(classifyLocalConversation('ช่วยลบไฟล์นี้').mutation_requested, true);
  assert.equal(classifyLocalConversation('restart the service').mutation_requested, true);
  assert.equal(classifyLocalConversation('วันนี้อากาศเป็นอย่างไร').mutation_requested, false);
});

test('mutation request returns approval_required without calling the LLM', async () => {
  let calls = 0;
  const result = await executeLocalConversation({
    commandId: 'command-1',
    sessionId: 'session-1',
    text: 'ช่วยรีสตาร์ตระบบให้หน่อย',
    locale: 'th-TH',
  }, {
    baseUrl: 'http://ollama:11434/v1',
    fetchImpl: async () => {
      calls += 1;
      throw new Error('must not be called');
    },
  });

  assert.equal(calls, 0);
  assert.equal(result.status, 'approval_required');
  assert.equal(result.safety.owner_approval_required, true);
  assert.equal(result.safety.mutation_executed, false);
});

test('ordinary conversation uses only the configured local Ollama endpoint', async () => {
  let captured;
  const result = await executeLocalConversation({
    commandId: 'command-2',
    sessionId: 'session-1',
    text: 'อธิบาย event-driven architecture แบบสั้น',
    locale: 'th-TH',
  }, {
    baseUrl: 'http://ollama:11434/v1',
    model: 'qwen3:8b',
    apiKey: 'local-only-token',
    fetchImpl: async (url, options) => {
      captured = { url: String(url), options, body: JSON.parse(options.body) };
      return new Response(JSON.stringify({
        choices: [{ message: { content: 'เป็นสถาปัตยกรรมที่ส่วนต่าง ๆ สื่อสารกันผ่านเหตุการณ์' } }],
      }), { status: 200, headers: { 'content-type': 'application/json' } });
    },
  });

  assert.equal(captured.url, 'http://ollama:11434/v1/chat/completions');
  assert.equal(captured.body.model, 'qwen3:8b');
  assert.equal(captured.options.redirect, 'error');
  assert.equal(result.intent.name, 'local.conversation.respond');
  assert.equal(result.result.local_only, true);
  assert.equal(result.result.mutation_executed, false);
  assert.equal(JSON.stringify(result).includes('local-only-token'), false);
});
