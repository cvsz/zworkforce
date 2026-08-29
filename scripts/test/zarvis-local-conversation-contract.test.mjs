import assert from 'node:assert/strict';
import test from 'node:test';

import {
  validateRuntimeListeners,
  validateStaticContract,
} from '../validate-zarvis-local-conversation.mjs';

test('local conversation files satisfy the canonical topology contract', () => {
  const result = validateStaticContract();
  assert.deepEqual(result.errors, []);
  assert.equal(result.contract.domain, 'voice.zarvis.zeaz.dev');
  assert.equal(result.contract.defaultModel, 'qwen3:8b');
});

test('runtime validation accepts the five loopback listeners', () => {
  const { contract } = validateStaticContract();
  const output = [
    'LISTEN 0 4096 127.0.0.1:8443 0.0.0.0:*',
    'LISTEN 0 4096 127.0.0.1:11434 0.0.0.0:*',
    'LISTEN 0 4096 127.0.0.1:8094 0.0.0.0:*',
    'LISTEN 0 4096 127.0.0.1:8450 0.0.0.0:*',
    'LISTEN 0 4096 127.0.0.1:3023 0.0.0.0:*',
  ].join('\n');

  const result = validateRuntimeListeners(contract, output);
  assert.deepEqual(result.errors, []);
});

test('runtime validation rejects wildcard exposure', () => {
  const { contract } = validateStaticContract();
  const output = [
    'LISTEN 0 4096 127.0.0.1:8443 0.0.0.0:*',
    'LISTEN 0 4096 0.0.0.0:11434 0.0.0.0:*',
    'LISTEN 0 4096 127.0.0.1:8094 0.0.0.0:*',
    'LISTEN 0 4096 127.0.0.1:8450 0.0.0.0:*',
    'LISTEN 0 4096 127.0.0.1:3023 0.0.0.0:*',
  ].join('\n');

  const result = validateRuntimeListeners(contract, output);
  assert(result.errors.some((error) => error.includes('ollama has unsafe listener 0.0.0.0:11434')));
});

test('runtime validation rejects a missing required listener', () => {
  const { contract } = validateStaticContract();
  const output = [
    'LISTEN 0 4096 127.0.0.1:8443 0.0.0.0:*',
    'LISTEN 0 4096 127.0.0.1:11434 0.0.0.0:*',
    'LISTEN 0 4096 127.0.0.1:8094 0.0.0.0:*',
    'LISTEN 0 4096 127.0.0.1:3023 0.0.0.0:*',
  ].join('\n');

  const result = validateRuntimeListeners(contract, output);
  assert(result.errors.some((error) => error.includes('voice-gateway is not listening on 127.0.0.1:8450')));
});
