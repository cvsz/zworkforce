import assert from 'node:assert/strict';
import { test } from 'node:test';
import { once } from 'node:events';

import { createGatewayApp } from '../index.js';

function createRedisStub() {
  return {
    on() {},
    async srandmember(key) {
      assert.equal(key, 'provider:anthropic:active_keys');
      return 'anthropic-provider-key';
    },
    async srem() {},
    async set() {},
    async sadd() {}
  };
}

function createSilentLogger() {
  return {
    child() {
      return this;
    },
    levels: {
      values: {
        debug: 20,
        error: 50,
        fatal: 60,
        info: 30,
        trace: 10,
        warn: 40
      }
    },
    debug() {},
    error() {},
    fatal() {},
    info() {},
    trace() {},
    warn() {}
  };
}

function restoreEnv(name, value) {
  if (value === undefined) {
    delete process.env[name];
  } else {
    process.env[name] = value;
  }
}

async function postJson(port, path, body, headers = {}) {
  const response = await fetch(`http://127.0.0.1:${port}${path}`, {
    method: 'POST',
    headers: {
      authorization: 'Bearer test-service-token',
      'content-type': 'application/json',
      ...headers
    },
    body: JSON.stringify(body)
  });
  return {
    status: response.status,
    headers: response.headers,
    body: await response.json()
  };
}

test('Anthropic Messages transport forwards latest message options and provider headers', async () => {
  const previousEnv = {
    token: process.env.Z_PLATFORM_SERVICE_TOKEN,
    upstream: process.env.ANTHROPIC_UPSTREAM_BASE_URL,
    version: process.env.ANTHROPIC_VERSION,
    beta: process.env.ANTHROPIC_BETA
  };
  process.env.Z_PLATFORM_SERVICE_TOKEN = 'test-service-token';
  process.env.ANTHROPIC_UPSTREAM_BASE_URL = 'https://anthropic.test/v1';
  process.env.ANTHROPIC_VERSION = '2023-06-01';
  process.env.ANTHROPIC_BETA = 'messages-2026-01-01';
  let server;
  const upstreamCalls = [];

  try {
    const fetchImpl = async (url, options = {}) => {
      upstreamCalls.push({ url, options, body: JSON.parse(options.body) });
      return new Response(JSON.stringify({
        id: 'msg_test',
        type: 'message',
        role: 'assistant',
        content: [{ type: 'text', text: 'ok' }],
        model: 'claude-sonnet-5',
        stop_reason: 'end_turn',
        usage: { input_tokens: 10, output_tokens: 2 }
      }), {
        status: 200,
        headers: {
          'content-type': 'application/json',
          'request-id': 'req_test'
        }
      });
    };

    const { app } = createGatewayApp({
      redis: createRedisStub(),
      fetchImpl,
      logger: createSilentLogger()
    });

    server = app.listen(0);
    await once(server, 'listening');
    const { port } = server.address();
    const requestBody = {
      model: 'claude-sonnet-5',
      max_tokens: 1024,
      messages: [{ role: 'user', content: [{ type: 'text', text: 'Hello' }] }],
      metadata: { user_id: 'tenant-user-1' },
      mcp_servers: [{ type: 'url', url: 'https://mcp.example.invalid', name: 'docs' }],
      service_tier: 'auto',
      stop_sequences: ['</done>'],
      stream: false,
      system: [{ type: 'text', text: 'Answer tersely.' }],
      temperature: 0.2,
      thinking: { type: 'adaptive', display: 'omitted' },
      tool_choice: { type: 'auto' },
      tools: [{
        name: 'lookup',
        description: 'Look up a controlled fixture.',
        input_schema: {
          type: 'object',
          properties: { query: { type: 'string' } },
          required: ['query']
        }
      }],
      top_k: 40,
      top_p: 0.9
    };

    const response = await postJson(port, '/v1/messages', requestBody);

    assert.equal(response.status, 200);
    assert.equal(response.headers.get('request-id'), 'req_test');
    assert.deepEqual(response.body.content, [{ type: 'text', text: 'ok' }]);
    assert.equal(upstreamCalls.length, 1);
    assert.equal(upstreamCalls[0].url, 'https://anthropic.test/v1/messages');
    assert.deepEqual(upstreamCalls[0].body, requestBody);
    assert.equal(upstreamCalls[0].options.headers['x-api-key'], 'anthropic-provider-key');
    assert.equal(upstreamCalls[0].options.headers['anthropic-version'], '2023-06-01');
    assert.equal(upstreamCalls[0].options.headers['anthropic-beta'], 'messages-2026-01-01');
    assert.equal(upstreamCalls[0].options.headers.authorization, undefined);
  } finally {
    restoreEnv('Z_PLATFORM_SERVICE_TOKEN', previousEnv.token);
    restoreEnv('ANTHROPIC_UPSTREAM_BASE_URL', previousEnv.upstream);
    restoreEnv('ANTHROPIC_VERSION', previousEnv.version);
    restoreEnv('ANTHROPIC_BETA', previousEnv.beta);
    if (server) await new Promise((resolve) => server.close(resolve));
  }
});

