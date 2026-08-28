import assert from 'node:assert/strict';
import http from 'node:http';
import { test } from 'node:test';
import { once } from 'node:events';

import { createGatewayApp } from '../index.js';

function createRedisStub() {
  return {
    on() {},
    async srandmember() {
      return 'provider-key';
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

test('client disconnect aborts the upstream request without retrying', async () => {
  const abortEvents = [];
  const fetchCalls = [];
  const previousToken = process.env.Z_PLATFORM_SERVICE_TOKEN;
  process.env.Z_PLATFORM_SERVICE_TOKEN = 'test-service-token';
  let server;

  try {
    let resolveFetchStarted;
    const fetchStarted = new Promise((resolve) => {
      resolveFetchStarted = resolve;
    });

    const fetchImpl = (_url, options = {}) => {
      fetchCalls.push(options);
      resolveFetchStarted();
      return new Promise((resolve, reject) => {
        options.signal?.addEventListener('abort', () => {
          abortEvents.push('abort');
          reject(new Error('aborted'));
        });
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

    const request = http.request({
      method: 'POST',
      port,
      path: '/v1/chat/completions',
      headers: {
        authorization: 'Bearer test-service-token',
        'content-type': 'application/json'
      }
    });

    request.write(JSON.stringify({ model: 'gpt-4o-mini', messages: [] }));
    request.end();

    await fetchStarted;
    const closed = new Promise((resolve) => request.once('close', resolve));
    request.once('error', () => {});
    request.destroy();

    await closed;
    await new Promise((resolve) => setTimeout(resolve, 50));

    assert.equal(fetchCalls.length, 1);
    assert.equal(abortEvents.length, 1);
  } finally {
    process.env.Z_PLATFORM_SERVICE_TOKEN = previousToken;
    if (server) {
      await new Promise((resolve) => server.close(resolve));
    }
  }
});
