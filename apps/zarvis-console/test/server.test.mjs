import assert from 'node:assert/strict';
import { once } from 'node:events';
import { createServer } from 'node:http';
import test from 'node:test';
import {
  createZarvisConsoleServer,
  ZARVIS_OWNER_GITHUB_ID,
} from '../server.mjs';

const EDGE_SECRET = 'edge-secret-0123456789-0123456789';
const SERVICE_TOKEN = 'service-token-0123456789-0123456789';

function ownerHeaders(extra = {}) {
  return {
    'x-zarvis-owner-id': ZARVIS_OWNER_GITHUB_ID,
    'x-zarvis-edge-secret': EDGE_SECRET,
    ...extra,
  };
}

function createConsole(options = {}) {
  return createZarvisConsoleServer({
    edgeSharedSecret: EDGE_SECRET,
    orchestratorServiceToken: SERVICE_TOKEN,
    logger: { error() {} },
    ...options,
  });
}

async function listen(server) {
  server.listen(0, '127.0.0.1');
  await once(server, 'listening');
  const address = server.address();
  return `http://127.0.0.1:${address.port}`;
}

test('console fails closed when owner secrets are not configured', () => {
  assert.throws(() => createZarvisConsoleServer(), /ZARVIS_EDGE_SHARED_SECRET/);
});

test('console rejects all non-health routes without the immutable owner assertion', async (t) => {
  const server = createConsole();
  const baseUrl = await listen(server);
  t.after(() => server.close());

  const response = await fetch(baseUrl);
  assert.equal(response.status, 403);
  assert.equal((await response.json()).error.code, 'owner_access_denied');
});

test('console serves the command center only to the configured owner', async (t) => {
  const server = createConsole();
  const baseUrl = await listen(server);
  t.after(() => server.close());

  const response = await fetch(baseUrl, { headers: ownerHeaders() });
  assert.equal(response.status, 200);
  assert.match(response.headers.get('content-security-policy'), /default-src 'self'/);
  assert.match(await response.text(), /Z\.A\.R\.V\.I\.S\./);
});

test('console replaces browser identity headers with the fixed owner service identity', async (t) => {
  let observedHeaders;
  let observedPath;
  const upstream = createServer(async (request, response) => {
    observedHeaders = request.headers;
    observedPath = request.url;
    const chunks = [];
    for await (const chunk of request) chunks.push(chunk);
    response.writeHead(200, { 'content-type': 'application/json' });
    response.end(JSON.stringify({ status: 'completed', received: JSON.parse(Buffer.concat(chunks)) }));
  });
  const upstreamUrl = await listen(upstream);
  t.after(() => upstream.close());

  const consoleServer = createConsole({ orchestratorUrl: upstreamUrl });
  const consoleUrl = await listen(consoleServer);
  t.after(() => consoleServer.close());

  const payload = { session_id: 'session-1', input: { modality: 'text', text: 'status' } };
  const response = await fetch(`${consoleUrl}/api/command`, {
    method: 'POST',
    headers: ownerHeaders({
      'content-type': 'application/json',
      'x-user-id': 'attacker',
      'x-tenant-id': 'attacker',
      authorization: 'Bearer browser-secret',
    }),
    body: JSON.stringify(payload),
  });

  assert.equal(response.status, 200);
  assert.equal(observedPath, '/v1/commands');
  assert.equal(observedHeaders.authorization, undefined);
  assert.equal(observedHeaders['x-zarvis-owner-id'], ZARVIS_OWNER_GITHUB_ID);
  assert.equal(observedHeaders['x-zarvis-service-token'], SERVICE_TOKEN);
  assert.equal(observedHeaders['x-user-id'], `github:${ZARVIS_OWNER_GITHUB_ID}`);
  assert.equal(observedHeaders['x-tenant-id'], `owner-${ZARVIS_OWNER_GITHUB_ID}`);
  assert.deepEqual((await response.json()).received, payload);
});

test('console rejects non-JSON command bodies after owner authentication', async (t) => {
  const server = createConsole();
  const baseUrl = await listen(server);
  t.after(() => server.close());

  const response = await fetch(`${baseUrl}/api/command`, {
    method: 'POST',
    headers: ownerHeaders({ 'content-type': 'text/plain' }),
    body: 'hello',
  });
  assert.equal(response.status, 415);
});
