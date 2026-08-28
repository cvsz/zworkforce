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
import { createContactsRepository } from '../server/storage/postgres/contacts-repository.js';
import { createConversationsRepository } from '../server/storage/postgres/conversations-repository.js';

const databaseUrl = process.env.ZOK_POSTGRES_TEST_URL;

test('real PostgreSQL pool enforces tenant-scoped contact, conversation, and message repositories', {
  skip: databaseUrl ? false : 'ZOK_POSTGRES_TEST_URL is not configured',
}, async () => {
  const tenantA = '99999999-9999-4999-8999-999999999999';
  const tenantB = 'aaaaaaaa-1111-4111-8111-aaaaaaaaaaaa';
  const appPassword = 'zok-real-pool-password';
  const adminUrl = new URL(databaseUrl);
  adminUrl.pathname = '/postgres';
  const isolatedUrl = new URL(databaseUrl);
  isolatedUrl.pathname = '/zok_pool_integration_test';
  const appUrl = new URL(isolatedUrl);
  appUrl.username = 'zok_real_pool_test';
  appUrl.password = appPassword;

  await executeSql(adminUrl.toString(), 'DROP DATABASE IF EXISTS zok_pool_integration_test WITH (FORCE);');
  await executeSql(adminUrl.toString(), 'CREATE DATABASE zok_pool_integration_test;');
  await applyInitialMigration(isolatedUrl.toString());
  try {
    await executeSql(isolatedUrl.toString(), `
      INSERT INTO tenants (id, slug, name) VALUES
        ('${tenantA}', 'real-pool-a', 'Real Pool A'),
        ('${tenantB}', 'real-pool-b', 'Real Pool B');
      CREATE ROLE zok_real_pool_test LOGIN PASSWORD '${appPassword}' NOSUPERUSER NOBYPASSRLS;
      GRANT USAGE ON SCHEMA public TO zok_real_pool_test;
      GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO zok_real_pool_test;
    `);
    await applyTenantIsolationMigration(isolatedUrl.toString());
    await applyRelationalIntegrityMigration(isolatedUrl.toString());

    const pool = createPostgresPool({ connectionString: appUrl.toString(), max: 2 });
    const storage = createPostgresStorage({ pool });
    try {
      let tenantAContactId;
      await storage.withTenantTransaction(tenantA, async tx => {
        assert.equal(tx.tenantId, tenantA);
        const contacts = createContactsRepository(tx);
        const created = await contacts.create({ name: 'Visible A', email: 'A@example.test' });
        tenantAContactId = created.id;
        assert.equal(created.name, 'Visible A');
        assert.equal(created.email, 'a@example.test');
        assert.equal((await contacts.list()).length, 1);

        const conversations = createConversationsRepository(tx);
        const conversation = await conversations.create({ contactId: created.id, channel: 'line' });
        const message = await conversations.addMessage(conversation.id, {
          direction: 'outbound',
          senderType: 'agent',
          body: 'Hello from tenant A',
        });
        assert.equal(message.conversationId, conversation.id);
        assert.equal(message.body, 'Hello from tenant A');
        assert.equal((await conversations.list()).length, 1);
      });

      let tenantBContactId;
      await storage.withTenantTransaction(tenantB, async tx => {
        assert.equal(tx.tenantId, tenantB);
        const contacts = createContactsRepository(tx);
        const created = await contacts.create({ name: 'Visible B', email: 'B@example.test' });
        tenantBContactId = created.id;
        assert.equal((await contacts.list()).length, 1);
        assert.equal((await createConversationsRepository(tx).list()).length, 0);
      });

      assert.notEqual(tenantAContactId, tenantBContactId);
      await assert.rejects(
        () => storage.withTenantTransaction(tenantA, tx =>
          createConversationsRepository(tx).create({ contactId: tenantBContactId, channel: 'line' })),
        /foreign key constraint/i,
      );

      await assert.rejects(
        () => storage.withTenantTransaction(tenantA, tx =>
          tx.query('INSERT INTO contacts (tenant_id, name) VALUES ($1, $2)', [tenantB, 'Cross tenant'])),
        /row-level security policy/i,
      );
    } finally {
      await storage.close();
    }
  } finally {
    await rollbackRelationalIntegrityMigration(isolatedUrl.toString()).catch(() => undefined);
    await rollbackTenantIsolationMigration(isolatedUrl.toString()).catch(() => undefined);
    await rollbackInitialMigration(isolatedUrl.toString()).catch(() => undefined);
    await executeSql(adminUrl.toString(), 'DROP DATABASE IF EXISTS zok_pool_integration_test WITH (FORCE);').catch(() => undefined);
    await executeSql(adminUrl.toString(), 'DROP ROLE IF EXISTS zok_real_pool_test;').catch(() => undefined);
  }
});
