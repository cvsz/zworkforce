import test from 'node:test';
import assert from 'node:assert/strict';
import { pbkdf2Sync, randomBytes } from 'node:crypto';
import os from 'node:os';
import path from 'node:path';
import { mkdtemp, rm } from 'node:fs/promises';
import { requirePermission } from '../server/storage/postgres/rbac-middleware.js';

const PASSWORD = 'secure-test-password-1234';
const TENANT_ID = 'bbbbbbbb-2222-4222-8222-bbbbbbbbbbbb';
const USER_ID = 'eeeeeeee-5555-4555-8555-eeeeeeeeeeee';

function hashPassword(password) {
  const salt = randomBytes(16).toString('base64url');
  const derived = pbkdf2Sync(password, salt, 310000, 32, 'sha256').toString('base64url');
  return `pbkdf2_sha256$310000$${salt}$${derived}`;
}

const ADMIN_HASH = hashPassword(PASSWORD);

let server;
let baseUrl;
let cookies;

async function startTestServer() {
  const testDir = await mkdtemp(path.join(os.tmpdir(), 'zok-rbac-'));
  const dbFile = path.join(testDir, 'db.json');

  process.env.NODE_ENV = 'test';
  process.env.ZOK_NO_LISTEN = 'true';
  process.env.ZOK_DB_FILE = dbFile;
  process.env.ZOK_ADMIN_EMAIL = 'admin@example.test';
  process.env.ZOK_ADMIN_PASSWORD_HASH = ADMIN_HASH;
  process.env.ZOK_ADMIN_TENANT_ID = TENANT_ID;
  process.env.ZOK_ALLOWED_ORIGINS = 'http://127.0.0.1:5175';
  process.env.ZOK_POSTGRES_URL = '';
  process.env.ZOK_CHAT_STORAGE = 'json';
  process.env.ZOK_RBAC_ENFORCEMENT = 'disabled';

  const { startServer } = await import('../server.js');
  server = startServer(0);
  await new Promise(resolve => server.once('listening', resolve));
  baseUrl = `http://127.0.0.1:${server.address().port}`;

  const login = await fetch(`${baseUrl}/api/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email: 'admin@example.test', password: PASSWORD }),
  });
  assert.equal(login.status, 200);
  const setCookie = login.headers.get('set-cookie');
  const sessionMatch = setCookie.match(/zok_session=([^;,]+)/);
  const csrfMatch = setCookie.match(/zok_csrf=([^;,]+)/);
  cookies = `zok_session=${sessionMatch[1]}; zok_csrf=${csrfMatch[1]}`;

  return testDir;
}

async function stopTestServer(testDir) {
  await new Promise(resolve => server.close(resolve));
  if (testDir) await rm(testDir, { recursive: true, force: true });
}

test('RBAC is deny-by-default when enforcement is disabled', async () => {
  const testDir = await startTestServer();
  try {
    const response = await fetch(`${baseUrl}/api/campaigns`, {
      method: 'POST',
      headers: {
        Cookie: cookies,
        'Content-Type': 'application/json',
        'X-CSRF-Token': cookies.match(/zok_csrf=([^;]+)/)?.[1] || '',
      },
      body: JSON.stringify({ name: 'Test', channel: 'line', target: 'test' }),
    });
    assert.equal(response.status, 201);
  } finally {
    await stopTestServer(testDir);
  }
});

test('RBAC middleware returns 403 for unauthenticated requests when enabled', async () => {
  const testDir = await startTestServer();
  try {
    const original = process.env.ZOK_RBAC_ENFORCEMENT;
    process.env.ZOK_RBAC_ENFORCEMENT = 'enabled';

    const { createRbacMiddleware } = await import('../server/storage/postgres/rbac-middleware.js');
    const middleware = createRbacMiddleware({
      async withTenantTransaction(tenantId, operation) {
        return operation({
          tenantId,
          async query() {
            return { rows: [] };
          },
        });
      },
    });

    const req = { user: null };
    const res = {
      status(code) {
        this.statusCode = code;
        return this;
      },
      json(body) {
        this.body = body;
      },
    };
    const next = () => {};

    await middleware(req, res, next);
    assert.equal(res.statusCode, 403);
    assert.deepEqual(res.body, { error: 'Permission denied' });

    process.env.ZOK_RBAC_ENFORCEMENT = original;
  } finally {
    await stopTestServer(testDir);
  }
});

test('RBAC middleware returns 403 when user lacks required permission', async () => {
  const testDir = await startTestServer();
  try {
    const original = process.env.ZOK_RBAC_ENFORCEMENT;
    process.env.ZOK_RBAC_ENFORCEMENT = 'enabled';

    const { createRbacMiddleware } = await import('../server/storage/postgres/rbac-middleware.js');
    const middleware = createRbacMiddleware({
      async withTenantTransaction(tenantId, operation) {
        return operation({
          tenantId,
          async query() {
            return { rows: [] };
          },
        });
      },
    });

    const req = {
      user: { id: USER_ID, tenantId: TENANT_ID },
      rbacCache: { tenantId: TENANT_ID, entries: new Map() },
      rbacRequired: 'admin:*',
    };
    const res = {
      status(code) {
        this.statusCode = code;
        return this;
      },
      json(body) {
        this.body = body;
      },
    };
    const next = () => {};

    await middleware(req, res, next);
    assert.equal(res.statusCode, 403);
    assert.deepEqual(res.body, { error: 'Permission denied' });

    process.env.ZOK_RBAC_ENFORCEMENT = original;
  } finally {
    await stopTestServer(testDir);
  }
});

test('RBAC middleware passes when user has required permission', async () => {
  const testDir = await startTestServer();
  try {
    const original = process.env.ZOK_RBAC_ENFORCEMENT;
    process.env.ZOK_RBAC_ENFORCEMENT = 'enabled';

    const { createRbacMiddleware } = await import('../server/storage/postgres/rbac-middleware.js');
    const middleware = createRbacMiddleware({
      async withTenantTransaction(tenantId, operation) {
        return operation({
          tenantId,
          async query() {
            return { rows: [{ permissions: { 'campaigns:write': true } }] };
          },
        });
      },
    });

    let passed = false;
    const req = {
      user: { id: USER_ID, tenantId: TENANT_ID },
      rbacCache: { tenantId: TENANT_ID, entries: new Map() },
      rbacRequired: 'campaigns:write',
    };
    const res = {};
    const next = () => { passed = true; };

    await middleware(req, res, next);
    assert.equal(passed, true);

    process.env.ZOK_RBAC_ENFORCEMENT = original;
  } finally {
    await stopTestServer(testDir);
  }
});

test('requirePermission sets required permission on request', () => {
  const middleware = requirePermission('chats:write');

  const req = {};
  const res = {};
  const next = () => {};

  middleware(req, res, next);
  assert.equal(req.rbacRequired, 'chats:write');
});

test('requirePermission rejects empty permission string', () => {
  assert.throws(() => requirePermission(''), /permission string is required/i);
  assert.throws(() => requirePermission('   '), /permission string is required/i);
});
