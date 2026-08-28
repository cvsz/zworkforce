import test from 'node:test';
import assert from 'node:assert/strict';
import { createSecretsVault } from '../server/security/secrets-vault.js';

const tenantId = 'bbbbbbbb-2222-4222-8222-bbbbbbbbbbbb';
const masterKey = 'test-master-key-for-secrets-vault-unit-tests';
const UUID_PATTERN = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;

function isValidUuid(value) {
  return typeof value === 'string' && UUID_PATTERN.test(value);
}

/**
 * Build a fake transaction context with an in-memory secrets store so that
 * reads reflect prior writes within the same context.
 */
function createFakeTx({ seed = [] } = {}) {
  const store = new Map();
  for (const row of seed) {
    store.set(row.id, { ...row });
  }
  const calls = [];
  let insertCounter = 0;

  function newId() {
    return `aaaaaaaa-1111-4111-8111-${String(insertCounter++).padStart(12, '0')}`;
  }

  function stripSensitive(row) {
    const { ciphertext: _c, iv: _i, auth_tag: _a, ...rest } = row;
    return rest;
  }

  return {
    tenantId,
    store,
    calls,
    async query(text, values = []) {
      calls.push({ text, values });
      const normalized = text.replace(/\s+/g, ' ').trim();

      if (normalized.startsWith('INSERT INTO secrets')) {
        const id = newId();
        const row = {
          id,
          tenant_id: tenantId,
          integration_id: values[1],
          name: values[2],
          provider: values[3],
          ciphertext: values[4],
          iv: values[5],
          auth_tag: values[6],
          keyId: values[7] || 'master-v1',
          status: 'active',
          createdAt: '2026-08-01T00:00:00.000Z',
          updatedAt: '2026-08-01T00:00:00.000Z',
        };
        store.set(id, row);
        return { rows: [row] };
      }
      if (normalized.startsWith('UPDATE secrets') && normalized.includes('deleted_at = now()')) {
        const id = values[1];
        const row = store.get(id);
        if (row) row.deletedAt = '2026-08-03T00:00:00.000Z';
        return { rows: row ? [{ id }] : [] };
      }
      if (normalized.startsWith('UPDATE secrets') && normalized.includes('RETURNING')) {
        const id = values[1];
        const row = store.get(id);
        if (row) row.updatedAt = '2026-08-02T00:00:00.000Z';
        return { rows: row ? [{ ...row }] : [] };
      }
      if (normalized.startsWith('SELECT') && normalized.includes('ciphertext, iv, auth_tag')) {
        const id = values[1];
        const row = store.get(id);
        return { rows: row ? [{ ...row }] : [] };
      }
      if (normalized.startsWith('SELECT') && normalized.includes('deleted_at IS NULL') && normalized.includes('ORDER BY')) {
        return { rows: [...store.values()].filter(r => !r.deletedAt).map(stripSensitive) };
      }
      if (normalized.startsWith('SELECT') && normalized.includes('deleted_at IS NULL') && normalized.includes('WHERE tenant_id = $1 AND id = $2')) {
        const id = values[1];
        const row = store.get(id);
        return { rows: row && !row.deletedAt ? [stripSensitive({ ...row })] : [] };
      }
      if (normalized.startsWith('INSERT INTO secret_access_logs')) {
        return { rows: [] };
      }
      if (normalized.startsWith('SELECT') && normalized.includes('FROM secret_access_logs')) {
        return { rows: [] };
      }
      return { rows: [] };
    },
  };
}

test('createSecretsVault requires a transaction context', () => {
  assert.throws(() => createSecretsVault({ masterKey }), /Transaction context with query\(\) is required/);
  assert.throws(() => createSecretsVault({ tx: {}, masterKey }), /Transaction context with query\(\) is required/);
});

test('createSecretsVault derives a master key from the provided string', () => {
  const tx = createFakeTx();
  assert.doesNotThrow(() => createSecretsVault({ tx, masterKey }));
});

