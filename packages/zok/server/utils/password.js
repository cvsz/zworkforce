import { pbkdf2Sync, randomBytes, timingSafeEqual } from 'node:crypto';

const PASSWORD_HASH_PREFIX = 'pbkdf2_sha256';
const PASSWORD_HASH_ITERATIONS = 310000;
const MAX_PASSWORD_HASH_ITERATIONS = 2_000_000;

export function createPasswordHash(password) {
  if (typeof password !== 'string' || password.length < 12) {
    throw new Error('Password must contain at least 12 characters');
  }

  const salt = randomBytes(16).toString('base64url');
  const derivedKey = pbkdf2Sync(
    password,
    salt,
    PASSWORD_HASH_ITERATIONS,
    32,
    'sha256',
  ).toString('base64url');

  return `${PASSWORD_HASH_PREFIX}$${PASSWORD_HASH_ITERATIONS}$${salt}$${derivedKey}`;
}

export function verifyPassword(password, storedHash) {
  if (typeof password !== 'string' || typeof storedHash !== 'string') return false;

  const [prefix, iterationsValue, salt, expectedValue] = storedHash.split('$');
  const iterations = Number(iterationsValue);
  if (
    prefix !== PASSWORD_HASH_PREFIX ||
    !Number.isSafeInteger(iterations) ||
    iterations < 100000 ||
    iterations > MAX_PASSWORD_HASH_ITERATIONS ||
    !salt ||
    !expectedValue
  ) {
    return false;
  }

  const expected = Buffer.from(expectedValue, 'base64url');
  if (expected.length !== 32) return false;
  const actual = pbkdf2Sync(password, salt, iterations, expected.length, 'sha256');
  return expected.length === actual.length && timingSafeEqual(expected, actual);
}
