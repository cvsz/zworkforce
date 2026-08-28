import test from 'node:test';
import assert from 'node:assert/strict';
import { createApiKeyManager } from '../server/security/api-key-manager.js';

const tenantId = 'bbbbbbbb-2222-4222-8222-bbbbbbbbbbbb';

function makeRecord(overrides = {}) {
  return {
    id: 'aaaaaaaa-1111-4111-8111-aaaaaaaaaaaa',
    name: 'Test Key',
    prefix: 'abcd1234',
    status: 'active',
    expiresAt: '2026-09-01T00:00:00.000Z',
    gracePeriodEndsAt: null,
    lastUsedAt: null,
    rotatedFromId: null,
    createdAt: '2026-08-01T00:00:00.000Z',
    updatedAt: '2026-08-01T00:00:00.000Z',
    ...overrides,
  };
}

/**
 * Build a fake transaction context. Rows are indexed by both id and key_hash
 * so verify()-by-hash and getById() lookups reflect prior writes.
 */
function createFakeTx({ seed = [] } = {}) {
  const store = new Map();
  const byHash = new Map();
  for (const row of seed) {
    store.set(row.id, { ...row });
    if (row.keyHash) byHash.set(row.keyHash, row);
  }
  const calls = [];
  let insertCounter = 0;

  function echoInsert(values) {
    const id = `aaaaaaaa-1111-4111-8111-${String(insertCounter++).padStart(12, '0')}`;
    return {
      id,
      name: values[1],
      prefix: values[3],
      status: values[4],
      expiresAt: values[5],
      gracePeriodEndsAt: null,
      lastUsedAt: null,
      rotatedFromId: values.length > 6 ? values[6] : null,
      createdAt: '2026-08-01T00:00:00.000Z',
      updatedAt: '2026-08-01T00:00:00.000Z',
    };
  }

  return {
    tenantId,
    store,
    byHash,
    calls,
    async query(text, values = []) {
      calls.push({ text, values });
      const normalized = text.replace(/\s+/g, ' ').trim();

      if (normalized.startsWith('INSERT INTO api_keys')) {
        const row = echoInsert(values);
        store.set(row.id, row);
        byHash.set(values[2], row);
        return { rows: [row] };
      }
      if (normalized.startsWith('UPDATE api_keys') && normalized.includes("status = 'rotated'")) {
        const id = values[values.length - 1];
        const row = store.get(id);
        if (row) {
          row.status = 'rotated';
          row.gracePeriodEndsAt = values[1];
          row.updatedAt = '2026-08-02T00:00:00.000Z';
        }
        return { rows: row ? [{ id }] : [] };
      }
      if (normalized.startsWith('UPDATE api_keys') && normalized.includes("status = 'revoked'")) {
        const id = values[values.length - 1];
        const row = store.get(id);
        if (!row) return { rows: [] };
        row.status = 'revoked';
        return { rows: [{ ...row }] };
      }
      if (normalized.startsWith('UPDATE api_keys') && normalized.includes("status = 'expired'")) {
        return { rows: [] };
      }
      if (normalized.startsWith('UPDATE api_keys') && normalized.includes('last_used_at = now()')) {
        const id = values[0];
        const row = store.get(id);
        if (row) row.lastUsedAt = new Date().toISOString();
        return { rows: [] };
      }
      if (normalized.startsWith('SELECT') && normalized.includes('WHERE key_hash = $1')) {
        const row = byHash.get(values[0]);
        return { rows: row ? [{ ...row, tenantId }] : [] };
      }
      if (normalized.startsWith('SELECT') && normalized.includes('WHERE tenant_id = $1 AND id = $2')) {
        const row = store.get(values[1]);
        return { rows: row ? [{ ...row }] : [] };
      }
      if (normalized.startsWith('SELECT') && normalized.includes('deleted_at IS NULL ORDER BY')) {
        return { rows: [...store.values()] };
      }
      return { rows: [] };
    },
  };
}

test('createApiKeyManager requires a transaction context', () => {
  assert.throws(() => createApiKeyManager(null), /Transaction context with query\(\) is required/);
  assert.throws(() => createApiKeyManager({}), /Transaction context with query\(\) is required/);
});

test('create generates a key, stores only the hash, and returns the plaintext once', async () => {
  const tx = createFakeTx();
  const manager = createApiKeyManager(tx);

  const result = await manager.create({ name: 'Production Key', expiresInDays: 30 });

  assert.equal(typeof result.key, 'string');
  assert.ok(result.key.length > 30, 'key should be long');
  assert.equal(result.record.name, 'Production Key');
  assert.equal(result.record.status, 'active');

  const insertCall = tx.calls.find(c => c.text.includes('INSERT INTO api_keys'));
  assert.ok(insertCall);
  const hashValue = insertCall.values[2];
  const prefixValue = insertCall.values[3];
  assert.ok(hashValue.length > 0);
  assert.ok(prefixValue.length > 0);
  assert.notEqual(hashValue, result.key, 'plaintext key must not be stored');
  assert.notEqual(hashValue, prefixValue, 'hash and prefix must differ');
  assert.ok(!insertCall.values.includes(result.key), 'plaintext must not appear in any stored value');
});

test('create defaults to 90-day expiry and validates name', async () => {
  const tx = createFakeTx();
  const manager = createApiKeyManager(tx);

  await assert.rejects(() => manager.create({ name: '' }), /Key name is required/);
  await assert.rejects(() => manager.create({}), /Key name is required/);
  await assert.rejects(() => manager.create({ name: 'a'.repeat(121) }), /Key name exceeds 120 characters/);

  const result = await manager.create({ name: '  Defaulted  ' });
  assert.equal(result.record.name, 'Defaulted');
  const insertCall = tx.calls.find(c => c.text.includes('INSERT INTO api_keys'));
  assert.ok(new Date(insertCall.values[5]).getTime() > Date.now());
});

