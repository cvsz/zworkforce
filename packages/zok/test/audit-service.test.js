import test from 'node:test';
import assert from 'node:assert/strict';
import { createAuditService } from '../server/storage/postgres/audit-service.js';

function createFakePool({ failQuery = false } = {}) {
  const clients = [];

  const client = {
    async query(text, values) {
      clients.push({ text, values });
      if (failQuery) {
        throw new Error('database error');
      }
      return { rows: [] };
    },
    release() {},
  };

  return {
    pool: {
      async connect() {
        return client;
      },
    },
    clients,
  };
}

test('createAuditService requires a pool', () => {
  assert.throws(() => createAuditService(null), /pg Pool is required/);
  assert.throws(() => createAuditService({}), /pg Pool is required/);
});

test('emit validates required fields and logs errors for invalid input', async () => {
  const fake = createFakePool();
  const service = createAuditService(fake.pool);

  await assert.doesNotReject(async () => service.emit(null));
  await assert.doesNotReject(async () => service.emit({}));
  await assert.doesNotReject(async () => service.emit({ action: 'test' }));

  assert.equal(fake.clients.length, 0);
});

test('emit inserts audit events with parameterized queries', async () => {
  const fake = createFakePool();
  const service = createAuditService(fake.pool);

  const occurredAt = '2024-01-01T00:00:00.000Z';
  await service.emit({
    tenant_id: 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa',
    actor_user_id: 'bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb',
    action: 'campaign.create',
    resource_type: 'campaign',
    resource_id: 'camp-1',
    request_id: 'req-123',
    occurred_at: occurredAt,
    metadata: { channel: 'line' },
  });

  assert.equal(fake.clients.length, 1);
  assert.ok(fake.clients[0].text.includes('INSERT INTO audit_events'));
  assert.deepEqual(fake.clients[0].values, [
    'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa',
    'bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb',
    'campaign.create',
    'campaign',
    'camp-1',
    'req-123',
    { channel: 'line' },
    occurredAt,
  ]);
});

test('emit uses null for missing resource_id', async () => {
  const fake = createFakePool();
  const service = createAuditService(fake.pool);

  await service.emit({
    tenant_id: 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa',
    actor_user_id: null,
    action: 'auth.login',
    resource_type: 'auth',
    resource_id: undefined,
    request_id: 'req-456',
    occurred_at: new Date().toISOString(),
  });

  assert.deepEqual(fake.clients[0].values[4], null);
});

test('emit is non-blocking on database errors', async () => {
  const fake = createFakePool({ failQuery: true });
  const service = createAuditService(fake.pool);

  await assert.doesNotReject(
    async () =>
      service.emit({
        tenant_id: 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa',
        actor_user_id: 'bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb',
        action: 'test',
        resource_type: 'test',
        resource_id: '1',
        request_id: 'req-789',
        occurred_at: new Date().toISOString(),
      })
  );
});

test('emit uses default empty metadata when not provided', async () => {
  const fake = createFakePool();
  const service = createAuditService(fake.pool);

  await service.emit({
    tenant_id: 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa',
    actor_user_id: 'bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb',
    action: 'test',
    resource_type: 'test',
    resource_id: '1',
    request_id: 'req-999',
    occurred_at: new Date().toISOString(),
  });

  assert.deepEqual(fake.clients[0].values[6], {});
});
