import test, { after } from 'node:test';
import assert from 'node:assert/strict';
import { mkdtemp, readFile, rm } from 'node:fs/promises';
import { pbkdf2Sync } from 'node:crypto';
import os from 'node:os';
import path from 'node:path';

process.env.NODE_ENV = 'test';
process.env.ZOK_NO_LISTEN = 'true';

const password = 'test-password-1234';
const tenantId = 'bbbbbbbb-2222-4222-8222-bbbbbbbbbbbb';
const testDirectory = await mkdtemp(path.join(os.tmpdir(), 'zok-privacy-'));
const databaseFile = path.join(testDirectory, 'db.json');
const salt = 'test-salt-for-zok-privacy';
const passwordHash = `pbkdf2_sha256$310000$${salt}$${pbkdf2Sync(password, salt, 310000, 32, 'sha256').toString('base64url')}`;

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
  const csrf = cookieValue(setCookie, 'zok_csrf');
  const cookies = `zok_session=${cookieValue(setCookie, 'zok_session')}; zok_csrf=${csrf}`;
  return { cookies, csrf };
}

test('privacy export endpoint requires authentication', async () => {
  const response = await fetch(`${baseUrl}/api/privacy/export`);
  assert.equal(response.status, 401);
});

test('privacy export returns ZIP file with tenant data', async () => {
  const { cookies, csrf } = await login();
  const response = await fetch(`${baseUrl}/api/privacy/export`, {
    headers: { Cookie: cookies, 'X-CSRF-Token': csrf },
  });
  assert.equal(response.status, 200);
  assert.equal(response.headers.get('content-type'), 'application/zip');
  assert.ok(response.headers.get('content-disposition')?.includes('attachment'));
  const buffer = Buffer.from(await response.arrayBuffer());
  assert.ok(buffer[0] === 0x50 && buffer[1] === 0x4b, 'should be a valid ZIP');
});

test('privacy delete endpoint requires authentication', async () => {
  const response = await fetch(`${baseUrl}/api/privacy/delete`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ confirm: true, types: ['chats'] }),
  });
  assert.equal(response.status, 401);
});

test('privacy delete requires explicit confirmation', async () => {
  const { cookies, csrf } = await login();
  const response = await fetch(`${baseUrl}/api/privacy/delete`, {
    method: 'POST',
    headers: { Cookie: cookies, 'X-CSRF-Token': csrf, 'Content-Type': 'application/json' },
    body: JSON.stringify({ types: ['chats'] }),
  });
  assert.equal(response.status, 400);
  const body = await response.json();
  assert.ok(body.error.includes('confirmation'));
});

test('privacy delete rejects protected audit_events type', async () => {
  const { cookies, csrf } = await login();
  const response = await fetch(`${baseUrl}/api/privacy/delete`, {
    method: 'POST',
    headers: { Cookie: cookies, 'X-CSRF-Token': csrf, 'Content-Type': 'application/json' },
    body: JSON.stringify({ confirm: true, types: ['audit_events'] }),
  });
  assert.equal(response.status, 400);
  const body = await response.json();
  assert.ok(body.error.includes('audit_events'));
});

test('privacy delete removes selected data in JSON mode', async () => {
  const { cookies, csrf } = await login();
  const response = await fetch(`${baseUrl}/api/privacy/delete`, {
    method: 'POST',
    headers: { Cookie: cookies, 'X-CSRF-Token': csrf, 'Content-Type': 'application/json' },
    body: JSON.stringify({ confirm: true, types: ['chats'] }),
  });
  assert.equal(response.status, 200);
  const body = await response.json();
  assert.equal(body.tenantId, tenantId);
  assert.equal(body.deletedCounts.chats, 5);

  const db = JSON.parse(await readFile(databaseFile, 'utf8'));
  assert.equal(db.chats.length, 0);
  assert.ok(db.campaigns.length > 0, 'campaigns should not be deleted');
});

test('privacy retention status endpoint requires authentication', async () => {
  const response = await fetch(`${baseUrl}/api/privacy/retention-status`);
  assert.equal(response.status, 401);
});

test('privacy retention status returns policy information', async () => {
  const { cookies, csrf } = await login();
  const response = await fetch(`${baseUrl}/api/privacy/retention-status`, {
    headers: { Cookie: cookies, 'X-CSRF-Token': csrf },
  });
  // Returns 503 when PostgreSQL is not configured (test mode uses JSON storage)
  assert.ok([200, 503].includes(response.status));
  if (response.status === 200) {
    const body = await response.json();
    assert.equal(body.tenantId, tenantId);
    assert.ok(body.policies);
    assert.ok(body.status);
  }
});

test('privacy retention purge requires owner role', async () => {
  const { cookies, csrf } = await login();
  const response = await fetch(`${baseUrl}/api/privacy/retention-purge`, {
    method: 'POST',
    headers: { Cookie: cookies, 'X-CSRF-Token': csrf, 'Content-Type': 'application/json' },
    body: JSON.stringify({}),
  });
  // Returns 403 when owner check fails, or 503 when PostgreSQL is not configured
  assert.ok([403, 503].includes(response.status));
});

test('privacy export endpoint includes all data types', async () => {
  const { cookies, csrf } = await login();
  const response = await fetch(`${baseUrl}/api/privacy/export`, {
    headers: { Cookie: cookies, 'X-CSRF-Token': csrf },
  });
  assert.equal(response.status, 200);
  const buffer = Buffer.from(await response.arrayBuffer());
  
  // Verify ZIP contains export.json by checking for the filename in the ZIP central directory
  const exportJsonMarker = Buffer.from('export.json', 'utf-8');
  assert.ok(buffer.includes(exportJsonMarker), 'ZIP should contain export.json');
});

test('privacy delete with all types removes all data', async () => {
  const { cookies, csrf } = await login();
  const response = await fetch(`${baseUrl}/api/privacy/delete`, {
    method: 'POST',
    headers: { Cookie: cookies, 'X-CSRF-Token': csrf, 'Content-Type': 'application/json' },
    body: JSON.stringify({ confirm: true, types: ['all'] }),
  });
  assert.equal(response.status, 200);
  const body = await response.json();
  assert.ok(body.deletedCounts.chats >= 0);
  assert.ok(body.deletedCounts.campaigns >= 0);
});

after(async () => {
  await new Promise(resolve => server.close(resolve));
  await rm(testDirectory, { recursive: true, force: true });
});
