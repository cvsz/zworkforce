import { test } from 'node:test';
import assert from 'node:assert/strict';
import { mkdtemp, rm, writeFile } from 'node:fs/promises';
import { pbkdf2Sync } from 'node:crypto';
import os from 'node:os';
import path from 'node:path';
import {
  applyInitialMigration,
  applyTenantIsolationMigration,
  applyRelationalIntegrityMigration,
  executeSql,
  rollbackInitialMigration,
  rollbackRelationalIntegrityMigration,
  rollbackTenantIsolationMigration,
} from '../scripts/postgres-migrations.js';

const password = 'test-audit-password-1234';
const tenantId = 'cccccccc-3333-4333-8333-cccccccccccc';
const databaseUrl = process.env.ZOK_POSTGRES_TEST_URL;

test('audit enforcement emits events for mutation routes when enabled', {
  skip: databaseUrl ? false : 'ZOK_POSTGRES_TEST_URL is not configured',
}, async () => {
  const adminUrl = new URL(databaseUrl);
  adminUrl.pathname = '/postgres';
  const isolatedUrl = new URL(databaseUrl);
  isolatedUrl.pathname = '/zok_audit_test';
  const appUrl = new URL(isolatedUrl.toString());
  appUrl.username = 'zok_audit_test';
  appUrl.password = 'zok-audit-test-pwd';

  await executeSql(adminUrl.toString(), 'DROP DATABASE IF EXISTS zok_audit_test WITH (FORCE);');
  await executeSql(adminUrl.toString(), 'DROP ROLE IF EXISTS zok_audit_test;');
  await executeSql(adminUrl.toString(), 'CREATE DATABASE zok_audit_test;');
  await applyInitialMigration(isolatedUrl.toString());

  await executeSql(isolatedUrl.toString(), `
    INSERT INTO tenants (id, slug, name) VALUES ('${tenantId}', 'audit-test', 'Audit Test');
    CREATE ROLE zok_audit_test LOGIN PASSWORD 'zok-audit-test-pwd' NOSUPERUSER NOBYPASSRLS;
    GRANT USAGE ON SCHEMA public TO zok_audit_test;
    GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO zok_audit_test;
  `);
  await applyTenantIsolationMigration(isolatedUrl.toString());
  await applyRelationalIntegrityMigration(isolatedUrl.toString());

  const testDir = await mkdtemp(path.join(os.tmpdir(), 'zok-audit-'));
  const dbFile = path.join(testDir, 'db.json');
  await writeFile(dbFile, JSON.stringify({
    chats: [],
    aiConfig: { agentName: 'Test', persona: 'sales', knowledgeBase: 'KB', qaPairs: [] },
    flowNodes: [],
    campaigns: [],
    integrations: [],
    syncLogs: [],
  }, null, 2), 'utf8');

  const salt = 'test-audit-salt';
  const passwordHash = `pbkdf2_sha256$310000$${salt}$${pbkdf2Sync(password, salt, 310000, 32, 'sha256').toString('base64url')}`;

  process.env.NODE_ENV = 'test';
  process.env.ZOK_NO_LISTEN = 'true';
  process.env.ZOK_DB_FILE = dbFile;
  process.env.ZOK_ADMIN_EMAIL = 'admin@example.test';
  process.env.ZOK_ADMIN_PASSWORD_HASH = passwordHash;
  process.env.ZOK_ADMIN_TENANT_ID = tenantId;
  process.env.ZOK_ALLOWED_ORIGINS = 'http://127.0.0.1:5175';
  process.env.ZOK_CHAT_STORAGE = 'postgres';
  process.env.ZOK_POSTGRES_URL = appUrl.toString();
  process.env.ZOK_AUDIT_ENFORCEMENT = 'enabled';

  let server;
  try {
    const { startServer } = await import('../server.js');
    server = startServer(0);
    await new Promise(resolve => server.once('listening', resolve));
    const baseUrl = `http://127.0.0.1:${server.address().port}`;

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
    const headers = {
      Cookie: cookies,
      'X-CSRF-Token': csrf,
      'Content-Type': 'application/json',
    };

    await fetch(`${baseUrl}/api/roles`, {
      method: 'POST',
      headers,
      body: JSON.stringify({ name: 'Audit Role', permissions: {} }),
    });

    await fetch(`${baseUrl}/api/campaigns`, {
      method: 'POST',
      headers,
      body: JSON.stringify({ name: 'Audit Campaign', channel: 'line', target: 'Test' }),
    });

    await fetch(`${baseUrl}/api/ai-config`, {
      method: 'POST',
      headers,
      body: JSON.stringify({ agentName: 'Audit Agent', persona: 'sales', knowledgeBase: 'KB', qaPairs: [] }),
    });

    const auditRows = await executeSql(isolatedUrl.toString(), `
      SELECT action, resource_type, resource_id, metadata
      FROM audit_events
      WHERE tenant_id = '${tenantId}'
      ORDER BY occurred_at ASC
    `);

    const lines = auditRows.split('\n').filter(line => line.trim());
    assert.ok(lines.length >= 4, `expected at least 4 audit events, got ${lines.length}`);

    const actions = lines.map(line => line.split('|')[0].trim());
    assert.ok(actions.includes('auth.login'), 'expected auth.login event');
    assert.ok(actions.includes('post'), 'expected post event for roles');
    assert.ok(actions.includes('post'), 'expected post event for campaigns');
    assert.ok(actions.includes('post'), 'expected post event for ai-config');
  } finally {
    if (server) await new Promise(resolve => server.close(resolve));
    await rm(testDir, { recursive: true, force: true });
    await rollbackRelationalIntegrityMigration(isolatedUrl.toString()).catch(() => undefined);
    await rollbackTenantIsolationMigration(isolatedUrl.toString()).catch(() => undefined);
    await rollbackInitialMigration(isolatedUrl.toString()).catch(() => undefined);
    await executeSql(adminUrl.toString(), 'DROP DATABASE IF EXISTS zok_audit_test WITH (FORCE);').catch(() => undefined);
    await executeSql(adminUrl.toString(), 'DROP ROLE IF EXISTS zok_audit_test;').catch(() => undefined);
    delete process.env.ZOK_CHAT_STORAGE;
    delete process.env.ZOK_POSTGRES_URL;
    delete process.env.ZOK_AUDIT_ENFORCEMENT;
  }
});

function cookieValue(setCookieHeader, name) {
  const match = setCookieHeader.match(new RegExp(`${name}=([^;,]+)`));
  assert.ok(match, `Expected ${name} cookie`);
  return match[1];
}
