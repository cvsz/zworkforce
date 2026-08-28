import { execFile } from 'node:child_process';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { promisify } from 'node:util';

const execFileAsync = promisify(execFile);
const __dirname = path.dirname(fileURLToPath(import.meta.url));
const migrationDirectory = path.resolve(
  __dirname,
  '../server/storage/postgres/migrations',
);

async function runPsql(databaseUrl, args) {
  if (!databaseUrl || typeof databaseUrl !== 'string') {
    throw new Error('PostgreSQL database URL is required');
  }

  const { stdout } = await execFileAsync(
    'psql',
    [databaseUrl, '--no-psqlrc', '--set', 'ON_ERROR_STOP=1', ...args],
    {
      encoding: 'utf8',
      maxBuffer: 2 * 1024 * 1024,
    },
  );
  return stdout;
}

async function executeMigrationFile(databaseUrl, fileName) {
  const migrationPath = path.join(migrationDirectory, fileName);
  await runPsql(databaseUrl, ['--single-transaction', '--file', migrationPath]);
}

export async function applyInitialMigration(databaseUrl) {
  await executeMigrationFile(databaseUrl, '001_initial.up.sql');
}

export async function rollbackInitialMigration(databaseUrl) {
  await executeMigrationFile(databaseUrl, '001_initial.down.sql');
}

export async function applyTenantIsolationMigration(databaseUrl) {
  await executeMigrationFile(databaseUrl, '002_tenant_rls.up.sql');
}

export async function rollbackTenantIsolationMigration(databaseUrl) {
  await executeMigrationFile(databaseUrl, '002_tenant_rls.down.sql');
}

export async function applyRelationalIntegrityMigration(databaseUrl) {
  await executeMigrationFile(databaseUrl, '003_tenant_relational_integrity.up.sql');
}

export async function rollbackRelationalIntegrityMigration(databaseUrl) {
  await executeMigrationFile(databaseUrl, '003_tenant_relational_integrity.down.sql');
}

export async function applySyncLogsMigration(databaseUrl) {
  await executeMigrationFile(databaseUrl, '004_sync_logs_and_idempotency.up.sql');
}

export async function rollbackSyncLogsMigration(databaseUrl) {
  await executeMigrationFile(databaseUrl, '004_sync_logs_and_idempotency.down.sql');
}

export async function applyRateLimitRecordsMigration(databaseUrl) {
  await executeMigrationFile(databaseUrl, '005_rate_limit_records.up.sql');
}

export async function rollbackRateLimitRecordsMigration(databaseUrl) {
  await executeMigrationFile(databaseUrl, '005_rate_limit_records.down.sql');
}

export async function applyMetricsMigration(databaseUrl) {
  await executeMigrationFile(databaseUrl, '006_metrics.up.sql');
}

export async function rollbackMetricsMigration(databaseUrl) {
  await executeMigrationFile(databaseUrl, '006_metrics.down.sql');
}

export async function applyAiGovernedMigration(databaseUrl) {
  await executeMigrationFile(databaseUrl, '007_ai_governed.up.sql');
}

export async function rollbackAiGovernedMigration(databaseUrl) {
  await executeMigrationFile(databaseUrl, '007_ai_governed.down.sql');
}

export async function applySoftDeleteMigration(databaseUrl) {
  await executeMigrationFile(databaseUrl, '008_soft_delete.up.sql');
}

export async function rollbackSoftDeleteMigration(databaseUrl) {
  await executeMigrationFile(databaseUrl, '008_soft_delete.down.sql');
}

export async function applyCommerceAttributionMigration(databaseUrl) {
  await executeMigrationFile(databaseUrl, '009_commerce_attribution.up.sql');
}

export async function rollbackCommerceAttributionMigration(databaseUrl) {
  await executeMigrationFile(databaseUrl, '009_commerce_attribution.down.sql');
}

export async function applyCampaignWorkersMigration(databaseUrl) {
  await executeMigrationFile(databaseUrl, '010_campaign_workers.up.sql');
}

export async function rollbackCampaignWorkersMigration(databaseUrl) {
  await executeMigrationFile(databaseUrl, '010_campaign_workers.down.sql');
}

export async function applySecurityMigration(databaseUrl) {
  await executeMigrationFile(databaseUrl, '011_security.up.sql');
}

export async function rollbackSecurityMigration(databaseUrl) {
  await executeMigrationFile(databaseUrl, '011_security.down.sql');
}

export async function executeSql(databaseUrl, sql) {
  await runPsql(databaseUrl, ['--quiet', '--command', sql]);
}

export async function queryScalar(databaseUrl, sql) {
  const stdout = await runPsql(databaseUrl, [
    '--quiet',
    '--tuples-only',
    '--no-align',
    '--command',
    sql,
  ]);
  return stdout.trim();
}

export async function listPublicTables(databaseUrl) {
  const stdout = await runPsql(databaseUrl, [
    '--tuples-only',
    '--no-align',
    '--command',
    "SELECT tablename FROM pg_catalog.pg_tables WHERE schemaname = 'public' ORDER BY tablename;",
  ]);

  return stdout
    .split('\n')
    .map(value => value.trim())
    .filter(Boolean);
}
