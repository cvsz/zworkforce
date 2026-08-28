import test from 'node:test';
import assert from 'node:assert/strict';
import { promisify } from 'node:util';
import { execFile } from 'node:child_process';
import { mkdtemp, rm, writeFile } from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import {
  applyInitialMigration,
  applyRelationalIntegrityMigration,
  applyTenantIsolationMigration,
  applySyncLogsMigration,
  executeSql,
  rollbackInitialMigration,
  rollbackRelationalIntegrityMigration,
  rollbackTenantIsolationMigration,
  rollbackSyncLogsMigration,
} from '../scripts/postgres-migrations.js';
import { createPostgresPool, createPostgresStorage } from '../server/storage/postgres-storage.js';

const execFileAsync = promisify(execFile);
const databaseUrl = process.env.ZOK_POSTGRES_TEST_URL;
const tenantId = 'eeeeeeee-5555-4555-8555-eeeeeeeeeeee';

function databaseState(overrides = {}) {
  return {
    chats: overrides.chats ?? [],
    aiConfig: overrides.aiConfig ?? {},
    flowNodes: overrides.flowNodes ?? [],
    campaigns: overrides.campaigns ?? [],
    integrations: overrides.integrations ?? [],
    syncLogs: overrides.syncLogs ?? [],
  };
}

async function writeDatabase(filePath, state) {
  await writeFile(filePath, `${JSON.stringify(state, null, 2)}\n`, 'utf8');
}

async function runRehearsal({ sourceFile, postgresUrl, apply = false }) {
  const args = [
    path.join(process.cwd(), 'scripts', 'rehearse-application-cutover.js'),
    '--source', sourceFile,
    '--tenant', tenantId,
    '--postgres-url', postgresUrl,
  ];
  if (apply) args.push('--apply');
  return execFileAsync(process.execPath, args, { cwd: process.cwd() });
}

async function setupIsolatedDatabase() {
  const testDirectory = await mkdtemp(path.join(os.tmpdir(), 'zok-application-rehearsal-'));
  const databaseFile = path.join(testDirectory, 'db.json');
  const appPassword = 'zok-application-rehearsal-db-password';
  const adminUrl = new URL(databaseUrl);
  adminUrl.pathname = '/postgres';
  const isolatedUrl = new URL(databaseUrl);
  isolatedUrl.pathname = '/zok_application_rehearsal_test';
  const appUrl = new URL(isolatedUrl);
  appUrl.username = 'zok_application_rehearsal_test';
  appUrl.password = appPassword;

  await executeSql(adminUrl.toString(), 'DROP DATABASE IF EXISTS zok_application_rehearsal_test WITH (FORCE);');
  await executeSql(adminUrl.toString(), 'DROP ROLE IF EXISTS zok_application_rehearsal_test;');
  await executeSql(adminUrl.toString(), 'CREATE DATABASE zok_application_rehearsal_test;');
  await applyInitialMigration(isolatedUrl.toString());
  await applyTenantIsolationMigration(isolatedUrl.toString());
  await applyRelationalIntegrityMigration(isolatedUrl.toString());
  await applySyncLogsMigration(isolatedUrl.toString());

  await executeSql(isolatedUrl.toString(), `
    INSERT INTO tenants (id, slug, name)
    VALUES ('${tenantId}', 'application-rehearsal', 'Application Rehearsal');
    CREATE ROLE zok_application_rehearsal_test LOGIN PASSWORD '${appPassword}' NOSUPERUSER NOBYPASSRLS;
    GRANT USAGE ON SCHEMA public TO zok_application_rehearsal_test;
    GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO zok_application_rehearsal_test;
    GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO zok_application_rehearsal_test;
  `);

  return { testDirectory, databaseFile, appUrl: appUrl.toString() };
}

async function teardownIsolatedDatabase() {
  const adminUrl = new URL(databaseUrl);
  adminUrl.pathname = '/postgres';
  await rollbackSyncLogsMigration(databaseUrl).catch(() => undefined);
  await rollbackRelationalIntegrityMigration(databaseUrl).catch(() => undefined);
  await rollbackTenantIsolationMigration(databaseUrl).catch(() => undefined);
  await rollbackInitialMigration(databaseUrl).catch(() => undefined);
  await executeSql(adminUrl.toString(), 'DROP DATABASE IF EXISTS zok_application_rehearsal_test WITH (FORCE);').catch(() => undefined);
  await executeSql(adminUrl.toString(), 'DROP ROLE IF EXISTS zok_application_rehearsal_test;').catch(() => undefined);
}

