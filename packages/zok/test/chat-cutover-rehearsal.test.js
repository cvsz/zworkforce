import test from 'node:test';
import assert from 'node:assert/strict';
import { promisify } from 'node:util';
import { execFile } from 'node:child_process';
import { mkdtemp, readFile, rm, writeFile } from 'node:fs/promises';
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

const execFileAsync = promisify(execFile);
const databaseUrl = process.env.ZOK_POSTGRES_TEST_URL;
const tenantId = 'eeeeeeee-5555-4555-8555-eeeeeeeeeeee';

function sourceChat(id, text = `Imported message ${id}`) {
  return {
    id,
    name: `Rehearsal Customer ${id}`,
    avatar: `R${id}`,
    channel: 'line',
    unread: 1,
    time: '10:00',
    messages: [
      { sender: 'customer', text, time: '10:00' },
      { sender: 'agent', text: `Reply ${id}`, time: '10:01' },
    ],
    details: {
      phone: `+66 811 000 ${id}`,
      email: `rehearsal-${id}@example.test`,
      assigned: 'Admin',
      tags: ['rehearsal'],
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

async function runRehearsal({ sourceFile, postgresUrl }) {
  return execFileAsync(process.execPath, [
    path.join(process.cwd(), 'scripts', 'rehearse-chat-cutover.js'),
    '--source', sourceFile,
    '--tenant', tenantId,
    '--postgres-url', postgresUrl,
  ], { cwd: process.cwd() });
}

test('operational chat cutover rehearsal passes exact imported state, preserves rollback JSON, and fails closed on drift', {
  skip: databaseUrl ? false : 'ZOK_POSTGRES_TEST_URL is not configured',
}, async () => {
  const testDirectory = await mkdtemp(path.join(os.tmpdir(), 'zok-chat-rehearsal-'));
  const databaseFile = path.join(testDirectory, 'db.json');
  const appPassword = 'zok-chat-rehearsal-db-password';
  const adminUrl = new URL(databaseUrl);
  adminUrl.pathname = '/postgres';
  const isolatedUrl = new URL(databaseUrl);
  isolatedUrl.pathname = '/zok_chat_rehearsal_test';
  const appUrl = new URL(isolatedUrl);
  appUrl.username = 'zok_chat_rehearsal_test';
  appUrl.password = appPassword;

  await executeSql(adminUrl.toString(), 'DROP DATABASE IF EXISTS zok_chat_rehearsal_test WITH (FORCE);');
  await executeSql(adminUrl.toString(), 'DROP ROLE IF EXISTS zok_chat_rehearsal_test;');
  await executeSql(adminUrl.toString(), 'CREATE DATABASE zok_chat_rehearsal_test;');
  await applyInitialMigration(isolatedUrl.toString());

  try {
    await executeSql(isolatedUrl.toString(), `
      INSERT INTO tenants (id, slug, name)
      VALUES ('${tenantId}', 'chat-rehearsal', 'Chat Rehearsal');
      CREATE ROLE zok_chat_rehearsal_test LOGIN PASSWORD '${appPassword}' NOSUPERUSER NOBYPASSRLS;
      GRANT USAGE ON SCHEMA public TO zok_chat_rehearsal_test;
      GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO zok_chat_rehearsal_test;
    `);
    await applyTenantIsolationMigration(isolatedUrl.toString());
    await applyRelationalIntegrityMigration(isolatedUrl.toString());

    const chats = [sourceChat(51), sourceChat(52)];
    await writeDatabase(databaseFile, chats);

    const storage = createPostgresStorage({
      pool: createPostgresPool({ connectionString: appUrl.toString(), max: 2 }),
    });
    try {
      const imported = await importLegacyChats({ chats, tenantId, storage });
      assert.equal(imported.chats, 2);
      assert.equal(imported.messagesCreated, 4);
    } finally {
      await storage.close();
    }

    const beforeSuccess = await readFile(databaseFile);
    const success = await runRehearsal({
      sourceFile: databaseFile,
      postgresUrl: appUrl.toString(),
    });
    const summary = JSON.parse(success.stdout.trim());
    assert.deepEqual({
      ready: summary.ready,
      chats: summary.chats,
      messages: summary.messages,
      rollbackSnapshotPreserved: summary.rollbackSnapshotPreserved,
    }, {
      ready: true,
      chats: 2,
      messages: 4,
      rollbackSnapshotPreserved: true,
    });
    assert.match(summary.sourceDigest, /^[0-9a-f]{64}$/);
    assert.deepEqual(await readFile(databaseFile), beforeSuccess);

    const missingImportChats = [...chats, sourceChat(53)];
    await writeDatabase(databaseFile, missingImportChats);
    const beforeMissingFailure = await readFile(databaseFile);
    await assert.rejects(
      runRehearsal({ sourceFile: databaseFile, postgresUrl: appUrl.toString() }),
      error => {
        assert.match(error.stderr, /Chat cutover preflight failed: missing imported conversation legacy-chat:53/);
        return true;
      },
    );
    assert.deepEqual(await readFile(databaseFile), beforeMissingFailure);

    await writeDatabase(databaseFile, chats);
    const driftStorage = createPostgresStorage({
      pool: createPostgresPool({ connectionString: appUrl.toString(), max: 2 }),
    });
    try {
      await driftStorage.withTenantTransaction(tenantId, tx => tx.query(`
        UPDATE messages
        SET body = 'PostgreSQL drifted body'
        WHERE external_message_id = 'legacy-chat:51:message:0'
      `));
    } finally {
      await driftStorage.close();
    }

    const beforeDriftFailure = await readFile(databaseFile);
    await assert.rejects(
      runRehearsal({ sourceFile: databaseFile, postgresUrl: appUrl.toString() }),
      error => {
        assert.match(error.stderr, /Chat cutover preflight failed: message legacy-chat:51:message:0 differs from the legacy source/);
        return true;
      },
    );
    assert.deepEqual(await readFile(databaseFile), beforeDriftFailure);
  } finally {
    await rm(testDirectory, { recursive: true, force: true });
    await rollbackRelationalIntegrityMigration(isolatedUrl.toString()).catch(() => undefined);
    await rollbackTenantIsolationMigration(isolatedUrl.toString()).catch(() => undefined);
    await rollbackInitialMigration(isolatedUrl.toString()).catch(() => undefined);
    await executeSql(adminUrl.toString(), 'DROP DATABASE IF EXISTS zok_chat_rehearsal_test WITH (FORCE);').catch(() => undefined);
    await executeSql(adminUrl.toString(), 'DROP ROLE IF EXISTS zok_chat_rehearsal_test;').catch(() => undefined);
  }
});
