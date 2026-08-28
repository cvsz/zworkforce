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
import { createLegacyChatRuntime } from '../server/storage/postgres/legacy-chat-runtime.js';

const databaseUrl = process.env.ZOK_POSTGRES_TEST_URL;
const tenantId = 'bbbbbbbb-2222-4222-8222-bbbbbbbbbbbb';
const otherTenantId = 'aaaaaaaa-1111-4111-8111-aaaaaaaaaaaa';

const chats = [{
  id: 7,
  name: 'Metadata Integration',
  avatar: 'MI',
  channel: 'line',
  unread: 4,
  time: 'Yesterday',
  messages: [{ sender: 'customer', text: 'hello', time: 'Yesterday' }],
  details: {
    email: 'metadata@example.test',
    phone: '+66 800 000 007',
    assigned: 'Alex Rivera',
    tags: ['VIP', 'LINE OA'],
    orders: [],
  },
}];

test('legacy chat metadata persists under tenant RLS and preserves compatibility fields', {
  skip: databaseUrl ? false : 'ZOK_POSTGRES_TEST_URL is not configured',
}, async () => {
  const appPassword = 'zok-metadata-test-password';
  const adminUrl = new URL(databaseUrl);
  adminUrl.pathname = '/postgres';
  const isolatedUrl = new URL(databaseUrl);
  isolatedUrl.pathname = '/zok_legacy_metadata_test';
  const appUrl = new URL(isolatedUrl);
  appUrl.username = 'zok_legacy_metadata_test';
  appUrl.password = appPassword;

  await executeSql(adminUrl.toString(), 'DROP DATABASE IF EXISTS zok_legacy_metadata_test WITH (FORCE);');
  await executeSql(adminUrl.toString(), 'CREATE DATABASE zok_legacy_metadata_test;');
  await applyInitialMigration(isolatedUrl.toString());

  try {
    await executeSql(isolatedUrl.toString(), `
      INSERT INTO tenants (id, slug, name) VALUES
        ('${tenantId}', 'metadata-primary', 'Metadata Primary'),
        ('${otherTenantId}', 'metadata-other', 'Metadata Other');
      CREATE ROLE zok_legacy_metadata_test LOGIN PASSWORD '${appPassword}' NOSUPERUSER NOBYPASSRLS;
      GRANT USAGE ON SCHEMA public TO zok_legacy_metadata_test;
      GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO zok_legacy_metadata_test;
    `);
    await applyTenantIsolationMigration(isolatedUrl.toString());
    await applyRelationalIntegrityMigration(isolatedUrl.toString());

    const storage = createPostgresStorage({ pool: createPostgresPool({ connectionString: appUrl.toString(), max: 2 }) });
    try {
      await importLegacyChats({ chats, tenantId, storage });
      const runtime = createLegacyChatRuntime({ storage });
      const request = { user: { tenantId } };

      const imported = await runtime.read(request, 7);
      assert.deepEqual(imported.metadata, {
        legacyChatId: 7,
        avatar: 'MI',
        assigned: 'Alex Rivera',
        tags: ['VIP', 'LINE OA'],
        orders: [],
        unread: 4,
        displayTime: 'Yesterday',
      });

      const readMetadata = await runtime.markRead(request, 7);
      assert.equal(readMetadata.unread, 0);
      const taggedMetadata = await runtime.replaceTags(request, 7, ['Priority']);
      assert.deepEqual(taggedMetadata.tags, ['Priority']);

      const reread = await runtime.read(request, 7);
      assert.equal(reread.metadata.unread, 0);
      assert.deepEqual(reread.metadata.tags, ['Priority']);
      assert.equal(reread.metadata.displayTime, 'Yesterday');

      const isolated = await runtime.read({ user: { tenantId: otherTenantId } }, 7);
      assert.equal(isolated, null);
    } finally {
      await storage.close();
    }
  } finally {
    await rollbackRelationalIntegrityMigration(isolatedUrl.toString()).catch(() => undefined);
    await rollbackTenantIsolationMigration(isolatedUrl.toString()).catch(() => undefined);
    await rollbackInitialMigration(isolatedUrl.toString()).catch(() => undefined);
    await executeSql(adminUrl.toString(), 'DROP DATABASE IF EXISTS zok_legacy_metadata_test WITH (FORCE);');
  }
});
