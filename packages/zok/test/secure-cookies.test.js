import test from 'node:test';
import assert from 'node:assert/strict';
import { createSecureCookieConfig } from '../server/edge/secure-cookies.js';

test('secure cookie config defaults to development mode', () => {
  process.env.NODE_ENV = 'test';
  const config = createSecureCookieConfig();
  assert.equal(config.defaults.secure, false);
  assert.equal(config.defaults.sameSite, 'lax');
  assert.equal(config.defaults.httpOnly, true);
  assert.equal(config.defaults.path, '/');
});

test('secure cookie config uses production defaults when isProduction is true', () => {
  const config = createSecureCookieConfig({ isProduction: true });
  assert.equal(config.defaults.secure, true);
  assert.equal(config.defaults.sameSite, 'strict');
  assert.equal(config.defaults.httpOnly, true);
});

test('secure cookie config builds a valid cookie string', () => {
  const config = createSecureCookieConfig({ isProduction: true });
  const cookie = config.buildCookie('zok_session', 'test-token', { maxAge: 3600 * 1000 });
  assert.ok(cookie.includes('zok_session=test-token'));
  assert.ok(cookie.includes('HttpOnly'));
  assert.ok(cookie.includes('Secure'));
  assert.ok(cookie.includes('SameSite=strict'));
  assert.ok(cookie.includes('Path=/'));
  assert.ok(cookie.includes('Max-Age=3600'));
});

test('secure cookie config includes domain when provided', () => {
  const config = createSecureCookieConfig({ isProduction: true, domain: 'example.com' });
  const cookie = config.buildCookie('test', 'value');
  assert.ok(cookie.includes('Domain=example.com'));
});

test('secure cookie config encrypts values when encryption key is provided', () => {
  const config = createSecureCookieConfig({
    isProduction: true,
    encryptionKey: 'test-secret-key-1234567890',
  });
  const cookie = config.buildCookie('secure', 'plain-value');
  assert.ok(cookie.includes('Secure'));
  const match = cookie.match(/secure=([^;]+)/);
  assert.ok(match, 'expected encrypted cookie value');
  const encrypted = decodeURIComponent(match[1]);
  assert.ok(encrypted.startsWith('T-') || encrypted.startsWith('plain-value'), 'encrypted value should contain transformed data');
  assert.ok(encrypted !== 'plain-value' || encrypted.length > 'plain-value'.length, 'encrypted value should differ from plain value');
});

test('secure cookie config parses encrypted values back to original', () => {
  const encryptionKey = 'test-secret-key-1234567890';
  const config = createSecureCookieConfig({
    isProduction: true,
    encryptionKey,
  });
  const cookie = config.buildCookie('secure', 'plain-value');
  const match = cookie.match(/secure=([^;]+)/);
  assert.ok(match, 'expected encrypted cookie value');
  const decrypted = config.parseEncryptedValue(match[1]);
  assert.equal(decrypted, 'plain-value');
});

test('secure cookie config rotation generates a new key', () => {
  const config = createSecureCookieConfig({ isProduction: true });
  const rotation = config.rotateKey();
  assert.ok(typeof rotation.newKey === 'string');
  assert.ok(rotation.newKey.length > 0);
  assert.ok(typeof rotation.rotatedAt === 'number');
});

test('secure cookie config detects when rotation is due', () => {
  const config = createSecureCookieConfig({ isProduction: true });
  assert.ok(config.isRotationDue(null));
  assert.ok(config.isRotationDue(Date.now() - 25 * 60 * 60 * 1000));
  assert.ok(!config.isRotationDue(Date.now()));
});

test('secure cookie config respects overrides', () => {
  const config = createSecureCookieConfig({ isProduction: true });
  const cookie = config.buildCookie('test', 'value', {
    secure: false,
    sameSite: 'none',
    httpOnly: false,
    domain: 'custom.example.com',
  });
  assert.ok(cookie.includes('SameSite=none'));
  assert.ok(!cookie.includes('HttpOnly'));
  assert.ok(!cookie.includes('Secure'));
  assert.ok(cookie.includes('Domain=custom.example.com'));
});
