import { after, test } from 'node:test';
import assert from 'node:assert/strict';
import { mkdtemp, readFile, readdir, rm, writeFile } from 'node:fs/promises';
import { pbkdf2Sync } from 'node:crypto';
import os from 'node:os';
import path from 'node:path';
import {
  applyInitialMigration,
  applyRateLimitRecordsMigration,
  applyRelationalIntegrityMigration,
  applyTenantIsolationMigration,
  executeSql,
  rollbackInitialMigration,
  rollbackRateLimitRecordsMigration,
  rollbackRelationalIntegrityMigration,
  rollbackTenantIsolationMigration,
} from '../scripts/postgres-migrations.js';

const password = 'test-password-1234';
const tenantId = 'bbbbbbbb-2222-4222-8222-bbbbbbbbbbbb';
const testDirectory = await mkdtemp(path.join(os.tmpdir(), 'zok-api-'));
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

test('API release hardening protects and validates the real request path', async () => {
  const health = await fetch(`${baseUrl}/api/health`);
  assert.equal(health.status, 200);
  assert.deepEqual(await health.json(), {
    status: 'ok',
    service: 'zok-api',
    environment: 'test',
    dependencies: {
      database: 'ok',
      postgres: 'disabled',
      sessionStore: 'disabled',
      rateLimitStore: 'disabled',
      auditService: 'disabled',
      channelAdapters: 'simulated',
      adapterHealth: {
        whatsapp: { status: 'ok', provider: 'whatsapp', mode: 'simulated' },
        line: { status: 'ok', provider: 'line', mode: 'simulated' },
        messenger: { status: 'ok', provider: 'messenger', mode: 'simulated' },
        tiktok: { status: 'ok', provider: 'tiktok', mode: 'simulated' },
      },
    },
  });
  assert.equal(health.headers.get('x-content-type-options'), 'nosniff');
  assert.equal(health.headers.get('x-frame-options'), 'DENY');
  assert.equal(health.headers.get('cache-control'), 'no-store');

  const blockedOrigin = await fetch(`${baseUrl}/api/health`, {
    headers: { Origin: 'https://untrusted.example' },
  });
  assert.equal(blockedOrigin.status, 403);

  const malformedJson = await fetch(`${baseUrl}/api/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: '{"email":',
  });
  assert.equal(malformedJson.status, 400);
  assert.deepEqual(await malformedJson.json(), { error: 'Request body must be valid JSON' });

  const unauthenticated = await fetch(`${baseUrl}/api/chats`);
  assert.equal(unauthenticated.status, 401);

  const badLogin = await fetch(`${baseUrl}/api/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email: 'admin@example.test', password: 'wrong-password' }),
  });
  assert.equal(badLogin.status, 401);

  const login = await fetch(`${baseUrl}/api/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email: 'admin@example.test', password }),
  });
  assert.equal(login.status, 200);
  assert.deepEqual((await login.json()).user, { email: 'admin@example.test', role: 'owner', tenantId });

  const setCookie = login.headers.get('set-cookie');
  assert.ok(setCookie);
  const cookies = `zok_session=${cookieValue(setCookie, 'zok_session')}; zok_csrf=${cookieValue(setCookie, 'zok_csrf')}`;
  const authenticatedHeaders = { Cookie: cookies };

  const me = await fetch(`${baseUrl}/api/auth/me`, { headers: authenticatedHeaders });
  assert.equal(me.status, 200);
  assert.deepEqual((await me.json()).user, { email: 'admin@example.test', role: 'owner', tenantId });

  const chats = await fetch(`${baseUrl}/api/chats`, { headers: authenticatedHeaders });
  assert.equal(chats.status, 200);
  assert.ok(Array.isArray(await chats.json()));

  const malformedCookie = await fetch(`${baseUrl}/api/chats`, {
    headers: { Cookie: 'zok_session=%E0%A4%A' },
  });
  assert.equal(malformedCookie.status, 401);

  const csrf = cookieValue(setCookie, 'zok_csrf');
  const unverifiedIntegration = await fetch(`${baseUrl}/api/integrations/shopify/toggle`, {
    method: 'POST',
    headers: { ...authenticatedHeaders, 'X-CSRF-Token': csrf },
  });
  assert.equal(unverifiedIntegration.status, 409);

  const missingCsrf = await fetch(`${baseUrl}/api/chats/1/tags`, {
    method: 'POST',
    headers: { ...authenticatedHeaders, 'Content-Type': 'application/json' },
    body: JSON.stringify({ tags: ['verified'] }),
  });
  assert.equal(missingCsrf.status, 403);

  const update = await fetch(`${baseUrl}/api/chats/1/tags`, {
    method: 'POST',
    headers: {
      ...authenticatedHeaders,
      'Content-Type': 'application/json',
      'X-CSRF-Token': csrf,
    },
    body: JSON.stringify({ tags: ['verified', 'release-test'] }),
  });
  assert.equal(update.status, 200);
  assert.deepEqual((await update.json()).details.tags, ['verified', 'release-test']);

  const invalidId = await fetch(`${baseUrl}/api/chats/not-an-id/tags`, {
    method: 'POST',
    headers: {
      ...authenticatedHeaders,
      'Content-Type': 'application/json',
      'X-CSRF-Token': csrf,
    },
    body: JSON.stringify({ tags: [] }),
  });
  assert.equal(invalidId.status, 400);

  const persisted = JSON.parse(await readFile(databaseFile, 'utf8'));
  assert.deepEqual(persisted.chats[0].details.tags, ['verified', 'release-test']);

  const concurrentCampaigns = await Promise.all(
    Array.from({ length: 20 }, (_, index) => fetch(`${baseUrl}/api/campaigns`, {
      method: 'POST',
      headers: {
        ...authenticatedHeaders,
        'Content-Type': 'application/json',
        'X-CSRF-Token': csrf,
      },
      body: JSON.stringify({
        name: `Concurrent release check ${index}`,
        channel: 'line',
        target: 'release-test',
      }),
    })),
  );
  assert.ok(concurrentCampaigns.every(response => response.status === 201));
  const afterConcurrentWrites = JSON.parse(await readFile(databaseFile, 'utf8'));
  assert.equal(afterConcurrentWrites.campaigns.length, 23);
  assert.equal((await readdir(testDirectory)).filter(name => name.endsWith('.tmp')).length, 0);

  await writeFile(databaseFile, '{"broken": true', 'utf8');
  const degradedHealth = await fetch(`${baseUrl}/api/health`);
  assert.equal(degradedHealth.status, 503);
  assert.deepEqual(await degradedHealth.json(), {
    status: 'degraded',
    service: 'zok-api',
    environment: 'test',
    dependencies: {
      database: 'error',
      postgres: 'disabled',
      sessionStore: 'disabled',
      rateLimitStore: 'disabled',
      auditService: 'disabled',
      channelAdapters: 'simulated',
    },
  });
  assert.equal(await readFile(databaseFile, 'utf8'), '{"broken": true');
  await writeFile(databaseFile, JSON.stringify(afterConcurrentWrites, null, 2), 'utf8');

  const logout = await fetch(`${baseUrl}/api/auth/logout`, {
    method: 'POST',
    headers: { ...authenticatedHeaders, 'X-CSRF-Token': csrf },
  });
  assert.equal(logout.status, 204);

  const afterLogout = await fetch(`${baseUrl}/api/chats`, { headers: authenticatedHeaders });
  assert.equal(afterLogout.status, 401);
});

test('PostgreSQL mode does not mutate JSON for campaigns, integrations, ai-config, and flow-nodes routes', {
  skip: process.env.ZOK_POSTGRES_TEST_URL ? false : 'ZOK_POSTGRES_TEST_URL is not configured',
}, async () => {
  const appPassword = 'zok-json-immutability-test';
  const databaseUrl = process.env.ZOK_POSTGRES_TEST_URL;
  const adminUrl = new URL(databaseUrl);
  adminUrl.pathname = '/postgres';
  const isolatedUrl = new URL(databaseUrl);
  isolatedUrl.pathname = '/zok_json_immutability_test';
  const appUrl = new URL(isolatedUrl);
  appUrl.username = 'zok_json_immutability_test';
  appUrl.password = appPassword;

  await executeSql(adminUrl.toString(), 'DROP DATABASE IF EXISTS zok_json_immutability_test WITH (FORCE);');
  await executeSql(adminUrl.toString(), 'DROP ROLE IF EXISTS zok_json_immutability_test;');
  await executeSql(adminUrl.toString(), 'CREATE DATABASE zok_json_immutability_test;');
  await applyInitialMigration(isolatedUrl.toString());

  await executeSql(isolatedUrl.toString(), `
    INSERT INTO tenants (id, slug, name) VALUES ('${tenantId}', 'json-immutability', 'JSON Immutability');
    CREATE ROLE zok_json_immutability_test LOGIN PASSWORD '${appPassword}' NOSUPERUSER NOBYPASSRLS;
    GRANT USAGE ON SCHEMA public TO zok_json_immutability_test;
    GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO zok_json_immutability_test;
  `);
  await applyTenantIsolationMigration(isolatedUrl.toString());
  await applyRelationalIntegrityMigration(isolatedUrl.toString());

  const testDir = await mkdtemp(path.join(os.tmpdir(), 'zok-json-immutable-'));
  const dbFile = path.join(testDir, 'db.json');
  await writeFile(dbFile, JSON.stringify({
    chats: [],
    aiConfig: { agentName: 'Original', persona: 'sales', knowledgeBase: 'Original KB', qaPairs: [] },
    flowNodes: [],
    campaigns: [],
    integrations: [],
    syncLogs: [],
  }, null, 2), 'utf8');

  process.env.ZOK_DB_FILE = dbFile;
  process.env.ZOK_CHAT_STORAGE = 'postgres';
  process.env.ZOK_POSTGRES_URL = appUrl.toString();

  let postgresServer;
  try {
    const { startServer } = await import('../server.js');
    postgresServer = startServer(0);
    await new Promise(resolve => postgresServer.once('listening', resolve));
    const baseUrl = `http://127.0.0.1:${postgresServer.address().port}`;

    const login = await fetch(`${baseUrl}/api/auth/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email: 'admin@example.test', password }),
    });
    assert.equal(login.status, 200);
    const setCookie = login.headers.get('set-cookie');
    assert.ok(setCookie);
    const cookies = `zok_session=${cookieValue(setCookie, 'zok_session')}; zok_csrf=${cookieValue(setCookie, 'zok_csrf')}`;
    const csrf = cookieValue(setCookie, 'zok_csrf');
    const headers = { Cookie: cookies, 'X-CSRF-Token': csrf, 'Content-Type': 'application/json' };

    const beforeJson = JSON.parse(await readFile(dbFile, 'utf8'));

    const campaigns = await fetch(`${baseUrl}/api/campaigns`, { headers: { Cookie: cookies } });
    assert.equal(campaigns.status, 200);

    const createCampaign = await fetch(`${baseUrl}/api/campaigns`, {
      method: 'POST',
      headers,
      body: JSON.stringify({ name: 'Postgres Campaign', channel: 'line', target: 'Test' }),
    });
    assert.equal(createCampaign.status, 201);

    const integrations = await fetch(`${baseUrl}/api/integrations`, { headers: { Cookie: cookies } });
    assert.equal(integrations.status, 200);

    const aiConfig = await fetch(`${baseUrl}/api/ai-config`, { headers: { Cookie: cookies } });
    assert.equal(aiConfig.status, 200);

    const updateAiConfig = await fetch(`${baseUrl}/api/ai-config`, {
      method: 'POST',
      headers,
      body: JSON.stringify({ agentName: 'New Agent', persona: 'support', knowledgeBase: 'New KB', qaPairs: [] }),
    });
    assert.equal(updateAiConfig.status, 200);

    const flowNodes = await fetch(`${baseUrl}/api/flow-nodes`, { headers: { Cookie: cookies } });
    assert.equal(flowNodes.status, 200);

    const updateFlowNodes = await fetch(`${baseUrl}/api/flow-nodes`, {
      method: 'POST',
      headers,
      body: JSON.stringify([{ id: 'node-1', type: 'trigger', title: 'T', x: 0, y: 0, details: {} }]),
    });
    assert.equal(updateFlowNodes.status, 200);

    const afterJson = JSON.parse(await readFile(dbFile, 'utf8'));
    assert.deepEqual(afterJson, beforeJson, 'JSON storage must not mutate when PostgreSQL mode is active');
  } finally {
    if (postgresServer) await new Promise(resolve => postgresServer.close(resolve));
    await rm(testDir, { recursive: true, force: true });
    await rollbackRelationalIntegrityMigration(isolatedUrl.toString()).catch(() => undefined);
    await rollbackTenantIsolationMigration(isolatedUrl.toString()).catch(() => undefined);
    await rollbackInitialMigration(isolatedUrl.toString()).catch(() => undefined);
    await executeSql(adminUrl.toString(), 'DROP DATABASE IF EXISTS zok_json_immutability_test WITH (FORCE);').catch(() => undefined);
    await executeSql(adminUrl.toString(), 'DROP ROLE IF EXISTS zok_json_immutability_test;').catch(() => undefined);
    delete process.env.ZOK_CHAT_STORAGE;
    delete process.env.ZOK_POSTGRES_URL;
  }
});

test('PostgreSQL session store persists sessions across process restarts', {
  skip: process.env.ZOK_POSTGRES_TEST_URL ? false : 'ZOK_POSTGRES_TEST_URL is not configured',
}, async () => {
  const appPassword = 'zok-session-persistence-test';
  const databaseUrl = process.env.ZOK_POSTGRES_TEST_URL;
  const adminUrl = new URL(databaseUrl);
  adminUrl.pathname = '/postgres';
  const isolatedUrl = new URL(databaseUrl);
  isolatedUrl.pathname = '/zok_session_persistence_test';
  const appUrl = new URL(isolatedUrl);
  appUrl.username = 'zok_session_persistence_test';
  appUrl.password = appPassword;

  const sessionTenantId = 'cccccccc-3333-4333-8333-cccccccccccc';

  await executeSql(adminUrl.toString(), 'DROP DATABASE IF EXISTS zok_session_persistence_test WITH (FORCE);');
  await executeSql(adminUrl.toString(), 'DROP ROLE IF EXISTS zok_session_persistence_test;');
  await executeSql(adminUrl.toString(), 'CREATE DATABASE zok_session_persistence_test;');
  await applyInitialMigration(isolatedUrl.toString());

  await executeSql(isolatedUrl.toString(), `
    INSERT INTO tenants (id, slug, name) VALUES ('${sessionTenantId}', 'session-persistence', 'Session Persistence');
    INSERT INTO users (tenant_id, email, display_name, password_hash, status)
      VALUES ('${sessionTenantId}', 'admin@example.test', 'Admin', '', 'active');
    CREATE ROLE zok_session_persistence_test LOGIN PASSWORD '${appPassword}' NOSUPERUSER NOBYPASSRLS;
    GRANT USAGE ON SCHEMA public TO zok_session_persistence_test;
    GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO zok_session_persistence_test;
  `);
  await applyTenantIsolationMigration(isolatedUrl.toString());
  await applyRelationalIntegrityMigration(isolatedUrl.toString());

  const testDir = await mkdtemp(path.join(os.tmpdir(), 'zok-session-persist-'));
  const dbFile = path.join(testDir, 'db.json');
  await writeFile(dbFile, JSON.stringify({
    chats: [],
    aiConfig: { agentName: 'Original', persona: 'sales', knowledgeBase: 'Original KB', qaPairs: [] },
    flowNodes: [],
    campaigns: [],
    integrations: [],
    syncLogs: [],
  }, null, 2), 'utf8');

  process.env.ZOK_DB_FILE = dbFile;
  process.env.ZOK_CHAT_STORAGE = 'postgres';
  process.env.ZOK_POSTGRES_URL = appUrl.toString();
  process.env.ZOK_SESSION_STORE = 'postgres';

  let postgresServer;
  let sessionCookie;
  let csrfToken;
  try {
    const { startServer } = await import(`../server.js?session-persistence-1=${Date.now()}`);
    postgresServer = startServer(0);
    await new Promise(resolve => postgresServer.once('listening', resolve));
    const baseUrl = `http://127.0.0.1:${postgresServer.address().port}`;

    const login = await fetch(`${baseUrl}/api/auth/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email: 'admin@example.test', password }),
    });
    assert.equal(login.status, 200, 'login should succeed in postgres session mode');
    const setCookie = login.headers.get('set-cookie');
    assert.ok(setCookie);
    sessionCookie = `zok_session=${cookieValue(setCookie, 'zok_session')}`;
    csrfToken = cookieValue(setCookie, 'zok_csrf');

    const me = await fetch(`${baseUrl}/api/auth/me`, {
      headers: { Cookie: `${sessionCookie}; zok_csrf=${csrfToken}` },
    });
    assert.equal(me.status, 200, 'auth/me should work with postgres session');
    assert.deepEqual((await me.json()).user, { email: 'admin@example.test', role: 'owner', tenantId: sessionTenantId });
  } finally {
    if (postgresServer) await new Promise(resolve => postgresServer.close(resolve));
    delete process.env.ZOK_SESSION_STORE;
  }

  let postgresServer2;
  try {
    const { startServer } = await import(`../server.js?session-persistence-2=${Date.now()}`);
    postgresServer2 = startServer(0);
    await new Promise(resolve => postgresServer2.once('listening', resolve));
    const baseUrl = `http://127.0.0.1:${postgresServer2.address().port}`;

    const meAfterRestart = await fetch(`${baseUrl}/api/auth/me`, {
      headers: { Cookie: `${sessionCookie}; zok_csrf=${csrfToken}` },
    });
    assert.equal(meAfterRestart.status, 200, 'session should persist across server restart');
    assert.deepEqual((await meAfterRestart.json()).user, { email: 'admin@example.test', role: 'owner', tenantId: sessionTenantId });
  } finally {
    if (postgresServer2) await new Promise(resolve => postgresServer2.close(resolve));
    await rm(testDir, { recursive: true, force: true });
    await rollbackRelationalIntegrityMigration(isolatedUrl.toString()).catch(() => undefined);
    await rollbackTenantIsolationMigration(isolatedUrl.toString()).catch(() => undefined);
    await rollbackInitialMigration(isolatedUrl.toString()).catch(() => undefined);
    await executeSql(adminUrl.toString(), 'DROP DATABASE IF EXISTS zok_session_persistence_test WITH (FORCE);').catch(() => undefined);
    await executeSql(adminUrl.toString(), 'DROP ROLE IF EXISTS zok_session_persistence_test;').catch(() => undefined);
    delete process.env.ZOK_CHAT_STORAGE;
    delete process.env.ZOK_POSTGRES_URL;
  }
});

