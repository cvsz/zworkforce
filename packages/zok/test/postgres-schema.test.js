import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';

const upPath = new URL('../server/storage/postgres/migrations/001_initial.up.sql', import.meta.url);
const downPath = new URL('../server/storage/postgres/migrations/001_initial.down.sql', import.meta.url);

const requiredTables = [
  'tenants',
  'roles',
  'users',
  'user_roles',
  'contacts',
  'conversations',
  'messages',
  'campaigns',
  'integrations',
  'consent_records',
  'sessions',
  'audit_events',
];

const tenantScopedTables = [
  'roles',
  'users',
  'contacts',
  'conversations',
  'messages',
  'campaigns',
  'integrations',
  'consent_records',
  'sessions',
  'audit_events',
];

function normalized(sql) {
  return sql.replace(/--.*$/gm, '').replace(/\s+/g, ' ').trim().toLowerCase();
}

test('initial PostgreSQL migration defines the durable multi-tenant data model', async () => {
  const sql = normalized(await readFile(upPath, 'utf8'));

  for (const table of requiredTables) {
    assert.match(sql, new RegExp(`create table ${table} \\(`), `missing ${table} table`);
  }

  for (const table of tenantScopedTables) {
    const tableMatch = sql.match(new RegExp(`create table ${table} \\((.*?)\\);`));
    assert.ok(tableMatch, `unable to inspect ${table}`);
    assert.match(tableMatch[1], /tenant_id uuid not null/, `${table} must require tenant_id`);
    assert.match(
      tableMatch[1],
      /foreign key \(tenant_id\) references tenants\(id\) on delete cascade/,
      `${table} must enforce tenant ownership`,
    );
  }

  assert.match(sql, /unique \(tenant_id, email\)/, 'users must prevent duplicate emails within a tenant');
  assert.match(sql, /unique \(tenant_id, name\)/, 'roles must prevent duplicate names within a tenant');
  assert.match(sql, /unique \(tenant_id, provider, external_id\)/, 'integrations must be tenant/provider scoped');
  assert.match(sql, /unique \(tenant_id, token_hash\)/, 'sessions must prevent duplicate tenant session tokens');
  assert.match(sql, /check \(direction in \('inbound', 'outbound'\)\)/, 'messages must constrain direction');
  assert.match(sql, /check \(status in \('draft', 'scheduled', 'running', 'completed', 'cancelled'\)\)/, 'campaign status must be constrained');
});

test('down migration explicitly removes every table created by the initial schema', async () => {
  const sql = normalized(await readFile(downPath, 'utf8'));

  for (const table of requiredTables.toReversed()) {
    assert.match(sql, new RegExp(`drop table if exists ${table}`), `down migration must remove ${table}`);
  }
});