test('application cutover dry-run reports zero drift when JSON and PostgreSQL are in sync', {
  skip: databaseUrl ? false : 'ZOK_POSTGRES_TEST_URL is not configured',
}, async () => {
  const { testDirectory, databaseFile, appUrl } = await setupIsolatedDatabase();
  try {
    const state = databaseState({
      campaigns: [
        { id: 1, name: 'Test Campaign', status: 'completed', channel: 'whatsapp', target: 'VIP', recipients: 100, delivered: '100%', opened: '80%', converted: '10%', date: '2026-08-22' },
      ],
      integrations: [
        { id: 'shopify', name: 'Shopify', description: 'Shopify integration', status: 'disconnected', category: 'E-commerce', logo: 'S' },
      ],
      aiConfig: { agentName: 'Test AI', persona: 'sales', knowledgeBase: 'KB', qaPairs: [] },
      flowNodes: [
        { id: 'node-1', type: 'trigger', title: 'Test Node', description: 'Desc', x: 10, y: 20, details: {} },
      ],
      syncLogs: ['[10:00:00 AM] Test log'],
    });
    await writeDatabase(databaseFile, state);

    const storage = createPostgresStorage({ pool: createPostgresPool({ connectionString: appUrl, max: 2 }) });
    try {
      await storage.withTenantTransaction(tenantId, async tx => {
        await tx.query(`
          INSERT INTO campaigns (tenant_id, name, status, channel, target) VALUES ($1, $2, $3, $4, $5::jsonb)
        `, [tenantId, 'Test Campaign', 'completed', 'whatsapp', JSON.stringify('VIP')]);
        await tx.query(`
          INSERT INTO integrations (tenant_id, provider, external_id, status, config) VALUES ($1, $2, $3, $4, $5::jsonb)
        `, [tenantId, 'shopify', 'shopify', 'disconnected', JSON.stringify({ name: 'Shopify', description: 'Shopify integration', category: 'E-commerce', logo: 'S' })]);
        await tx.query(`
          INSERT INTO ai_config (tenant_id, agent_name, persona, knowledge_base, qa_pairs)
          VALUES ($1, $2, $3, $4, $5::jsonb)
        `, [tenantId, 'Test AI', 'sales', 'KB', JSON.stringify([])]);
        await tx.query(`
          INSERT INTO flow_nodes (tenant_id, id, type, title, description, x, y, details)
          VALUES ($1, $2, $3, $4, $5, $6, $7, $8::jsonb)
        `, [tenantId, 'node-1', 'trigger', 'Test Node', 'Desc', 10, 20, JSON.stringify({})]);
        await tx.query(`
          INSERT INTO sync_logs (tenant_id, log_text) VALUES ($1, $2)
        `, [tenantId, '[10:00:00 AM] Test log']);
      });
    } finally {
      await storage.close();
    }

    const { stdout } = await runRehearsal({ sourceFile: databaseFile, postgresUrl: appUrl });
    const summary = JSON.parse(stdout.trim());
    assert.equal(summary.ready, true);
    assert.equal(summary.driftCount, 0);
    assert.equal(summary.chatPreflight.ready, true);
  } finally {
    await rm(testDirectory, { recursive: true, force: true });
    await teardownIsolatedDatabase();
  }
});

test('application cutover dry-run reports drift when PostgreSQL state differs from JSON', {
  skip: databaseUrl ? false : 'ZOK_POSTGRES_TEST_URL is not configured',
}, async () => {
  const { testDirectory, databaseFile, appUrl } = await setupIsolatedDatabase();
  try {
    const state = databaseState({
      campaigns: [
        { id: 1, name: 'Drift Campaign', status: 'completed', channel: 'whatsapp', target: 'VIP', recipients: 100, delivered: '100%', opened: '80%', converted: '10%', date: '2026-08-22' },
      ],
      integrations: [
        { id: 'shopify', name: 'Shopify', description: 'Shopify integration', status: 'disconnected', category: 'E-commerce', logo: 'S' },
      ],
      aiConfig: { agentName: 'Drift AI', persona: 'sales', knowledgeBase: 'KB', qaPairs: [] },
      flowNodes: [],
      syncLogs: [],
    });
    await writeDatabase(databaseFile, state);

    const storage = createPostgresStorage({ pool: createPostgresPool({ connectionString: appUrl, max: 2 }) });
    try {
      await storage.withTenantTransaction(tenantId, async tx => {
        await tx.query(`
          INSERT INTO campaigns (tenant_id, name, status, channel, target) VALUES ($1, $2, $3, $4, $5::jsonb)
        `, [tenantId, 'Drift Campaign', 'draft', 'line', JSON.stringify('Other')]);
        await tx.query(`
          INSERT INTO integrations (tenant_id, provider, external_id, status, config) VALUES ($1, $2, $3, $4, $5::jsonb)
        `, [tenantId, 'shopify', 'shopify', 'connected', JSON.stringify({ name: 'Shopify Drifted', description: 'Shopify integration', category: 'E-commerce', logo: 'S' })]);
        await tx.query(`
          INSERT INTO ai_config (tenant_id, agent_name, persona, knowledge_base, qa_pairs)
          VALUES ($1, $2, $3, $4, $5::jsonb)
        `, [tenantId, 'Other AI', 'support', 'Other KB', JSON.stringify([])]);
        await tx.query(`
          INSERT INTO sync_logs (tenant_id, log_text) VALUES ($1, $2)
        `, [tenantId, '[10:00:00 AM] Different log']);
      });
    } finally {
      await storage.close();
    }

    await assert.rejects(
      runRehearsal({ sourceFile: databaseFile, postgresUrl: appUrl }),
      error => {
        assert.equal(error.code, 2);
        const summary = JSON.parse(error.stdout.trim());
        assert.equal(summary.ready, false);
        assert.ok(summary.driftCount >= 4);
        const collections = summary.sampleDriftedRecords.map(item => item.collection);
        assert.ok(collections.includes('campaigns'));
        assert.ok(collections.includes('integrations'));
        assert.ok(collections.includes('aiConfig'));
        assert.ok(collections.includes('syncLogs'));
        return true;
      },
    );
  } finally {
    await rm(testDirectory, { recursive: true, force: true });
    await teardownIsolatedDatabase();
  }
});

