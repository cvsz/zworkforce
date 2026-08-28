import test from 'node:test';
import assert from 'node:assert/strict';
import { once } from 'node:events';
import { mkdtemp, rm, writeFile } from 'node:fs/promises';
import { pbkdf2Sync } from 'node:crypto';
import os from 'node:os';
import path from 'node:path';
import {
  applyInitialMigration,
  applyRelationalIntegrityMigration,
  applyTenantIsolationMigration,
  executeSql,
  rollbackInitialMigration,
  rollbackRelationalIntegrityMigration,
  rollbackTenantIsolationMigration,
} from '../scripts/postgres-migrations.js';
import { createPostgresPool, createPostgresStorage } from '../server/storage/postgres-storage.js';
import { importLegacyChats } from '../server/storage/postgres/legacy-chat-import.js';

const databaseUrl = process.env.ZOK_POSTGRES_TEST_URL;
const tenantId = 'dddddddd-4444-4444-8444-dddddddddddd';
const password = 'cutover-rollback-test-1234';
const salt = 'cutover-rollback-test-salt';
const passwordHash = `pbkdf2_sha256$310000$${salt}$${pbkdf2Sync(password, salt, 310000, 32, 'sha256').toString('base64url')}`;
let moduleNonce = 0;

function sourceChat(id = 41, text = 'Imported PostgreSQL source message') {
  return {
    id,
    name: `Cutover Customer ${id}`,
    avatar: `C${id}`,
    channel: 'line',
    unread: 1,
    time: '09:00',
    messages: [{ sender: 'customer', text, time: '09:00' }],
    details: {
      phone: `+66 800 000 ${id}`,
      email: `cutover-${id}@example.test`,
      assigned: 'Admin',
      tags: ['cutover'],
      orders: [],
    },
  };
}

function databaseState(chats) {
  return {
    chats,
    aiConfig: {},
    flowNodes: [],
    campaigns: [],
    integrations: [],
    syncLogs: [],
  };
}

async function writeDatabase(filePath, chats) {
  await writeFile(filePath, `${JSON.stringify(databaseState(chats), null, 2)}\n`, 'utf8');
}

function cookieValue(setCookieHeader, name) {
  const match = setCookieHeader.match(new RegExp(`${name}=([^;,]+)`));
  assert.ok(match, `Expected ${name} cookie`);
  return match[1];
}

async function startConfiguredServer({ mode, databaseFile, postgresUrl }) {
  process.env.NODE_ENV = 'test';
  process.env.ZOK_NO_LISTEN = 'true';
  process.env.ZOK_DB_FILE = databaseFile;
  process.env.ZOK_ADMIN_EMAIL = 'admin@example.test';
  process.env.ZOK_ADMIN_PASSWORD_HASH = passwordHash;
  process.env.ZOK_ADMIN_TENANT_ID = tenantId;
  process.env.ZOK_ALLOWED_ORIGINS = 'http://127.0.0.1:5175';
  process.env.ZOK_CHAT_STORAGE = mode;
  if (postgresUrl) process.env.ZOK_POSTGRES_URL = postgresUrl;
  else delete process.env.ZOK_POSTGRES_URL;

  moduleNonce += 1;
  const { startServer } = await import(`../server.js?cutover-rollback=${mode}-${moduleNonce}`);
  const server = startServer(0);
  await once(server, 'listening');
  return {
    server,
    baseUrl: `http://127.0.0.1:${server.address().port}`,
  };
}

