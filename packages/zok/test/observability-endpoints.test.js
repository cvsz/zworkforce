import { after, test } from 'node:test';
import assert from 'node:assert/strict';
import { mkdtemp, readFile, rm, writeFile } from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import { pbkdf2Sync } from 'node:crypto';

const password = 'test-password-1234';
const tenantId = 'bbbbbbbb-2222-4222-8222-bbbbbbbbbbbb';
const testDirectory = await mkdtemp(path.join(os.tmpdir(), 'zok-obs-'));
const databaseFile = path.join(testDirectory, 'db.json');
const salt = 'test-salt-for-zok';
const passwordHash = `pbkdf2_sha256$310000$${salt}$${pbkdf2Sync(password, salt, 310000, 32, 'sha256').toString('base64url')}`;

process.env.NODE_ENV = 'test';
process.env.ZOK_NO_LISTEN = 'true';
process.env.ZOK_DB_FILE = databaseFile;
process.env.ZOK_ADMIN_EMAIL = 'admin@example.test';
process.env.ZOK_ADMIN_PASSWORD_HASH = passwordHash;
process.env.ZOK_ADMIN_TENANT_ID = tenantId;
process.env.ZOK_ALLOWED_ORIGINS = 'http://127.0.0.1:5175';

const { startServer } = await import('../server.js');
const server = startServer(0);
await new Promise(resolve => server.once('listening', resolve));
const baseUrl = `http://127.0.0.1:${server.address().port}`;

function cookieValue(setCookieHeader, name) {
  const match = setCookieHeader.match(new RegExp(`${name}=([^;,]+)`));
  assert.ok(match, `Expected ${name} cookie`);
  return match[1];
}

test('health endpoint reports dependency status', async () => {
  const health = await fetch(`${baseUrl}/api/health`);
  assert.equal(health.status, 200);
  const body = await health.json();
  assert.equal(body.status, 'ok');
  assert.equal(body.service, 'zok-api');
  assert.equal(body.environment, 'test');
  assert.ok(body.dependencies);
  assert.equal(body.dependencies.database, 'ok');
  assert.ok(['connected', 'disabled'].includes(body.dependencies.postgres));
  assert.ok(['connected', 'disabled'].includes(body.dependencies.sessionStore));
  assert.ok(['connected', 'disabled'].includes(body.dependencies.rateLimitStore));
  assert.ok(['connected', 'disabled'].includes(body.dependencies.auditService));
});

test('metrics endpoint returns Prometheus format', async () => {
  const metrics = await fetch(`${baseUrl}/metrics`);
  assert.equal(metrics.status, 200);
  assert.ok(metrics.headers.get('content-type').startsWith('text/plain'));
  const body = await metrics.text();
  assert.ok(body.includes('# TYPE api_requests counter'));
  assert.ok(body.includes('# TYPE active_sessions gauge'));
  assert.ok(body.includes('# TYPE api_latency histogram'));
});

test('metrics endpoint tracks requests after calls', async () => {
  await fetch(`${baseUrl}/api/health`);
  const metrics = await fetch(`${baseUrl}/metrics`);
  const body = await metrics.text();
  assert.ok(body.includes('api_requests '));
});

test('request id and trace id headers are present on responses', async () => {
  const health = await fetch(`${baseUrl}/api/health`);
  const requestId = health.headers.get('x-request-id');
  const traceId = health.headers.get('x-trace-id');
  assert.ok(requestId, 'expected x-request-id header');
  assert.ok(traceId, 'expected x-trace-id header');
});

test('authenticated requests carry tenant and user context', async () => {
  const login = await fetch(`${baseUrl}/api/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email: 'admin@example.test', password }),
  });
  assert.equal(login.status, 200);
  const setCookie = login.headers.get('set-cookie');
  const cookies = `zok_session=${cookieValue(setCookie, 'zok_session')}; zok_csrf=${cookieValue(setCookie, 'zok_csrf')}`;

  const me = await fetch(`${baseUrl}/api/auth/me`, { headers: { Cookie: cookies } });
  assert.equal(me.status, 200);
  assert.ok(me.headers.get('x-request-id'));
  assert.ok(me.headers.get('x-trace-id'));
});

after(async () => {
  await new Promise(resolve => server.close(resolve));
  await rm(testDirectory, { recursive: true, force: true });
});
