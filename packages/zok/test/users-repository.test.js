process.env.NODE_ENV = 'test';
process.env.ZOK_NO_LISTEN = 'true';

import test from 'node:test';
import assert from 'node:assert/strict';
import { createUsersRepository } from '../server/storage/postgres/users-repository.js';
import { createPasswordHash } from '../server/utils/password.js';

const tenantId = 'bbbbbbbb-2222-4222-8222-bbbbbbbbbbbb';
const userId = 'eeeeeeee-5555-4555-8555-eeeeeeeeeeee';

test('users repository validates tenant transaction context', () => {
  assert.throws(
    () => createUsersRepository({ query: async () => ({ rows: [] }) }),
    /tenant transaction context is required/i
  );
});

test('users repository creates user with hashed password and strips hash from response', async () => {
  const calls = [];
  const tx = {
    tenantId,
    async query(text, _values = []) {
      calls.push({ text, values: _values });
      if (/INSERT INTO users/i.test(text)) {
        return {
          rows: [{
            id: userId,
            tenantId,
            email: 'test@example.test',
            displayName: 'Test User',
            passwordHash: 'pbkdf2_sha256$310000$mock-salt$mock-hash',
            status: 'active',
          }],
        };
      }
      return { rows: [] };
    },
  };
  const repo = createUsersRepository(tx);

  const user = await repo.create({
    email: 'test@example.test',
    displayName: 'Test User',
    password: 'secure-password-1234',
  });

  assert.equal(user.id, userId);
  assert.equal(user.email, 'test@example.test');
  assert.equal(user.displayName, 'Test User');
  assert.equal(user.status, 'active');
  assert.equal(user.passwordHash, undefined);
  assert.ok(calls[0].values[3].startsWith('pbkdf2_sha256$310000$'));
});

test('users repository normalizes email and trims display name', async () => {
  const calls = [];
  const tx = {
    tenantId,
    async query(text, _values = []) {
      calls.push({ text, values: _values });
      return { rows: [{ id: userId, email: 'trimmed@example.test', displayName: 'Trimmed', status: 'active' }] };
    },
  };
  const repo = createUsersRepository(tx);

  await repo.create({
    email: '  TRIMMED@EXAMPLE.TEST  ',
    displayName: '  Trimmed Name  ',
    password: 'secure-password-1234',
  });

  assert.equal(calls[0].values[1], 'trimmed@example.test');
  assert.equal(calls[0].values[2], 'Trimmed Name');
});

test('users repository rejects invalid email', async () => {
  const tx = {
    tenantId,
    query: async () => ({ rows: [] }),
  };
  const repo = createUsersRepository(tx);

  await assert.rejects(() => repo.create({ email: 'not-email', password: 'secure-password-1234' }), /valid email is required/i);
  await assert.rejects(() => repo.create({ password: 'secure-password-1234' }), /valid email is required/i);
});

test('users repository creates user with null password hash when password is too short', async () => {
  const calls = [];
  const tx = {
    tenantId,
    async query(text, _values = []) {
      calls.push({ text, values: _values });
      return {
        rows: [{
          id: userId,
          tenantId,
          email: 'test@example.test',
          displayName: 'Test',
          status: 'active',
        }],
      };
    },
  };
  const repo = createUsersRepository(tx);

  const user = await repo.create({ email: 'test@example.test', displayName: 'Test', password: 'short' });
  assert.equal(user.id, userId);
  assert.equal(user.passwordHash, undefined);
  assert.equal(calls[0].values[3], null);
});

test('users repository findById returns user without password hash', async () => {
  const tx = {
    tenantId,
    async query(text, _values = []) {
      return {
        rows: [{
          id: userId,
          email: 'test@example.test',
          displayName: 'Test',
          status: 'active',
        }],
      };
    },
  };
  const repo = createUsersRepository(tx);

  const user = await repo.findById(userId);
  assert.equal(user.id, userId);
  assert.equal(user.email, 'test@example.test');
  assert.equal(user.status, 'active');
});

test('users repository findByEmail finds by normalized email', async () => {
  const calls = [];
  const tx = {
    tenantId,
    async query(text, _values = []) {
      calls.push({ text, values: _values });
      return {
        rows: [{
          id: userId,
          email: 'test@example.test',
          displayName: 'Test',
          status: 'active',
        }],
      };
    },
  };
  const repo = createUsersRepository(tx);

  const user = await repo.findByEmail('Test@Example.Test');
  assert.equal(user.id, userId);
  assert.equal(calls[0].values[1], 'test@example.test');
});

test('users repository list returns all users', async () => {
  const tx = {
    tenantId,
    async query() {
      return { rows: [{ id: '1' }, { id: '2' }] };
    },
  };
  const repo = createUsersRepository(tx);

  const users = await repo.list();
  assert.deepEqual(users, [{ id: '1' }, { id: '2' }]);
});

test('users repository update modifies specified fields', async () => {
  const calls = [];
  const tx = {
    tenantId,
    async query(text, _values = []) {
      calls.push({ text, values: _values });
      return { rows: [{ id: userId, email: 'new@example.test', displayName: 'New Name', status: 'active' }] };
    },
  };
  const repo = createUsersRepository(tx);

  const user = await repo.update(userId, {
    email: 'new@example.test',
    displayName: 'New Name',
  });

  assert.equal(user.email, 'new@example.test');
  assert.equal(user.displayName, 'New Name');
});

test('users repository delete removes user', async () => {
  const tx = {
    tenantId,
    async query() {
      return { rowCount: 1 };
    },
  };
  const repo = createUsersRepository(tx);

  const deleted = await repo.removeUser(userId);
  assert.equal(deleted, true);
});

test('users repository authenticate verifies password and returns user without hash', async () => {
  const realHash = createPasswordHash('secure-test-password-1234');
  const tx = {
    tenantId,
    async query(text, _values = []) {
      return {
        rows: [{
          id: userId,
          email: 'test@example.test',
          displayName: 'Test',
          passwordHash: realHash,
          status: 'active',
        }],
      };
    },
  };
  const repo = createUsersRepository(tx);

  const user = await repo.authenticate('test@example.test', 'secure-test-password-1234');
  assert.equal(user?.email, 'test@example.test');
  assert.equal(user?.passwordHash, undefined);
});

test('users repository authenticate rejects wrong password or disabled user', async () => {
  const tx = {
    tenantId,
    async query() {
      return {
        rows: [{
          id: userId,
          email: 'test@example.test',
          passwordHash: 'pbkdf2_sha256$310000$salt$hash',
          status: 'disabled',
        }],
      };
    },
  };
  const repo = createUsersRepository(tx);

  assert.equal(await repo.authenticate('test@example.test', 'wrong'), null);
});

test('users repository rejects invalid id for findById', async () => {
  const tx = {
    tenantId,
    query: async () => ({ rows: [] }),
  };
  const repo = createUsersRepository(tx);

  await assert.rejects(() => repo.findById('bad'), /valid user id is required/i);
});
