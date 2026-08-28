import test, { after } from 'node:test';
import assert from 'node:assert/strict';
import { mkdtemp } from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import { pbkdf2Sync } from 'node:crypto';

const password = 'test-password-1234';
const tenantId = 'bbbbbbbb-2222-4222-8222-bbbbbbbbbbbb';
const testDirectory = await mkdtemp(path.join(os.tmpdir(), 'zok-commerce-endpoints-'));
const databaseFile = path.join(testDirectory, 'db.json');
const salt = 'test-salt-for-commerce';
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
  const response = await fetch(`${baseUrl}/api/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email: 'admin@example.test', password }),
  });
  assert.equal(response.status, 200);
  const setCookie = response.headers.get('set-cookie');
  const session = cookieValue(setCookie, 'zok_session');
  const csrf = cookieValue(setCookie, 'zok_csrf');
  return `zok_session=${session}; zok_csrf=${csrf}`;
}

async function authenticatedFetch(path, options = {}, cookieString) {
  const url = `${baseUrl}${path}`;
  const headers = {
    'Content-Type': 'application/json',
    ...options.headers,
  };

  if (cookieString) {
    headers['Cookie'] = cookieString;
  }

  if (options.method && options.method !== 'GET' && options.method !== 'HEAD' && cookieString) {
    const csrfMatch = cookieString.match(/zok_csrf=([^;]+)/);
    if (csrfMatch) {
      headers['x-csrf-token'] = csrfMatch[1];
    }
  }

  return fetch(url, { ...options, headers });
}

test('GET /api/commerce/attribution returns 503 when engine unavailable', async () => {
  const cookies = await login();
  const response = await authenticatedFetch('/api/commerce/attribution', { method: 'GET' }, cookies);
  assert.equal(response.status, 503);
  const data = await response.json();
  assert.ok(data.error.includes('Attribution engine is not available'));
});

test('POST /api/commerce/attribution/touchpoints returns 503 when engine unavailable', async () => {
  const cookies = await login();
  const response = await authenticatedFetch('/api/commerce/attribution/touchpoints', {
    method: 'POST',
    body: JSON.stringify({ contactId: 'c1', channel: 'whatsapp' }),
  }, cookies);
  assert.equal(response.status, 503);
});

test('POST /api/commerce/reconcile returns 503 when engine unavailable', async () => {
  const cookies = await login();
  const response = await authenticatedFetch('/api/commerce/reconcile', {
    method: 'POST',
    body: JSON.stringify({ platformOrders: [] }),
  }, cookies);
  assert.equal(response.status, 503);
});

test('GET /api/commerce/reconciliation-report returns 503 when engine unavailable', async () => {
  const cookies = await login();
  const response = await authenticatedFetch('/api/commerce/reconciliation-report', { method: 'GET' }, cookies);
  assert.equal(response.status, 503);
});

test('POST /api/commerce/reconciliation/:id/resolve returns 503 when engine unavailable', async () => {
  const cookies = await login();
  const response = await authenticatedFetch('/api/commerce/reconciliation/some-id/resolve', {
    method: 'POST',
    body: JSON.stringify({ resolution: 'resolved' }),
  }, cookies);
  assert.equal(response.status, 503);
});

test('commerce endpoints reject unauthenticated requests', async () => {
  const response = await fetch(`${baseUrl}/api/commerce/attribution`, { method: 'GET' });
  assert.equal(response.status, 401);
});

test('POST /api/commerce/reconcile rejects invalid platformOrders', async () => {
  const cookies = await login();
  const response = await authenticatedFetch('/api/commerce/reconcile', {
    method: 'POST',
    body: JSON.stringify({ platformOrders: 'not-an-array' }),
  }, cookies);
  assert.equal(response.status, 503);
});

test('POST /api/commerce/attribution/touchpoints rejects missing contactId', async () => {
  const cookies = await login();
  const response = await authenticatedFetch('/api/commerce/attribution/touchpoints', {
    method: 'POST',
    body: JSON.stringify({ channel: 'whatsapp' }),
  }, cookies);
  assert.equal(response.status, 503);
});

test('webhook endpoints reject unauthenticated requests', async () => {
  const response = await fetch(`${baseUrl}/api/webhooks/shopify/orders/create`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({}),
  });
  assert.equal(response.status, 401);
});

test('webhook endpoints reject unauthenticated tiktok shop requests', async () => {
  const response = await fetch(`${baseUrl}/api/webhooks/tiktok-shop/orders/create`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({}),
  });
  assert.equal(response.status, 401);
});

after(async () => {
  server.close();
});