test('PostgreSQL rate-limit store blocks excess requests and preserves standard headers', {
  skip: process.env.ZOK_POSTGRES_TEST_URL ? false : 'ZOK_POSTGRES_TEST_URL is not configured',
}, async () => {
  const appPassword = 'zok-rate-limit-test';
  const databaseUrl = process.env.ZOK_POSTGRES_TEST_URL;
  const adminUrl = new URL(databaseUrl);
  adminUrl.pathname = '/postgres';
  const isolatedUrl = new URL(databaseUrl);
  isolatedUrl.pathname = '/zok_rate_limit_test';
  const appUrl = new URL(isolatedUrl);
  appUrl.username = 'zok_rate_limit_test';
  appUrl.password = appPassword;

  await executeSql(adminUrl.toString(), 'DROP DATABASE IF EXISTS zok_rate_limit_test WITH (FORCE);');
  await executeSql(adminUrl.toString(), 'DROP ROLE IF EXISTS zok_rate_limit_test;');
  await executeSql(adminUrl.toString(), 'CREATE DATABASE zok_rate_limit_test;');
  await applyInitialMigration(isolatedUrl.toString());
  await applyRateLimitRecordsMigration(isolatedUrl.toString());

  await executeSql(isolatedUrl.toString(), `
    INSERT INTO tenants (id, slug, name) VALUES ('${tenantId}', 'rate-limit', 'Rate Limit');
    CREATE ROLE zok_rate_limit_test LOGIN PASSWORD '${appPassword}' NOSUPERUSER NOBYPASSRLS;
    GRANT USAGE ON SCHEMA public TO zok_rate_limit_test;
    GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO zok_rate_limit_test;
  `);
  await applyTenantIsolationMigration(isolatedUrl.toString());
  await applyRelationalIntegrityMigration(isolatedUrl.toString());

  const testDir = await mkdtemp(path.join(os.tmpdir(), 'zok-rate-limit-'));
  const dbFile = path.join(testDir, 'db.json');
  await writeFile(dbFile, JSON.stringify({
    chats: [],
    aiConfig: { agentName: 'Original', persona: 'sales', knowledgeBase: 'Original KB', qaPairs: [] },
    flowNodes: [],
    campaigns: [],
    integrations: [],
    syncLogs: [],
  }, null, 2), 'utf8');

  process.env.ZOK_DB_FILE = dbFile;
  process.env.ZOK_CHAT_STORAGE = 'postgres';
  process.env.ZOK_POSTGRES_URL = appUrl.toString();
  process.env.ZOK_RATE_LIMIT_STORE = 'postgres';

  let postgresServer;
  try {
    const { startServer } = await import('../server.js');
    postgresServer = startServer(0);
    await new Promise(resolve => postgresServer.once('listening', resolve));
    const baseUrl = `http://127.0.0.1:${postgresServer.address().port}`;

    const login = await fetch(`${baseUrl}/api/auth/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email: 'admin@example.test', password }),
    });
    assert.equal(login.status, 200);
    const setCookie = login.headers.get('set-cookie');
    assert.ok(setCookie);

    const health = await fetch(`${baseUrl}/api/health`);
    assert.equal(health.status, 200);
    assert.equal(health.headers.get('rate-limit-limit'), '180');
    assert.equal(health.headers.get('rate-limit-remaining'), '179');

    const burst = [];
    for (let i = 0; i < 180; i += 1) {
      burst.push(fetch(`${baseUrl}/api/health`));
    }
    const burstResults = await Promise.all(burst);
    const allowed = burstResults.filter((r) => r.status === 200);
    const blocked = burstResults.filter((r) => r.status === 429);
    assert.ok(allowed.length > 0, 'first burst requests should be allowed');
    assert.ok(blocked.length > 0, 'excess requests should be rate limited');
    const firstBlocked = blocked[0];
    assert.equal(firstBlocked.headers.get('rate-limit-limit'), '180');
    assert.equal(firstBlocked.headers.get('rate-limit-remaining'), '0');
    assert.ok(firstBlocked.headers.get('retry-after'));

    const afterBurst = await fetch(`${baseUrl}/api/health`);
    assert.equal(afterBurst.status, 429);
  } finally {
    if (postgresServer) await new Promise(resolve => postgresServer.close(resolve));
    await rm(testDir, { recursive: true, force: true });
    await rollbackRateLimitRecordsMigration(isolatedUrl.toString()).catch(() => undefined);
    await rollbackRelationalIntegrityMigration(isolatedUrl.toString()).catch(() => undefined);
    await rollbackTenantIsolationMigration(isolatedUrl.toString()).catch(() => undefined);
    await rollbackInitialMigration(isolatedUrl.toString()).catch(() => undefined);
    await executeSql(adminUrl.toString(), 'DROP DATABASE IF EXISTS zok_rate_limit_test WITH (FORCE);').catch(() => undefined);
    await executeSql(adminUrl.toString(), 'DROP ROLE IF EXISTS zok_rate_limit_test;').catch(() => undefined);
    delete process.env.ZOK_CHAT_STORAGE;
    delete process.env.ZOK_POSTGRES_URL;
    delete process.env.ZOK_RATE_LIMIT_STORE;
  }
});

after(async () => {
  await new Promise(resolve => server.close(resolve));
  await rm(testDirectory, { recursive: true, force: true });
});
