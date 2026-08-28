import test from 'node:test';
import assert from 'node:assert/strict';
import { createAuditMiddleware } from '../server/storage/postgres/audit-middleware.js';

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

test('createAuditMiddleware returns a no-op when enforcement is disabled', async () => {
  const middleware = createAuditMiddleware(null);
  const req = { method: 'POST', path: '/roles' };
  const res = {};
  let nextCalled = false;
  await middleware(req, res, () => {
    nextCalled = true;
  });
  assert.equal(nextCalled, true);
});

test('createAuditMiddleware returns a no-op when pool is missing', async () => {
  process.env.ZOK_AUDIT_ENFORCEMENT = 'enabled';
  const middleware = createAuditMiddleware(null);
  const req = { method: 'POST', path: '/roles' };
  const res = {};
  let nextCalled = false;
  await middleware(req, res, () => {
    nextCalled = true;
  });
  assert.equal(nextCalled, true);
  delete process.env.ZOK_AUDIT_ENFORCEMENT;
});

test('middleware assigns a requestId when one is not present', async () => {
  process.env.ZOK_AUDIT_ENFORCEMENT = 'enabled';
  const fake = createFakePool();
  const middleware = createAuditMiddleware(fake.pool);
  const req = {
    method: 'GET',
    path: '/roles',
    headers: {},
    user: {},
  };
  const res = {};
  await middleware(req, res, () => {});
  assert.ok(req.requestId);
  assert.ok(/^[0-9a-f-]+$/i.test(req.requestId));
  delete process.env.ZOK_AUDIT_ENFORCEMENT;
});

test('middleware preserves an existing x-request-id header', async () => {
  process.env.ZOK_AUDIT_ENFORCEMENT = 'enabled';
  const fake = createFakePool();
  const middleware = createAuditMiddleware(fake.pool);
  const req = {
    method: 'GET',
    path: '/roles',
    headers: { 'x-request-id': 'ext-req-1' },
    user: {},
  };
  const res = {};
  await middleware(req, res, () => {});
  assert.equal(req.requestId, 'ext-req-1');
  delete process.env.ZOK_AUDIT_ENFORCEMENT;
});

test('middleware emits for POST mutation routes', async () => {
  process.env.ZOK_AUDIT_ENFORCEMENT = 'enabled';
  const fake = createFakePool();
  const middleware = createAuditMiddleware(fake.pool);
  const req = {
    method: 'POST',
    path: '/roles',
    originalUrl: '/api/roles',
    headers: {},
    user: { tenantId: 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa', id: 'user-1' },
    params: {},
    get: () => null,
    ip: '127.0.0.1',
    socket: { remoteAddress: '::1' },
  };
  const res = {};
  await middleware(req, res, () => {});
  assert.equal(fake.clients.length, 1);
  assert.ok(fake.clients[0].text.includes('INSERT INTO audit_events'));
  assert.equal(fake.clients[0].values[3], 'roles');
  assert.equal(fake.clients[0].values[4], null);
  delete process.env.ZOK_AUDIT_ENFORCEMENT;
});

test('middleware emits for PUT mutation routes', async () => {
  process.env.ZOK_AUDIT_ENFORCEMENT = 'enabled';
  const fake = createFakePool();
  const middleware = createAuditMiddleware(fake.pool);
  const req = {
    method: 'PUT',
    path: '/roles/role-1',
    originalUrl: '/api/roles/role-1',
    headers: {},
    user: { tenantId: 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa', id: 'user-1' },
    params: { id: 'role-1' },
    get: () => null,
    ip: '127.0.0.1',
    socket: { remoteAddress: '::1' },
  };
  const res = {};
  await middleware(req, res, () => {});
  assert.equal(fake.clients[0].values[4], 'role-1');
  delete process.env.ZOK_AUDIT_ENFORCEMENT;
});

test('middleware emits for DELETE mutation routes', async () => {
  process.env.ZOK_AUDIT_ENFORCEMENT = 'enabled';
  const fake = createFakePool();
  const middleware = createAuditMiddleware(fake.pool);
  const req = {
    method: 'DELETE',
    path: '/campaigns/camp-1',
    originalUrl: '/api/campaigns/camp-1',
    headers: {},
    user: { tenantId: 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa', id: 'user-1' },
    params: { id: 'camp-1' },
    get: () => null,
    ip: '127.0.0.1',
    socket: { remoteAddress: '::1' },
  };
  const res = {};
  await middleware(req, res, () => {});
  assert.equal(fake.clients[0].values[4], 'camp-1');
  delete process.env.ZOK_AUDIT_ENFORCEMENT;
});

test('middleware skips GET requests', async () => {
  process.env.ZOK_AUDIT_ENFORCEMENT = 'enabled';
  const fake = createFakePool();
  const middleware = createAuditMiddleware(fake.pool);
  const req = {
    method: 'GET',
    path: '/roles',
    headers: {},
    user: { tenantId: 't' },
  };
  const res = {};
  await middleware(req, res, () => {});
  assert.equal(fake.clients.length, 0);
  delete process.env.ZOK_AUDIT_ENFORCEMENT;
});

test('middleware skips auth routes', async () => {
  process.env.ZOK_AUDIT_ENFORCEMENT = 'enabled';
  const fake = createFakePool();
  const middleware = createAuditMiddleware(fake.pool);
  const req = {
    method: 'POST',
    path: '/auth/login',
    headers: {},
    user: { tenantId: 't' },
  };
  const res = {};
  await middleware(req, res, () => {});
  assert.equal(fake.clients.length, 0);
  delete process.env.ZOK_AUDIT_ENFORCEMENT;
});

test('middleware skips requests without tenant context', async () => {
  process.env.ZOK_AUDIT_ENFORCEMENT = 'enabled';
  const fake = createFakePool();
  const middleware = createAuditMiddleware(fake.pool);
  const req = {
    method: 'POST',
    path: '/roles',
    headers: {},
    user: {},
  };
  const res = {};
  await middleware(req, res, () => {});
  assert.equal(fake.clients.length, 0);
  delete process.env.ZOK_AUDIT_ENFORCEMENT;
});

test('middleware is non-blocking on database errors', async () => {
  process.env.ZOK_AUDIT_ENFORCEMENT = 'enabled';
  const fake = createFakePool();
  fake.pool.connect = async () => ({
    async query() {
      throw new Error('database error');
    },
    release() {},
  });
  const middleware = createAuditMiddleware(fake.pool);
  const req = {
    method: 'POST',
    path: '/roles',
    originalUrl: '/api/roles',
    headers: {},
    user: { tenantId: 't', id: 'u' },
    params: {},
    get: () => null,
    ip: '127.0.0.1',
    socket: { remoteAddress: '::1' },
  };
  const res = {};
  await assert.doesNotReject(() => middleware(req, res, () => {}));
  delete process.env.ZOK_AUDIT_ENFORCEMENT;
});