test('application cutover --apply migrates data idempotently', {
  skip: databaseUrl ? false : 'ZOK_POSTGRES_TEST_URL is not configured',
}, async () => {
  const { testDirectory, databaseFile, appUrl } = await setupIsolatedDatabase();
  try {
    const state = databaseState({
      campaigns: [
        { id: 1, name: 'Migrate Campaign', status: 'completed', channel: 'whatsapp', target: 'VIP', recipients: 100, delivered: '100%', opened: '80%', converted: '10%', date: '2026-08-22' },
      ],
      integrations: [
        { id: 'shopify', name: 'Shopify', description: 'Shopify integration', status: 'disconnected', category: 'E-commerce', logo: 'S' },
      ],
      aiConfig: { agentName: 'Migrate AI', persona: 'sales', knowledgeBase: 'KB', qaPairs: [] },
      flowNodes: [
        { id: 'node-1', type: 'trigger', title: 'Migrate Node', description: 'Desc', x: 10, y: 20, details: {} },
      ],
      syncLogs: ['[10:00:00 AM] Migrate log'],
    });
    await writeDatabase(databaseFile, state);

    const { stdout: firstStdout } = await runRehearsal({ sourceFile: databaseFile, postgresUrl: appUrl, apply: true });
    const first = JSON.parse(firstStdout.trim());
    assert.equal(first.ready, true);
    assert.equal(first.migrationSummary.campaigns.created, 1);
    assert.equal(first.migrationSummary.integrations.created, 1);
    assert.equal(first.migrationSummary.aiConfig.created, 1);
    assert.equal(first.migrationSummary.flowNodes.created, 1);
    assert.equal(first.migrationSummary.syncLogs.created, 1);

    const { stdout: secondStdout } = await runRehearsal({ sourceFile: databaseFile, postgresUrl: appUrl, apply: true });
    const second = JSON.parse(secondStdout.trim());
    assert.equal(second.ready, true);
    assert.equal(second.migrationSummary.campaigns.created, 0);
    assert.equal(second.migrationSummary.campaigns.reused, 1);
    assert.equal(second.migrationSummary.integrations.created, 0);
    assert.equal(second.migrationSummary.integrations.reused, 1);
    assert.equal(second.migrationSummary.aiConfig.created, 0);
    assert.equal(second.migrationSummary.aiConfig.reused, 1);
    assert.equal(second.migrationSummary.flowNodes.created, 0);
    assert.equal(second.migrationSummary.flowNodes.reused, 1);
    assert.equal(second.migrationSummary.syncLogs.created, 0);
    assert.equal(second.migrationSummary.syncLogs.reused, 1);

    const storage = createPostgresStorage({ pool: createPostgresPool({ connectionString: appUrl, max: 2 }) });
    try {
      const counts = await storage.withTenantTransaction(tenantId, async tx => {
        const campaigns = await tx.query('SELECT count(*) FROM campaigns WHERE tenant_id = $1', [tenantId]);
        const integrations = await tx.query('SELECT count(*) FROM integrations WHERE tenant_id = $1', [tenantId]);
        const aiConfigs = await tx.query('SELECT count(*) FROM ai_config WHERE tenant_id = $1', [tenantId]);
        const flowNodes = await tx.query('SELECT count(*) FROM flow_nodes WHERE tenant_id = $1', [tenantId]);
        const syncLogs = await tx.query('SELECT count(*) FROM sync_logs WHERE tenant_id = $1', [tenantId]);
        return {
          campaigns: Number(campaigns.rows[0].count),
          integrations: Number(integrations.rows[0].count),
          aiConfigs: Number(aiConfigs.rows[0].count),
          flowNodes: Number(flowNodes.rows[0].count),
          syncLogs: Number(syncLogs.rows[0].count),
        };
      });
      assert.equal(counts.campaigns, 1);
      assert.equal(counts.integrations, 1);
      assert.equal(counts.aiConfigs, 1);
      assert.equal(counts.flowNodes, 1);
      assert.equal(counts.syncLogs, 1);
    } finally {
      await storage.close();
    }
  } finally {
    await rm(testDirectory, { recursive: true, force: true });
    await teardownIsolatedDatabase();
  }
});
