import { after, test } from 'node:test';
import assert from 'node:assert/strict';
import { mkdtemp, readFile, rm } from 'node:fs/promises';
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

const databaseUrl = process.env.ZOK_POSTGRES_TEST_URL;
const tenantId = 'cccccccc-3333-4333-8333-cccccccccccc';
const password = 'postgres-route-test-1234';
const salt = 'postgres-route-test-salt';
const passwordHash = `pbkdf2_sha256$310000$${salt}$${pbkdf2Sync(password, salt, 310000, 32, 'sha256').toString('base64url')}`;
const testDirectory = await mkdtemp(path.join(os.tmpdir(), 'zok-postgres-api-'));
const databaseFile = path.join(testDirectory, 'db.json');

let server;
let adminUrl;
let isolatedUrl;

function cookieValue(setCookieHeader, name) {
  const match = setCookieHeader.match(new RegExp(`${name}=([^;,]+)`));
  assert.ok(match, `Expected ${name} cookie`);
  return match[1];
}

test('configuration-gated chat API owns messages/read/tags in PostgreSQL while preserving JSON rollback default', {
  skip: databaseUrl ? false : 'ZOK_POSTGRES_TEST_URL is not configured',
}, async () => {
  const appPassword = 'zok-chat-route-db-password';
  adminUrl = new URL(databaseUrl);
  adminUrl.pathname = '/postgres';
  isolatedUrl = new URL(databaseUrl);
  isolatedUrl.pathname = '/zok_chat_route_api_test';
  const appUrl = new URL(isolatedUrl);
  appUrl.username = 'zok_chat_route_test';
  appUrl.password = appPassword;

  await executeSql(adminUrl.toString(), 'DROP DATABASE IF EXISTS zok_chat_route_api_test WITH (FORCE);');
  await executeSql(adminUrl.toString(), 'DROP ROLE IF EXISTS zok_chat_route_test;');
  await executeSql(adminUrl.toString(), 'CREATE DATABASE zok_chat_route_api_test;');
  await applyInitialMigration(isolatedUrl.toString());

  await executeSql(isolatedUrl.toString(), `
    INSERT INTO tenants (id, slug, name)
    VALUES ('${tenantId}', 'chat-route-api', 'Chat Route API');

    WITH legacy(id, channel) AS (
      VALUES (1, 'line'), (2, 'whatsapp'), (3, 'messenger'), (4, 'tiktok'), (5, 'shopify')
    ), inserted_contacts AS (
      INSERT INTO contacts (tenant_id, external_id, name)
      SELECT '${tenantId}', 'legacy-chat:' || id, 'Imported chat ' || id
      FROM legacy
      RETURNING id, external_id
    )
    INSERT INTO conversations (tenant_id, contact_id, channel, external_thread_id)
    SELECT '${tenantId}', c.id, l.channel, c.external_id
    FROM inserted_contacts c
    JOIN legacy l ON c.external_id = 'legacy-chat:' || l.id;

    INSERT INTO messages (tenant_id, conversation_id, direction, sender_type, body, metadata)
    SELECT '${tenantId}', c.id, 'inbound', 'customer',
      'Imported PostgreSQL message ' || split_part(c.external_thread_id, ':', 2),
      jsonb_build_object('legacyTime', 'Imported')
    FROM conversations c;

    CREATE ROLE zok_chat_route_test LOGIN PASSWORD '${appPassword}' NOSUPERUSER NOBYPASSRLS;
    GRANT USAGE ON SCHEMA public TO zok_chat_route_test;
    GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO zok_chat_route_test;
  `);
  await applyTenantIsolationMigration(isolatedUrl.toString());
  await applyRelationalIntegrityMigration(isolatedUrl.toString());

  process.env.NODE_ENV = 'test';
  process.env.ZOK_NO_LISTEN = 'true';
  process.env.ZOK_DB_FILE = databaseFile;
  process.env.ZOK_ADMIN_EMAIL = 'admin@example.test';
  process.env.ZOK_ADMIN_PASSWORD_HASH = passwordHash;
  process.env.ZOK_ADMIN_TENANT_ID = tenantId;
  process.env.ZOK_ALLOWED_ORIGINS = 'http://127.0.0.1:5175';
  process.env.ZOK_CHAT_STORAGE = 'postgres';
  process.env.ZOK_POSTGRES_URL = appUrl.toString();

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

  const initial = await fetch(`${baseUrl}/api/chats`, { headers: { Cookie: cookies } });
  assert.equal(initial.status, 200);
  const initialChats = await initial.json();
  assert.equal(initialChats.length, 5);
  assert.deepEqual(initialChats[0].messages, [{
    sender: 'customer',
    text: 'Imported PostgreSQL message 1',
    time: 'Imported',
  }]);

  const rollbackBefore = JSON.parse(await readFile(databaseFile, 'utf8'));
  assert.equal(rollbackBefore.chats[0].unread, 2);
  assert.deepEqual(rollbackBefore.chats[0].details.tags, ['New Lead', 'LINE OA', 'Medical Service']);

  const markRead = await fetch(`${baseUrl}/api/chats/1/read`, {
    method: 'POST',
    headers: { Cookie: cookies, 'X-CSRF-Token': csrf },
  });
  assert.equal(markRead.status, 200);
  const readChat = await markRead.json();
  assert.equal(readChat.unread, 0);

  const replaceTags = await fetch(`${baseUrl}/api/chats/1/tags`, {
    method: 'POST',
    headers: {
      Cookie: cookies,
      'Content-Type': 'application/json',
      'X-CSRF-Token': csrf,
    },
    body: JSON.stringify({ tags: ['  Priority  ', 'Postgres'] }),
  });
  assert.equal(replaceTags.status, 200);
  const taggedChat = await replaceTags.json();
  assert.deepEqual(taggedChat.details.tags, ['Priority', 'Postgres']);
  assert.equal(taggedChat.unread, 0);

  const rollbackAfterMetadataWrites = JSON.parse(await readFile(databaseFile, 'utf8'));
  assert.equal(rollbackAfterMetadataWrites.chats[0].unread, 2);
  assert.deepEqual(rollbackAfterMetadataWrites.chats[0].details.tags, ['New Lead', 'LINE OA', 'Medical Service']);

  const write = await fetch(`${baseUrl}/api/chats/1/messages`, {
    method: 'POST',
    headers: {
      Cookie: cookies,
      'Content-Type': 'application/json',
      'X-CSRF-Token': csrf,
    },
    body: JSON.stringify({ text: 'Persist this in PostgreSQL', sender: 'agent', activeChatId: 1 }),
  });
  assert.equal(write.status, 201);
  const updated = await write.json();
  assert.equal(updated.time, 'Just now');
  assert.equal(updated.unread, 0);
  assert.equal(updated.messages.at(-1).sender, 'agent');
  assert.equal(updated.messages.at(-1).text, 'Persist this in PostgreSQL');

  const rollbackAfterMessageWrite = JSON.parse(await readFile(databaseFile, 'utf8'));
  assert.equal(rollbackAfterMessageWrite.chats[0].time, '10:24 AM');
  assert.equal(rollbackAfterMessageWrite.chats[0].unread, 2);

  const reread = await fetch(`${baseUrl}/api/chats`, { headers: { Cookie: cookies } });
  assert.equal(reread.status, 200);
  const rereadChats = await reread.json();
  assert.equal(rereadChats[0].messages.at(-1).text, 'Persist this in PostgreSQL');
  assert.equal(rereadChats[0].unread, 0);
  assert.deepEqual(rereadChats[0].details.tags, ['Priority', 'Postgres']);

  await new Promise(resolve => setTimeout(resolve, 1700));
  const afterReply = await fetch(`${baseUrl}/api/chats`, { headers: { Cookie: cookies } });
  assert.equal(afterReply.status, 200);
  const afterReplyChats = await afterReply.json();
  assert.equal(afterReplyChats[0].messages.at(-1).sender, 'customer');
  assert.match(afterReplyChats[0].messages.at(-1).text, /thank you for writing back/i);
  assert.equal(afterReplyChats[0].time, 'Just now');
  assert.equal(afterReplyChats[0].unread, 0);

  const rollbackAfterReply = JSON.parse(await readFile(databaseFile, 'utf8'));
  assert.equal(rollbackAfterReply.chats[0].time, '10:24 AM');
  assert.equal(rollbackAfterReply.chats[0].unread, 2);
});

after(async () => {
  if (server) await new Promise(resolve => server.close(resolve));
  await rm(testDirectory, { recursive: true, force: true });
  if (isolatedUrl) {
    await rollbackRelationalIntegrityMigration(isolatedUrl.toString()).catch(() => undefined);
    await rollbackTenantIsolationMigration(isolatedUrl.toString()).catch(() => undefined);
    await rollbackInitialMigration(isolatedUrl.toString()).catch(() => undefined);
  }
  if (adminUrl) {
    await executeSql(adminUrl.toString(), 'DROP DATABASE IF EXISTS zok_chat_route_api_test WITH (FORCE);').catch(() => undefined);
    await executeSql(adminUrl.toString(), 'DROP ROLE IF EXISTS zok_chat_route_test;').catch(() => undefined);
  }
});