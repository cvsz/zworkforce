import { after, test } from 'node:test';
import assert from 'node:assert/strict';
import { mkdtemp, rm } from 'node:fs/promises';
import { pbkdf2Sync } from 'node:crypto';
import os from 'node:os';
import path from 'node:path';

const password = 'test-password-1234';
const tenantId = 'bbbbbbbb-2222-4222-8222-bbbbbbbbbbbb';
const testDirectory = await mkdtemp(path.join(os.tmpdir(), 'zok-ai-'));
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

test('AI endpoints require authentication', async () => {
  const configRes = await fetch(`${baseUrl}/api/ai/config`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: '{}' });
  assert.equal(configRes.status, 401);

  const chatRes = await fetch(`${baseUrl}/api/ai/chat`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: '{}' });
  assert.equal(chatRes.status, 401);

  const approvalsRes = await fetch(`${baseUrl}/api/ai/approvals`);
  assert.equal(approvalsRes.status, 401);

  const telemetryRes = await fetch(`${baseUrl}/api/ai/telemetry`);
  assert.equal(telemetryRes.status, 401);
});

test('AI endpoints reject CSRF-missing requests', async () => {
  const login = await fetch(`${baseUrl}/api/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email: 'admin@example.test', password }),
  });
  const setCookie = login.headers.get('set-cookie');
  const cookies = `zok_session=${cookieValue(setCookie, 'zok_session')}; zok_csrf=${cookieValue(setCookie, 'zok_csrf')}`;

  const noCsrf = await fetch(`${baseUrl}/api/ai/config`, {
    method: 'POST',
    headers: { Cookie: cookies, 'Content-Type': 'application/json' },
    body: JSON.stringify({ config: { model: 'gpt-4', temperature: 0.7, max_tokens: 1024, system_prompt: 'Hi' } }),
  });
  assert.equal(noCsrf.status, 403);
});

test('POST /api/ai/chat rejects empty messages', async () => {
  const { cookies, csrf } = await login();

  const bad = await fetch(`${baseUrl}/api/ai/chat`, {
    method: 'POST',
    headers: {
      Cookie: cookies,
      'X-CSRF-Token': csrf,
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ messages: [] }),
  });
  assert.ok([400, 503].includes(bad.status), `expected 400 or 503, got ${bad.status}`);
});

test('Governed AI endpoints return 503 when PostgreSQL is not configured', async () => {
  const { cookies, csrf } = await login();

  const configRes = await fetch(`${baseUrl}/api/ai/config`, {
    method: 'POST',
    headers: {
      Cookie: cookies,
      'X-CSRF-Token': csrf,
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ config: { model: 'gpt-4', temperature: 0.7, max_tokens: 1024, system_prompt: 'Hi' }, risk_level: 'low' }),
  });
  assert.equal(configRes.status, 503);
  const configBody = await configRes.json();
  assert.equal(configBody.error, 'Governed AI service is not available');

  const chatRes = await fetch(`${baseUrl}/api/ai/chat`, {
    method: 'POST',
    headers: {
      Cookie: cookies,
      'X-CSRF-Token': csrf,
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ messages: [{ content: 'Hello' }] }),
  });
  assert.equal(chatRes.status, 503);
  const chatBody = await chatRes.json();
  assert.equal(chatBody.error, 'Governed AI service is not available');

  const approvalsRes = await fetch(`${baseUrl}/api/ai/approvals`, {
    headers: { Cookie: cookies },
  });
  assert.equal(approvalsRes.status, 503);

  const telemetryRes = await fetch(`${baseUrl}/api/ai/telemetry`, {
    headers: { Cookie: cookies },
  });
  assert.equal(telemetryRes.status, 503);
});

after(async () => {
  await new Promise(resolve => server.close(resolve));
  await rm(testDirectory, { recursive: true, force: true });
});
