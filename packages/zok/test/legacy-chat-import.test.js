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
import {
  createLegacyChatImportCheckpoint,
  importLegacyChats,
} from '../server/storage/postgres/legacy-chat-import.js';

const databaseUrl = process.env.ZOK_POSTGRES_TEST_URL;
const tenantId = 'bbbbbbbb-2222-4222-8222-bbbbbbbbbbbb';

function sampleChats() {
  return [{
    id: 7,
    name: 'Replay Customer',
    channel: 'line',
    avatar: '/avatar.png',
    messages: [
      { sender: 'customer', text: 'Hello', time: '09:00' },
      { sender: 'agent', text: 'Welcome', time: '09:01' },
    ],
    details: {
      email: 'Replay@Example.test',
      phone: '+66 800 000 007',
      assigned: 'Admin',
      tags: ['vip'],
      orders: [{ id: 'order-7' }],
    },
  }];
}

function resumableChats() {
  return [8, 9].map(id => ({
    id,
    name: `Resume Customer ${id}`,
    channel: 'line',
    avatar: `/avatar-${id}.png`,
    messages: [
      { sender: 'customer', text: `Hello ${id}`, time: '10:00' },
      { sender: 'agent', text: `Welcome ${id}`, time: '10:01' },
    ],
    details: {
      email: `resume-${id}@example.test`,
      phone: `+66 800 000 0${id}`,
      assigned: 'Admin',
      tags: ['resume'],
      orders: [],
    },
  }));
}

test('legacy chat import dry-run validates and counts without acquiring PostgreSQL storage', async () => {
  let touchedStorage = false;
  const result = await importLegacyChats({
    chats: sampleChats(),
    tenantId,
    dryRun: true,
    storage: {
      async withTenantTransaction() {
        touchedStorage = true;
      },
    },
  });

  assert.deepEqual(result, {
    chats: 1,
    messages: 2,
    contactsCreated: 0,
    contactsReused: 0,
    conversationsCreated: 0,
    conversationsReused: 0,
    messagesCreated: 0,
    messagesReused: 0,
    dryRun: true,
  });
  assert.equal(touchedStorage, false);

  await assert.rejects(
    () => importLegacyChats({ chats: [...sampleChats(), ...sampleChats()], tenantId, dryRun: true }),
    /Duplicate legacy chat external id/,
  );
});

test('legacy chat import checkpoint is deterministic and source-bound', () => {
  const first = createLegacyChatImportCheckpoint({ chats: resumableChats(), tenantId, nextIndex: 1 });
  const second = createLegacyChatImportCheckpoint({ chats: resumableChats(), tenantId, nextIndex: 1 });

  assert.deepEqual(first, second);
  assert.deepEqual(Object.keys(first), ['version', 'tenantId', 'sourceDigest', 'nextIndex', 'totalChats']);
  assert.equal(first.version, 1);
  assert.equal(first.nextIndex, 1);
  assert.equal(first.totalChats, 2);
  assert.match(first.sourceDigest, /^[0-9a-f]{64}$/);
});