test('create validates expiresInDays range', async () => {
  const tx = createFakeTx();
  const manager = createApiKeyManager(tx);

  await assert.rejects(() => manager.create({ name: 'k', expiresInDays: 0 }), /between/);
  await assert.rejects(() => manager.create({ name: 'k', expiresInDays: 9999 }), /between/);
  await assert.rejects(() => manager.create({ name: 'k', expiresInDays: 'abc' }), /expiresInDays/);
});

test('verify returns the record for a valid active key and updates last used', async () => {
  const tx = createFakeTx();
  const manager = createApiKeyManager(tx);
  const created = await manager.create({ name: 'Verify Key' });

  const result = await manager.verify(created.key);
  assert.ok(result, 'should verify a valid key');
  assert.equal(result.id, created.record.id);
  assert.equal(result.tenantId, tenantId);

  const updateCall = tx.calls.find(c => c.text.includes('last_used_at = now()'));
  assert.ok(updateCall, 'should update last_used_at');
});

test('verify returns null for invalid, revoked, and unknown keys', async () => {
  const tx = createFakeTx();
  const manager = createApiKeyManager(tx);

  assert.equal(await manager.verify(''), null);
  assert.equal(await manager.verify(null), null);
  assert.equal(await manager.verify('this-key-does-not-exist'), null);

  const created = await manager.create({ name: 'To Revoke' });
  // Manually revoke in the store to simulate a revoked row.
  tx.store.get(created.record.id).status = 'revoked';
  assert.equal(await manager.verify(created.key), null);
});

test('verify honors the grace period for rotated keys', async () => {
  const tx = createFakeTx();
  const manager = createApiKeyManager(tx);
  const created = await manager.create({ name: 'Grace Key' });

  const row = tx.store.get(created.record.id);
  row.status = 'rotated';
  row.gracePeriodEndsAt = new Date(Date.now() + 86400000).toISOString();
  row.expiresAt = new Date(Date.now() - 1000).toISOString();

  const result = await manager.verify(created.key);
  assert.ok(result, 'rotated key should be valid within grace period');
  assert.equal(result.status, 'rotated');
});

test('verify rejects a rotated key past its grace period', async () => {
  const tx = createFakeTx();
  const manager = createApiKeyManager(tx);
  const created = await manager.create({ name: 'Expired Grace' });

  const row = tx.store.get(created.record.id);
  row.status = 'rotated';
  row.gracePeriodEndsAt = new Date(Date.now() - 1000).toISOString();
  row.expiresAt = new Date(Date.now() + 86400000).toISOString();

  assert.equal(await manager.verify(created.key), null);
});

test('rotate creates a new active key and marks the old one rotated with a grace period', async () => {
  const tx = createFakeTx();
  const manager = createApiKeyManager(tx);
  const created = await manager.create({ name: 'Rotate Me' });

  const result = await manager.rotate(created.record.id, { gracePeriodDays: 7 });
  assert.ok(result.key);
  assert.notEqual(result.key, created.key);
  assert.equal(result.record.status, 'active');
  assert.equal(result.record.rotatedFromId, created.record.id);

  const oldRow = tx.store.get(created.record.id);
  assert.equal(oldRow.status, 'rotated');
  assert.ok(oldRow.gracePeriodEndsAt);
});

test('rotate validates inputs and returns null for missing keys', async () => {
  const tx = createFakeTx();
  const manager = createApiKeyManager(tx);

  await assert.rejects(() => manager.rotate('not-a-uuid'), /Valid key id is required/);
  const missing = await manager.rotate('aaaaaaaa-1111-4111-8111-aaaaaaaaaaaa');
  assert.equal(missing, null);
  await assert.rejects(() => manager.rotate('aaaaaaaa-1111-4111-8111-aaaaaaaaaaaa', { gracePeriodDays: -1 }), /gracePeriodDays/);
  await assert.rejects(() => manager.rotate('aaaaaaaa-1111-4111-8111-aaaaaaaaaaaa', { gracePeriodDays: 200 }), /gracePeriodDays/);
});

test('revoke marks a key revoked and returns the record', async () => {
  const tx = createFakeTx();
  const manager = createApiKeyManager(tx);
  const created = await manager.create({ name: 'Revoke Me' });

  const revoked = await manager.revoke(created.record.id);
  assert.ok(revoked);
  assert.equal(revoked.status, 'revoked');

  const notFound = await manager.revoke('aaaaaaaa-1111-4111-8111-bbbbbbbbbbbb');
  assert.equal(notFound, null);
});

test('list and getById query by tenant', async () => {
  const tx = createFakeTx();
  const manager = createApiKeyManager(tx);
  const first = await manager.create({ name: 'Key One' });
  await manager.create({ name: 'Key Two' });

  const list = await manager.list();
  assert.equal(list.length, 2);
  assert.equal(list[0].prefix.length > 0, true);

  const byId = await manager.getById(first.record.id);
  assert.ok(byId);
  assert.equal(byId.name, 'Key One');

  await assert.rejects(() => manager.getById('not-uuid'), /Valid key id is required/);
  assert.equal(await manager.getById('aaaaaaaa-1111-4111-8111-bbbbbbbbbbbb'), null);
});

test('purgeExpired marks active past-due keys as expired', async () => {
  const tx = {
    tenantId,
    async query(text, values = []) {
      if (text.includes("status = 'expired'")) {
        return { rows: [{ id: 'x' }, { id: 'y' }] };
      }
      return { rows: [] };
    },
  };
  const count = await createApiKeyManager(tx).purgeExpired();
  assert.equal(count, 2);
});