test('storeSecret encrypts the value and never stores plaintext', async () => {
  const tx = createFakeTx();
  const vault = createSecretsVault({ tx, masterKey });

  const secret = await vault.storeSecret({ name: 'Shopify Token', provider: 'shopify', secretValue: 'shpat_super_secret_123' });

  assert.equal(secret.name, 'Shopify Token');
  assert.equal(secret.provider, 'shopify');
  assert.ok(isValidUuid(secret.id), 'should return a valid uuid');

  const insertCall = tx.calls.find(c => c.text.includes('INSERT INTO secrets'));
  assert.ok(insertCall);
  const [, , name, provider, ciphertext, iv, authTag] = insertCall.values;
  assert.equal(name, 'Shopify Token');
  assert.equal(provider, 'shopify');
  assert.notEqual(ciphertext, 'shpat_super_secret_123', 'plaintext must not be stored');
  assert.ok(iv.length > 0, 'iv must be stored');
  assert.ok(authTag.length > 0, 'auth tag must be stored');
  assert.ok(!ciphertext.includes('shpat_super_secret'));
});

test('storeSecret encrypts structured values as JSON', async () => {
  const tx = createFakeTx();
  const vault = createSecretsVault({ tx, masterKey });

  await vault.storeSecret({
    name: 'OAuth Creds',
    provider: 'shopify',
    secretValue: { accessToken: 'abc', refreshToken: 'def' },
  });

  const insertCall = tx.calls.find(c => c.text.includes('INSERT INTO secrets'));
  assert.ok(!insertCall.values[4].includes('abc'), 'access token must be encrypted');
});

test('storeSecret validates inputs', async () => {
  const tx = createFakeTx();
  const vault = createSecretsVault({ tx, masterKey });

  await assert.rejects(() => vault.storeSecret({ name: '', secretValue: 'x' }), /Secret name is required/);
  await assert.rejects(() => vault.storeSecret({ name: 'n', secretValue: null }), /Secret value is required/);
  await assert.rejects(() => vault.storeSecret({ name: 'n'.repeat(121), secretValue: 'x' }), /Secret name exceeds 120 characters/);
  await assert.rejects(() => vault.storeSecret({ name: 'n', secretValue: 'x', integrationId: 'bad-id' }), /integrationId must be a valid UUID/);
});

test('getSecret decrypts the value and logs access', async () => {
  const tx = createFakeTx();
  const vault = createSecretsVault({ tx, masterKey });
  const stored = await vault.storeSecret({ name: 'Token', provider: 'shopify', secretValue: 'shpat_secret_value' });

  const secretRow = tx.store.get(stored.id);
  const readTx = createFakeTx({ seed: [{ ...secretRow, tenant_id: tenantId, integration_id: null }] });
  const readVault = createSecretsVault({ tx: readTx, masterKey });
  const result = await readVault.getSecret({ id: stored.id, actorUserId: 'user-1', requestId: 'req-1' });

  assert.equal(result.value, 'shpat_secret_value');
  assert.equal(result.name, 'Token');

  const auditCall = readTx.calls.find(c => c.text.includes('INSERT INTO secret_access_logs'));
  assert.ok(auditCall, 'access should be audited');
  assert.equal(auditCall.values[3], 'user-1');
  assert.equal(auditCall.values[4], 'req-1');
});

test('getSecret decrypts structured values', async () => {
  const value = { accessToken: 'abc', refreshToken: 'def' };
  const tx = createFakeTx();
  const vault = createSecretsVault({ tx, masterKey });
  const stored = await vault.storeSecret({ name: 'OAuth', provider: 'shopify', secretValue: value });

  const secretRow = tx.store.get(stored.id);
  const readTx = createFakeTx({ seed: [{ ...secretRow, tenant_id: tenantId, integration_id: null }] });
  const result = await createSecretsVault({ tx: readTx, masterKey }).getSecret({ id: stored.id });
  assert.deepEqual(result.value, value);
});