test('legacy chat import is replay-idempotent, resumable after interruption, and fails closed on conflicts', {
  skip: databaseUrl ? false : 'ZOK_POSTGRES_TEST_URL is not configured',
}, async () => {
  const appPassword = 'zok-import-test-password';
  const adminUrl = new URL(databaseUrl);
  adminUrl.pathname = '/postgres';
  const isolatedUrl = new URL(databaseUrl);
  isolatedUrl.pathname = '/zok_legacy_import_test';
  const appUrl = new URL(isolatedUrl);
  appUrl.username = 'zok_legacy_import_test';
  appUrl.password = appPassword;

  await executeSql(adminUrl.toString(), 'DROP DATABASE IF EXISTS zok_legacy_import_test WITH (FORCE);');
  await executeSql(adminUrl.toString(), 'CREATE DATABASE zok_legacy_import_test;');
  await applyInitialMigration(isolatedUrl.toString());

  try {
    await executeSql(isolatedUrl.toString(), `
      INSERT INTO tenants (id, slug, name)
      VALUES ('${tenantId}', 'legacy-import', 'Legacy Import');
      CREATE ROLE zok_legacy_import_test LOGIN PASSWORD '${appPassword}' NOSUPERUSER NOBYPASSRLS;
      GRANT USAGE ON SCHEMA public TO zok_legacy_import_test;
      GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO zok_legacy_import_test;
    `);
    await applyTenantIsolationMigration(isolatedUrl.toString());
    await applyRelationalIntegrityMigration(isolatedUrl.toString());

    const storage = createPostgresStorage({
      pool: createPostgresPool({ connectionString: appUrl.toString(), max: 2 }),
    });
    try {
      const first = await importLegacyChats({ chats: sampleChats(), tenantId, storage });
      assert.deepEqual(first, {
        chats: 1,
        messages: 2,
        contactsCreated: 1,
        contactsReused: 0,
        conversationsCreated: 1,
        conversationsReused: 0,
        messagesCreated: 2,
        messagesReused: 0,
        dryRun: false,
      });

      const replay = await importLegacyChats({ chats: sampleChats(), tenantId, storage });
      assert.equal(replay.contactsCreated, 0);
      assert.equal(replay.contactsReused, 1);
      assert.equal(replay.conversationsCreated, 0);
      assert.equal(replay.conversationsReused, 1);
      assert.equal(replay.messagesCreated, 0);
      assert.equal(replay.messagesReused, 2);

      await storage.withTenantTransaction(tenantId, async tx => {
        const counts = await tx.query(`
          SELECT
            (SELECT count(*)::int FROM contacts) AS contacts,
            (SELECT count(*)::int FROM conversations) AS conversations,
            (SELECT count(*)::int FROM messages) AS messages
        `);
        assert.deepEqual(counts.rows[0], { contacts: 1, conversations: 1, messages: 2 });
      });

      const conflicting = sampleChats();
      conflicting[0].messages[0].text = 'Changed source message';
      await assert.rejects(
        () => importLegacyChats({ chats: conflicting, tenantId, storage }),
        /Existing message conflicts with import source/,
      );

      await storage.withTenantTransaction(tenantId, async tx => {
        const result = await tx.query('SELECT count(*)::int AS count FROM messages');
        assert.equal(result.rows[0].count, 2);
      });

      let checkpoint;
      await assert.rejects(
        () => importLegacyChats({
          chats: resumableChats(),
          tenantId,
          storage,
          onCheckpoint(nextCheckpoint) {
            checkpoint = nextCheckpoint;
            if (nextCheckpoint.nextIndex === 1) throw new Error('simulated import interruption');
          },
        }),
        /simulated import interruption/,
      );

      assert.equal(checkpoint.nextIndex, 1);
      assert.equal(checkpoint.totalChats, 2);

      await storage.withTenantTransaction(tenantId, async tx => {
        const counts = await tx.query(`
          SELECT
            (SELECT count(*)::int FROM contacts) AS contacts,
            (SELECT count(*)::int FROM conversations) AS conversations,
            (SELECT count(*)::int FROM messages) AS messages
        `);
        assert.deepEqual(counts.rows[0], { contacts: 2, conversations: 2, messages: 4 });
      });

      const resumed = await importLegacyChats({
        chats: resumableChats(),
        tenantId,
        storage,
        checkpoint,
        onCheckpoint(nextCheckpoint) {
          checkpoint = nextCheckpoint;
        },
      });
      assert.equal(resumed.contactsCreated, 1);
      assert.equal(resumed.conversationsCreated, 1);
      assert.equal(resumed.messagesCreated, 2);
      assert.equal(checkpoint.nextIndex, 2);

      await storage.withTenantTransaction(tenantId, async tx => {
        const counts = await tx.query(`
          SELECT
            (SELECT count(*)::int FROM contacts) AS contacts,
            (SELECT count(*)::int FROM conversations) AS conversations,
            (SELECT count(*)::int FROM messages) AS messages
        `);
        assert.deepEqual(counts.rows[0], { contacts: 3, conversations: 3, messages: 6 });
      });

      const changedResumeSource = resumableChats();
      changedResumeSource[1].messages[0].text = 'Changed after checkpoint';
      await assert.rejects(
        () => importLegacyChats({
          chats: changedResumeSource,
          tenantId,
          storage,
          checkpoint: createLegacyChatImportCheckpoint({ chats: resumableChats(), tenantId, nextIndex: 1 }),
        }),
        /checkpoint source does not match/,
      );
    } finally {
      await storage.close();
    }
  } finally {
    await rollbackRelationalIntegrityMigration(isolatedUrl.toString()).catch(() => undefined);
    await rollbackTenantIsolationMigration(isolatedUrl.toString()).catch(() => undefined);
    await rollbackInitialMigration(isolatedUrl.toString()).catch(() => undefined);
    await executeSql(adminUrl.toString(), 'DROP DATABASE IF EXISTS zok_legacy_import_test WITH (FORCE);').catch(() => undefined);
    await executeSql(adminUrl.toString(), 'DROP ROLE IF EXISTS zok_legacy_import_test;').catch(() => undefined);
  }
});
