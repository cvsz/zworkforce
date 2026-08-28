import test, { after } from 'node:test';
import assert from 'node:assert/strict';
import { mkdtemp } from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import { pbkdf2Sync } from 'node:crypto';

const password = 'test-password-1234';
const tenantId = 'bbbbbbbb-2222-4222-8222-bbbbbbbbbbbb';
const testDirectory = await mkdtemp(path.join(os.tmpdir(), 'zok-security-endpoints-'));
const databaseFile = path.join(testDirectory, 'db.json');
const salt = 'test-salt-for-security';
const passwordHash = `pbkdf2_sha256$310000$${salt}$${pbkdf2Sync(password, salt, 310000, 32, 'sha256').toString('base64url')}`;

process.env.NODE_ENV = 'test';
process.env.ZOK_NO_LISTEN = 'true';
process.env.ZOK_DB_FILE = databaseFile;
process.env.ZOK_ADMIN_EMAIL = 'admin@example.test';
process.env.ZOK_ADMIN_PASSWORD_HASH = passwordHash;
process.env.ZOK_ADMIN_TENANT_ID = tenantId;
process.env.ZOK_ALLOWED_ORIGINS = 'http://127.0.0.1:5175';
delete process.env.ZOK_SECRETS_MASTER_KEY;

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
  const response = await fetch(`${baseUrl}/api/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email: 'admin@example.test', password }),
  });
  assert.equal(response.status, 200);
  const setCookie = response.headers.get('set-cookie');
  return {
    cookie: `zok_session=${cookieValue(setCookie, 'zok_session')}; zok_csrf=${cookieValue(setCookie, 'zok_csrf')}`,
    csrf: cookieValue(setCookie, 'zok_csrf'),
  };
}

async function authedFetch(path, options = {}) {
  const { cookie, csrf } = await login();
  const headers = {
    'Content-Type': 'application/json',
    Cookie: cookie,
    ...options.headers,
  };
  if (options.method && options.method !== 'GET' && options.method !== 'HEAD') {
    headers['x-csrf-token'] = csrf;
  }
  return fetch(`${baseUrl}${path}`, { ...options, headers });
}

test('security endpoints reject unauthenticated requests with 401', async () => {
  const paths = [
    ['/api/security/api-keys', { method: 'GET' }],
    ['/api/security/api-keys', { method: 'POST', body: JSON.stringify({ name: 'k' }) }],
    ['/api/security/api-keys/aaaaaaaa-1111-4111-8111-aaaaaaaaaaaa/rotate', { method: 'POST', body: JSON.stringify({}) }],
    ['/api/security/api-keys/aaaaaaaa-1111-4111-8111-aaaaaaaaaaaa', { method: 'DELETE' }],
    ['/api/security/audit', { method: 'GET' }],
  ];

  for (const [path, options] of paths) {
    const response = await fetch(`${baseUrl}${path}`, {
      headers: { 'Content-Type': 'application/json' },
      ...options,
    });
    assert.equal(response.status, 401, `${options.method || 'GET'} ${path} should require auth`);
  }
});

test('security endpoints return 503 when postgres is unavailable', async () => {
  const list = await authedFetch('/api/security/api-keys');
  assert.equal(list.status, 503);
  assert.ok((await list.json()).error.includes('not available'));

  const create = await authedFetch('/api/security/api-keys', {
    method: 'POST',
    body: JSON.stringify({ name: 'Production' }),
  });
  assert.equal(create.status, 503);

  const rotate = await authedFetch('/api/security/api-keys/aaaaaaaa-1111-4111-8111-aaaaaaaaaaaa/rotate', {
    method: 'POST',
    body: JSON.stringify({}),
  });
  assert.equal(rotate.status, 503);

  const revoke = await authedFetch('/api/security/api-keys/aaaaaaaa-1111-4111-8111-aaaaaaaaaaaa', {
    method: 'DELETE',
  });
  assert.equal(revoke.status, 503);

  const audit = await authedFetch('/api/security/audit');
  assert.equal(audit.status, 503);
});

test('security endpoints reject requests without CSRF token', async () => {
  const { cookie } = await login();
  const response = await fetch(`${baseUrl}/api/security/api-keys`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', Cookie: cookie },
    body: JSON.stringify({ name: 'No CSRF' }),
  });
  assert.equal(response.status, 403);
});

after(async () => {
  server.close();
});