async function login(baseUrl) {
  const response = await fetch(`${baseUrl}/api/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email: 'admin@example.test', password }),
  });
  assert.equal(response.status, 200);
  const setCookie = response.headers.get('set-cookie');
  assert.ok(setCookie);
  return `zok_session=${cookieValue(setCookie, 'zok_session')}; zok_csrf=${cookieValue(setCookie, 'zok_csrf')}`;
}

async function closeServer(server) {
  await new Promise((resolve, reject) => {
    server.close(error => error ? reject(error) : resolve());
  });
}

test('imported chat cutover stays PostgreSQL-only, missing imports fail closed, and JSON rollback remains intact', {
  skip: databaseUrl ? false : 'ZOK_POSTGRES_TEST_URL is not configured',
}, async () => {
  const testDirectory = await mkdtemp(path.join(os.tmpdir(), 'zok-cutover-rollback-'));
  const databaseFile = path.join(testDirectory, 'db.json');
  const appPassword = 'zok-cutover-rollback-db-password';
  const adminUrl = new URL(databaseUrl);
  adminUrl.pathname = '/postgres';
  const isolatedUrl = new URL(databaseUrl);
  isolatedUrl.pathname = '/zok_chat_cutover_rollback_test';
  const appUrl = new URL(isolatedUrl);
  appUrl.username = 'zok_chat_cutover_rollback_test';
  appUrl.password = appPassword;

  let postgresServer;
  let jsonServer;

  await executeSql(adminUrl.toString(), 'DROP DATABASE IF EXISTS zok_chat_cutover_rollback_test WITH (FORCE);');
  await executeSql(adminUrl.toString(), 'DROP ROLE IF EXISTS zok_chat_cutover_rollback_test;');
  await executeSql(adminUrl.toString(), 'CREATE DATABASE zok_chat_cutover_rollback_test;');
  await applyInitialMigration(isolatedUrl.toString());

  try {
    await executeSql(isolatedUrl.toString(), `
      INSERT INTO tenants (id, slug, name)
      VALUES ('${tenantId}', 'cutover-rollback', 'Cutover Rollback');
      CREATE ROLE zok_chat_cutover_rollback_test LOGIN PASSWORD '${appPassword}' NOSUPERUSER NOBYPASSRLS;
      GRANT USAGE ON SCHEMA public TO zok_chat_cutover_rollback_test;
      GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO zok_chat_cutover_rollback_test;
    `);
    await applyTenantIsolationMigration(isolatedUrl.toString());
    await applyRelationalIntegrityMigration(isolatedUrl.toString());

    const importedChat = sourceChat();
    await writeDatabase(databaseFile, [importedChat]);

    const importStorage = createPostgresStorage({
      pool: createPostgresPool({ connectionString: appUrl.toString(), max: 2 }),
    });
    try {
      const imported = await importLegacyChats({ chats: [importedChat], tenantId, storage: importStorage });
      assert.equal(imported.chats, 1);
      assert.equal(imported.messagesCreated, 1);
    } finally {
      await importStorage.close();
    }

    const divergentJsonChat = sourceChat(41, 'JSON rollback-only divergent message');
    await writeDatabase(databaseFile, [divergentJsonChat]);

    const postgresRuntime = await startConfiguredServer({
      mode: 'postgres',
      databaseFile,
      postgresUrl: appUrl.toString(),
    });
    postgresServer = postgresRuntime.server;
    const postgresCookies = await login(postgresRuntime.baseUrl);

    const cutoverRead = await fetch(`${postgresRuntime.baseUrl}/api/chats`, {
      headers: { Cookie: postgresCookies },
    });
    assert.equal(cutoverRead.status, 200);
    const cutoverChats = await cutoverRead.json();
    assert.equal(cutoverChats.length, 1);
    assert.deepEqual(cutoverChats[0].messages, [{
      sender: 'customer',
      text: 'Imported PostgreSQL source message',
      time: '09:00',
    }]);
    assert.notEqual(cutoverChats[0].messages[0].text, divergentJsonChat.messages[0].text);

    const unimportedChat = sourceChat(42, 'JSON-only unimported message');
    await writeDatabase(databaseFile, [divergentJsonChat, unimportedChat]);

    const incompleteCutoverRead = await fetch(`${postgresRuntime.baseUrl}/api/chats`, {
      headers: { Cookie: postgresCookies },
    });
    assert.equal(incompleteCutoverRead.status, 503);
    assert.deepEqual(await incompleteCutoverRead.json(), {
      error: 'PostgreSQL chat import is incomplete',
    });

    await closeServer(postgresServer);
    postgresServer = undefined;

    const jsonRuntime = await startConfiguredServer({
      mode: 'json',
      databaseFile,
    });
    jsonServer = jsonRuntime.server;
    const jsonCookies = await login(jsonRuntime.baseUrl);

    const rollbackRead = await fetch(`${jsonRuntime.baseUrl}/api/chats`, {
      headers: { Cookie: jsonCookies },
    });
    assert.equal(rollbackRead.status, 200);
    const rollbackChats = await rollbackRead.json();
    assert.equal(rollbackChats.length, 2);
    assert.equal(rollbackChats[0].messages[0].text, 'JSON rollback-only divergent message');
    assert.equal(rollbackChats[1].messages[0].text, 'JSON-only unimported message');
  } finally {
    if (postgresServer) await closeServer(postgresServer).catch(() => undefined);
    if (jsonServer) await closeServer(jsonServer).catch(() => undefined);
    await rm(testDirectory, { recursive: true, force: true });
    await rollbackRelationalIntegrityMigration(isolatedUrl.toString()).catch(() => undefined);
    await rollbackTenantIsolationMigration(isolatedUrl.toString()).catch(() => undefined);
    await rollbackInitialMigration(isolatedUrl.toString()).catch(() => undefined);
    await executeSql(adminUrl.toString(), 'DROP DATABASE IF EXISTS zok_chat_cutover_rollback_test WITH (FORCE);').catch(() => undefined);
    await executeSql(adminUrl.toString(), 'DROP ROLE IF EXISTS zok_chat_cutover_rollback_test;').catch(() => undefined);
  }
});
