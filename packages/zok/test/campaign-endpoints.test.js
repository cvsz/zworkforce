import { after, test } from 'node:test';
import assert from 'node:assert/strict';
import { mkdtemp, readFile, readdir, rm, writeFile } from 'node:fs/promises';
import { pbkdf2Sync } from 'node:crypto';
import os from 'node:os';
import path from 'node:path';
import {
  applyCampaignWorkersMigration,
  applyInitialMigration,
  applyRelationalIntegrityMigration,
  applyTenantIsolationMigration,
  executeSql,
  rollbackCampaignWorkersMigration,
  rollbackRelationalIntegrityMigration,
  rollbackTenantIsolationMigration,
} from '../scripts/postgres-migrations.js';

const password = 'test-campaign-endpoints';
const tenantId = 'dddddddd-4444-4444-8444-dddddddddddd';
const testDirectory = await mkdtemp(path.join(os.tmpdir(), 'zok-campaign-endpoints-'));
const databaseFile = path.join(testDirectory, 'db.json');
const salt = 'test-salt-campaigns';
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

test('campaign endpoints work in JSON mode', async () => {
  const login = await fetch(`${baseUrl}/api/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email: 'admin@example.test', password }),
  });
  assert.equal(login.status, 200);
  const setCookie = login.headers.get('set-cookie');
  const cookies = `zok_session=${cookieValue(setCookie, 'zok_session')}; zok_csrf=${cookieValue(setCookie, 'zok_csrf')}`;
  const csrf = cookieValue(setCookie, 'zok_csrf');
  const headers = { Cookie: cookies, 'X-CSRF-Token': csrf, 'Content-Type': 'application/json' };

  const campaign = await fetch(`${baseUrl}/api/campaigns`, {
    method: 'POST',
    headers,
    body: JSON.stringify({ name: 'Endpoint Test Campaign', channel: 'line', target: 'Test' }),
  });
  assert.equal(campaign.status, 201);
  const campaignData = await campaign.json();
  const campaignId = String(campaignData.id);

  const start = await fetch(`${baseUrl}/api/campaigns/${campaignId}/start`, {
    method: 'POST',
    headers,
  });
  assert.equal(start.status, 200);
  const started = await start.json();
  assert.equal(started.status, 'running');

  const pause = await fetch(`${baseUrl}/api/campaigns/${campaignId}/pause`, {
    method: 'POST',
    headers,
  });
  assert.equal(pause.status, 200);
  const paused = await pause.json();
  assert.equal(paused.status, 'paused');

  const resume = await fetch(`${baseUrl}/api/campaigns/${campaignId}/resume`, {
    method: 'POST',
    headers,
  });
  assert.equal(resume.status, 200);
  const resumed = await resume.json();
  assert.equal(resumed.status, 'running');

  const executions = await fetch(`${baseUrl}/api/campaigns/${campaignId}/executions`, {
    headers,
  });
  assert.equal(executions.status, 200);
  const executionsData = await executions.json();
  assert.ok('executions' in executionsData);
  assert.ok('deadLetters' in executionsData);

  const health = await fetch(`${baseUrl}/api/campaigns/workers/health`, {
    headers,
  });
  assert.equal(health.status, 200);
  const healthData = await health.json();
  assert.ok('status' in healthData);
  assert.equal(healthData.status, 'disabled');
});

test('campaign endpoints require authentication', async () => {
  const health = await fetch(`${baseUrl}/api/campaigns/workers/health`);
  assert.equal(health.status, 401);
});

test('campaign endpoints validate campaign id', async () => {
  const login = await fetch(`${baseUrl}/api/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email: 'admin@example.test', password }),
  });
  assert.equal(login.status, 200);
  const setCookie = login.headers.get('set-cookie');
  const cookies = `zok_session=${cookieValue(setCookie, 'zok_session')}; zok_csrf=${cookieValue(setCookie, 'zok_csrf')}`;
  const csrf = cookieValue(setCookie, 'zok_csrf');
  const headers = { Cookie: cookies, 'X-CSRF-Token': csrf, 'Content-Type': 'application/json' };

  const start = await fetch(`${baseUrl}/api/campaigns/does-not-exist/start`, {
    method: 'POST',
    headers,
  });
  assert.equal(start.status, 404);
});

after(async () => {
  await new Promise(resolve => server.close(resolve));
  await rm(testDirectory, { recursive: true, force: true });
  delete process.env.ZOK_CHAT_STORAGE;
  delete process.env.ZOK_POSTGRES_URL;
});