test('Anthropic Messages transport rejects malformed requests before upstream selection', async () => {
  const previousToken = process.env.Z_PLATFORM_SERVICE_TOKEN;
  process.env.Z_PLATFORM_SERVICE_TOKEN = 'test-service-token';
  let server;

  try {
    const { app } = createGatewayApp({
      redis: createRedisStub(),
      fetchImpl: async () => {
        throw new Error('fetch should not be called for invalid message requests');
      },
      logger: createSilentLogger()
    });

    server = app.listen(0);
    await once(server, 'listening');
    const { port } = server.address();

    const missingMaxTokens = await postJson(port, '/v1/messages', {
      model: 'claude-sonnet-5',
      messages: [{ role: 'user', content: 'Hello' }]
    });
    assert.equal(missingMaxTokens.status, 400);
    assert.equal(missingMaxTokens.body.error.code, 'BAD_REQUEST');

    const missingMessages = await postJson(port, '/v1/messages', {
      model: 'claude-sonnet-5',
      max_tokens: 1024
    });
    assert.equal(missingMessages.status, 400);
    assert.equal(missingMessages.body.error.code, 'BAD_REQUEST');
  } finally {
    restoreEnv('Z_PLATFORM_SERVICE_TOKEN', previousToken);
    if (server) await new Promise((resolve) => server.close(resolve));
  }
});

test('Gateway isolates provider key selection per tenant and fails closed when AI_GATEWAY_REQUIRE_TENANT is enabled', async () => {
  const previousToken = process.env.Z_PLATFORM_SERVICE_TOKEN;
  const previousRequireTenant = process.env.AI_GATEWAY_REQUIRE_TENANT;
  const previousAllowShared = process.env.AI_GATEWAY_ALLOW_SHARED_PROVIDER_KEYS;
  process.env.Z_PLATFORM_SERVICE_TOKEN = 'test-service-token';
  process.env.AI_GATEWAY_REQUIRE_TENANT = 'true';
  process.env.AI_GATEWAY_ALLOW_SHARED_PROVIDER_KEYS = 'false';
  let server;
  const lookedUpPools = [];
  const usedApiKeys = [];

  try {
    const redis = {
      on() {},
      async srandmember(pool) {
        lookedUpPools.push(pool);
        if (pool === 'tenant:acme:provider:anthropic:active_keys') {
          return 'acme-dedicated-anthropic-key';
        }
        return null;
      },
      async srem() {},
      async set() {},
      async sadd() {}
    };

    const { app } = createGatewayApp({
      redis,
      fetchImpl: async (_url, options = {}) => {
        usedApiKeys.push(options.headers['x-api-key']);
        return new Response(JSON.stringify({ id: 'msg_acme', content: [] }), {
          status: 200,
          headers: { 'content-type': 'application/json' }
        });
      },
      logger: createSilentLogger()
    });

    server = app.listen(0);
    await once(server, 'listening');
    const { port } = server.address();

    const missingTenant = await postJson(port, '/v1/messages', {
      model: 'claude-sonnet-5',
      max_tokens: 64,
      messages: [{ role: 'user', content: 'hi' }]
    });
    assert.equal(missingTenant.status, 403);
    assert.equal(missingTenant.body.error.code, 'TENANT_REQUIRED');

    const unprovisionedTenant = await postJson(port, '/v1/messages', {
      model: 'claude-sonnet-5',
      max_tokens: 64,
      messages: [{ role: 'user', content: 'hi' }]
    }, { 'x-authenticated-tenant': 'other-tenant' });
    assert.equal(unprovisionedTenant.status, 503);

    const acmeResponse = await postJson(port, '/v1/messages', {
      model: 'claude-sonnet-5',
      max_tokens: 64,
      messages: [{ role: 'user', content: 'hi' }]
    }, { 'x-authenticated-tenant': 'acme' });
    assert.equal(acmeResponse.status, 200);
    assert.equal(acmeResponse.headers.get('x-tenant-id'), 'acme');
    assert.deepEqual(usedApiKeys, ['acme-dedicated-anthropic-key']);
    assert.ok(lookedUpPools.includes('tenant:acme:provider:anthropic:active_keys'));
  } finally {
    restoreEnv('Z_PLATFORM_SERVICE_TOKEN', previousToken);
    restoreEnv('AI_GATEWAY_REQUIRE_TENANT', previousRequireTenant);
    restoreEnv('AI_GATEWAY_ALLOW_SHARED_PROVIDER_KEYS', previousAllowShared);
    if (server) await new Promise((resolve) => server.close(resolve));
  }
});
