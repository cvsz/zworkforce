import test from 'node:test';
import assert from 'node:assert/strict';
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

function concurrentChats() {
  return [{
    id: 40,
    name: 'Concurrent Import Customer',
    channel: 'line',
    avatar: '/avatar-40.png',
    messages: [
      { sender: 'customer', text: 'Concurrent hello', time: '12:00' },
    ],
    details: {
      email: 'concurrent@example.test',
      phone: '+66 800 000 040',
      assigned: 'Admin',
      tags: ['concurrent'],
      orders: [],
    },
  }];
}

test('same-tenant/source legacy chat import fails closed while a competing importer holds the database lock', {
  skip: databaseUrl ? false : 'ZOK_POSTGRES_TEST_URL is not configured',
}, async () => {
  const appPassword = 'zok-import-concurrency-password';
  const adminUrl = new URL(databaseUrl);
  adminUrl.pathname = '/postgres';
  const isolatedUrl = new URL(databaseUrl);
  isolatedUrl.pathname = '/zok_legacy_import_concurrency_test';
  const appUrl = new URL(isolatedUrl);
  appUrl.username = 'zok_legacy_import_concurrency_test';
  appUrl.password = appPassword;

  await executeSql(adminUrl.toString(), 'DROP DATABASE IF EXISTS zok_legacy_import_concurrency_test WITH (FORCE);');
  await executeSql(adminUrl.toString(), 'CREATE DATABASE zok_legacy_import_concurrency_test;');
  await applyInitialMigration(isolatedUrl.toString());

  try {
    await executeSql(isolatedUrl.toString(), `
      INSERT INTO tenants (id, slug, name)
      VALUES ('${tenantId}', 'legacy-import-concurrency', 'Legacy Import Concurrency');
      CREATE ROLE zok_legacy_import_concurrency_test LOGIN PASSWORD '${appPassword}' NOSUPERUSER NOBYPASSRLS;
      GRANT USAGE ON SCHEMA public TO zok_legacy_import_concurrency_test;
      GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO zok_legacy_import_concurrency_test;
    `);
    await applyTenantIsolationMigration(isolatedUrl.toString());
    await applyRelationalIntegrityMigration(isolatedUrl.toString());

    const storage = createPostgresStorage({
      pool: createPostgresPool({ connectionString: appUrl.toString(), max: 3 }),
    });

    try {
      let signalCheckpoint;
      const checkpointReached = new Promise(resolve => {
        signalCheckpoint = resolve;
      });
      let releaseCheckpoint;
      const holdCheckpoint = new Promise(resolve => {
        releaseCheckpoint = resolve;
      });

      const firstImport = importLegacyChats({
        chats: concurrentChats(),
        tenantId,
        storage,
        async onCheckpoint() {
          signalCheckpoint();
          await holdCheckpoint;
        },
      });

      await checkpointReached;

      await assert.rejects(
        () => importLegacyChats({ chats: concurrentChats(), tenantId, storage }),
        /PostgreSQL advisory lock is already held/,
      );

      await storage.withTenantTransaction(tenantId, async tx => {
        const counts = await tx.query(`
          SELECT
            (SELECT count(*)::int FROM contacts) AS contacts,
            (SELECT count(*)::int FROM conversations) AS conversations,
            (SELECT count(*)::int FROM messages) AS messages
        `);
        assert.deepEqual(counts.rows[0], { contacts: 1, conversations: 1, messages: 1 });
      });

      releaseCheckpoint();
      const completed = await firstImport;
      assert.equal(completed.contactsCreated, 1);
      assert.equal(completed.conversationsCreated, 1);
      assert.equal(completed.messagesCreated, 1);

      const replay = await importLegacyChats({ chats: concurrentChats(), tenantId, storage });
      assert.equal(replay.contactsCreated, 0);
      assert.equal(replay.contactsReused, 1);
      assert.equal(replay.conversationsCreated, 0);
      assert.equal(replay.conversationsReused, 1);
      assert.equal(replay.messagesCreated, 0);
      assert.equal(replay.messagesReused, 1);
    } finally {
      await storage.close();
    }
  } finally {
    await rollbackRelationalIntegrityMigration(isolatedUrl.toString()).catch(() => undefined);
    await rollbackTenantIsolationMigration(isolatedUrl.toString()).catch(() => undefined);
    await rollbackInitialMigration(isolatedUrl.toString()).catch(() => undefined);
    await executeSql(adminUrl.toString(), 'DROP DATABASE IF EXISTS zok_legacy_import_concurrency_test WITH (FORCE);').catch(() => undefined);
    await executeSql(adminUrl.toString(), 'DROP ROLE IF EXISTS zok_legacy_import_concurrency_test;').catch(() => undefined);
  }
});