test('getSecret returns null for unknown id and validates input', async () => {
  const tx = createFakeTx();
  const vault = createSecretsVault({ tx, masterKey });

  assert.equal(await vault.getSecret({ id: 'aaaaaaaa-1111-4111-8111-aaaaaaaaaaaa' }), null);
  await assert.rejects(() => vault.getSecret({ id: 'bad' }), /Valid secret id is required/);
});

test('rotateSecret re-encrypts the value and logs rotation', async () => {
  const tx = createFakeTx();
  const vault = createSecretsVault({ tx, masterKey });
  const stored = await vault.storeSecret({ name: 'Token', provider: 'shopify', secretValue: 'old_value' });

  const rotated = await vault.rotateSecret({ id: stored.id, newSecretValue: 'shpat_new_value' });
  assert.ok(rotated);

  const updateCall = tx.calls.find(c => c.text.includes('UPDATE secrets') && c.text.includes('RETURNING'));
  assert.ok(updateCall);
  assert.notEqual(updateCall.values[2], 'shpat_new_value', 'new value must be encrypted');

  const auditCall = tx.calls.find(c => c.text.includes('INSERT INTO secret_access_logs'));
  assert.ok(auditCall);
  assert.equal(auditCall.values[2], 'rotate');
});

test('rotateSecret returns null for unknown id and validates input', async () => {
  const tx = createFakeTx();
  const vault = createSecretsVault({ tx, masterKey });

  assert.equal(await vault.rotateSecret({ id: 'aaaaaaaa-1111-4111-8111-aaaaaaaaaaaa', newSecretValue: 'x' }), null);
  await assert.rejects(() => vault.rotateSecret({ id: 'bad', newSecretValue: 'x' }), /Valid secret id is required/);
  await assert.rejects(() => vault.rotateSecret({ id: 'aaaaaaaa-1111-4111-8111-aaaaaaaaaaaa', newSecretValue: null }), /New secret value is required/);
});

test('deleteSecret soft-deletes and logs deletion', async () => {
  const tx = createFakeTx();
  const vault = createSecretsVault({ tx, masterKey });
  const stored = await vault.storeSecret({ name: 'Token', provider: 'shopify', secretValue: 'v' });

  const deleted = await vault.deleteSecret({ id: stored.id });
  assert.equal(deleted, true);
  assert.ok(tx.store.get(stored.id).deletedAt, 'row should be soft-deleted');

  const updateCall = tx.calls.find(c => c.text.includes('deleted_at = now()'));
  assert.ok(updateCall);

  const auditCall = tx.calls.find(c => c.text.includes('INSERT INTO secret_access_logs'));
  assert.ok(auditCall);
  assert.equal(auditCall.values[2], 'delete');
});

test('listSecrets and getSecretMetadata do not expose ciphertext', async () => {
  const tx = createFakeTx();
  const vault = createSecretsVault({ tx, masterKey });
  await vault.storeSecret({ name: 'Token', provider: 'shopify', secretValue: 'v' });

  const list = await vault.listSecrets();
  assert.equal(list.length, 1);
  assert.equal(list[0].name, 'Token');
  assert.equal(list[0].ciphertext, undefined);
  assert.equal(list[0].iv, undefined);

  const stored = await vault.storeSecret({ name: 'Other', provider: 'shopify', secretValue: 'v' });
  const meta = await vault.getSecretMetadata(stored.id);
  assert.equal(meta.name, 'Other');
  assert.equal(meta.ciphertext, undefined);
});

test('listAccessLogs queries by tenant and validates input', async () => {
  const tx = createFakeTx();
  const vault = createSecretsVault({ tx, masterKey });

  const logs = await vault.listAccessLogs();
  assert.deepEqual(logs, []);

  const scoped = await vault.listAccessLogs({ secretId: 'aaaaaaaa-1111-4111-8111-aaaaaaaaaaaa' });
  assert.deepEqual(scoped, []);

  await assert.rejects(() => vault.listAccessLogs({ secretId: 'bad' }), /secretId must be a valid UUID/);
});
