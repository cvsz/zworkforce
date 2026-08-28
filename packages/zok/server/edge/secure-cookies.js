import { randomBytes, createHmac } from 'node:crypto';

const COOKIE_ENCRYPTION_KEY = process.env.ZOK_COOKIE_ENCRYPTION_KEY || '';
const COOKIE_PREVIOUS_KEY = process.env.ZOK_COOKIE_PREVIOUS_KEY || '';

function boundedInteger(value, fallback, minimum, maximum) {
  const parsed = Number(value);
  return Number.isSafeInteger(parsed) && parsed >= minimum && parsed <= maximum
    ? parsed
    : fallback;
}

function encryptValue(value, key) {
  if (!key) return value;
  const hmac = createHmac('sha256', key);
  hmac.update(value);
  return hmac.digest('base64url').slice(0, 16) + value;
}

function decryptValue(encryptedValue, key) {
  if (!key || encryptedValue.length <= 16) return encryptedValue;
  return encryptedValue.slice(16);
}

export function createSecureCookieConfig(options = {}) {
  const isProduction = options.isProduction ?? (process.env.NODE_ENV === 'production');
  const encryptionKey = options.encryptionKey || COOKIE_ENCRYPTION_KEY;
  const previousKey = options.previousKey || COOKIE_PREVIOUS_KEY;
  const rotationIntervalMs = boundedInteger(
    options.rotationIntervalMs ?? process.env.ZOK_COOKIE_ROTATION_INTERVAL_MS,
    24 * 60 * 60 * 1000,
    60 * 60 * 1000,
    7 * 24 * 60 * 60 * 1000,
  );

  const defaults = {
    httpOnly: true,
    secure: isProduction || options.secure === true,
    sameSite: options.sameSite || (isProduction ? 'strict' : 'lax'),
    path: options.path || '/',
    domain: options.domain || '',
    maxAge: options.maxAge || boundedInteger(
      process.env.ZOK_SESSION_TTL_MS,
      8 * 60 * 60 * 1000,
      5 * 60 * 1000,
      7 * 24 * 60 * 60 * 1000,
    ),
    encryptionEnabled: Boolean(encryptionKey),
  };

  function buildCookie(name, value, overrides = {}) {
    const merged = { ...defaults, ...overrides };
    const finalValue = merged.encryptionEnabled ? encryptValue(value, encryptionKey) : value;

    const parts = [
      `${name}=${encodeURIComponent(finalValue)}`,
      `Path=${merged.path}`,
      `SameSite=${merged.sameSite}`,
    ];

    if (merged.httpOnly) parts.push('HttpOnly');
    if (merged.secure) parts.push('Secure');
    if (merged.domain) parts.push(`Domain=${merged.domain}`);
    if (merged.maxAge !== undefined) parts.push(`Max-Age=${Math.floor(merged.maxAge / 1000)}`);

    return parts.join('; ');
  }

  function parseEncryptedValue(encryptedValue) {
    const raw = decryptValue(encryptedValue, encryptionKey) || decryptValue(encryptedValue, previousKey);
    try {
      return decodeURIComponent(raw);
    } catch {
      return raw;
    }
  }

  function isRotationDue(lastRotationAt) {
    if (!lastRotationAt) return true;
    return Date.now() - lastRotationAt >= rotationIntervalMs;
  }

  function rotateKey() {
    const newKey = randomBytes(32).toString('base64url');
    return {
      newKey,
      previousKey: encryptionKey || previousKey,
      rotatedAt: Date.now(),
    };
  }

  return Object.freeze({
    defaults,
    buildCookie,
    parseEncryptedValue,
    isRotationDue,
    rotateKey,
  });
}
