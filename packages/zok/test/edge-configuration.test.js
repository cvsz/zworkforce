import { after, test } from 'node:test';
import assert from 'node:assert/strict';
import { mkdtemp, rm } from 'node:fs/promises';
import { pbkdf2Sync } from 'node:crypto';
import os from 'node:os';
import path from 'node:path';

const password = 'test-edge-password-1234';
const tenantId = 'bbbbbbbb-2222-4222-8222-bbbbbbbbbbbb';
const testDirectory = await mkdtemp(path.join(os.tmpdir(), 'zok-edge-'));
const databaseFile = path.join(testDirectory, 'db.json');
const salt = 'test-salt-edge-config';
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

async function login() {
  const login = await fetch(`${baseUrl}/api/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email: 'admin@example.test', password }),
  });
  assert.equal(login.status, 200);
  const setCookie = login.headers.get('set-cookie');
  assert.ok(setCookie);
  const cookies = `zok_session=${cookieValue(setCookie, 'zok_session')}; zok_csrf=${cookieValue(setCookie, 'zok_csrf')}`;
  return { cookies, csrf: cookieValue(setCookie, 'zok_csrf') };
}

test('health live endpoint returns 200 when server is healthy', async () => {
  const response = await fetch(`${baseUrl}/health/live`);
  assert.equal(response.status, 200);
  const body = await response.json();
  assert.equal(body.status, 'healthy');
  assert.ok(body.checks);
  assert.ok(body.timestamp);
});

test('health ready endpoint returns 200 when dependencies are ready', async () => {
  const response = await fetch(`${baseUrl}/health/ready`);
  assert.equal(response.status, 200);
  const body = await response.json();
  assert.equal(body.status, 'ready');
  assert.ok(body.checks.database);
  assert.ok(body.checks.postgres);
  assert.ok(body.checks.sessionStore);
  assert.ok(body.checks.rateLimitStore);
  assert.ok(body.checks.auditService);
});

test('POST /admin/rollback creates a rollback record', async () => {
  const { cookies, csrf } = await login();

  const response = await fetch(`${baseUrl}/admin/rollback`, {
    method: 'POST',
    headers: {
      Cookie: cookies,
      'X-CSRF-Token': csrf,
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ flagName: 'test-flag', percentage: 30, reason: 'load testing' }),
  });

  assert.equal(response.status, 201);
  const body = await response.json();
  assert.equal(body.flagName, 'test-flag');
  assert.equal(body.rollbackPercentage, 30);
  assert.equal(body.reason, 'load testing');
  assert.equal(body.enabled, true);
});

test('GET /admin/rollback returns all rollback statuses', async () => {
  const { cookies } = await login();

  await fetch(`${baseUrl}/admin/rollback`, {
    method: 'POST',
    headers: {
      Cookie: cookies,
      'X-CSRF-Token': 'dummy',
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ flagName: 'list-test-flag', percentage: 10 }),
  });

  const response = await fetch(`${baseUrl}/admin/rollback`, {
    headers: { Cookie: cookies },
  });

  assert.equal(response.status, 200);
  const body = await response.json();
  assert.ok(Array.isArray(body));
  assert.ok(body.some(item => item.flagName === 'list-test-flag'));
});

test('GET /admin/rollback/:flagName returns specific status', async () => {
  const { cookies } = await login();

  const response = await fetch(`${baseUrl}/admin/rollback/list-test-flag`, {
    headers: { Cookie: cookies },
  });

  assert.equal(response.status, 200);
  const body = await response.json();
  assert.equal(body.flagName, 'list-test-flag');
  assert.equal(body.rollbackPercentage, 10);
});

test('POST /admin/rollback/:flagName/emergency performs emergency rollback', async () => {
  const { cookies, csrf } = await login();

  const response = await fetch(`${baseUrl}/admin/rollback/emergency-flag/emergency`, {
    method: 'POST',
    headers: {
      Cookie: cookies,
      'X-CSRF-Token': csrf,
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ reason: 'production outage' }),
  });

  assert.equal(response.status, 201);
  const body = await response.json();
  assert.equal(body.flagName, 'emergency-flag');
  assert.equal(body.enabled, false);
  assert.equal(body.rollbackPercentage, 100);
  assert.equal(body.reason, 'production outage');
});

test('admin rollback endpoints reject unauthenticated requests', async () => {
  const response = await fetch(`${baseUrl}/admin/rollback`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ flagName: 'unauth-flag', percentage: 10 }),
  });

  assert.equal(response.status, 401);
});

test('admin rollback endpoints reject non-owner requests', async () => {
  const response = await fetch(`${baseUrl}/admin/rollback`, {
    method: 'POST',
    headers: { Cookie: 'zok_session=invalid' },
    body: JSON.stringify({ flagName: 'owner-flag', percentage: 10 }),
  });

  assert.equal(response.status, 401);
});

test('POST /admin/rollback validates required fields', async () => {
  const { cookies, csrf } = await login();

  const response = await fetch(`${baseUrl}/admin/rollback`, {
    method: 'POST',
    headers: {
      Cookie: cookies,
      'X-CSRF-Token': csrf,
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({}),
  });

  assert.equal(response.status, 400);
  const body = await response.json();
  assert.ok(body.error.includes('flagName is required'));
});

test('POST /admin/rollback validates percentage bounds', async () => {
  const { cookies, csrf } = await login();

  const response = await fetch(`${baseUrl}/admin/rollback`, {
    method: 'POST',
    headers: {
      Cookie: cookies,
      'X-CSRF-Token': csrf,
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ flagName: 'bounds-flag', percentage: 150 }),
  });

  assert.equal(response.status, 400);
  const body = await response.json();
  assert.ok(body.error.includes('percentage must be an integer'));
});

after(async () => {
  await new Promise(resolve => server.close(resolve));
  await rm(testDirectory, { recursive: true, force: true });
});
