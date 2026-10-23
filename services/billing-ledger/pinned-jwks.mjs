// Candidate-only pinned JWKS transport for createFinancialTenantResolver.
// The URL is operator-owned; no JWT header or request field controls network access.
import { FinancialIdentityError } from './tenant-identity.mjs';

const unavailable = () => new FinancialIdentityError('Trusted key service unavailable', 503);

function pinnedUrl(issuer, jwksUrl) {
  if (typeof issuer !== 'string' || typeof jwksUrl !== 'string') throw unavailable();
  let identity, endpoint;
  try {
    identity = new URL(issuer);
    endpoint = new URL(jwksUrl);
  } catch { throw unavailable(); }
  if (identity.protocol !== 'https:' || endpoint.protocol !== 'https:' ||
      identity.origin !== endpoint.origin ||
      identity.username || identity.password || identity.search || identity.hash ||
      endpoint.username || endpoint.password || endpoint.search || endpoint.hash ||
      identity.href !== issuer || endpoint.href !== jwksUrl ||
      !endpoint.pathname.startsWith(identity.pathname.endsWith('/') ? identity.pathname : `${identity.pathname}/`)) {
    throw unavailable();
  }
  return endpoint.href;
}

async function readBoundedJson(response, maxBytes) {
  if (!response || response.status !== 200 ||
      !/^application\/(?:json|jwk-set\+json)(?:\s*;|\s*$)/i.test(response.headers?.get?.('content-type') || '') ||
      !response.body || typeof response.body.getReader !== 'function') throw unavailable();
  const reader = response.body.getReader();
  let length = 0;
  const chunks = [];
  try {
    while (true) {
      const { value, done } = await reader.read();
      if (done) break;
      if (!(value instanceof Uint8Array)) throw unavailable();
      length += value.byteLength;
      if (length > maxBytes) throw unavailable();
      chunks.push(value);
    }
  } finally {
    reader.releaseLock();
  }
  const decoded = new TextDecoder('utf-8', { fatal: true }).decode(Buffer.concat(chunks));
  const parsed = JSON.parse(decoded);
  if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed) ||
      !Array.isArray(parsed.keys) || parsed.keys.length < 1 || parsed.keys.length > 100 ||
      parsed.keys.some(k => !k || typeof k !== 'object' || Array.isArray(k) ||
        typeof k.kid !== 'string' || k.kid.length < 1 || k.kid.length > 128) ||
      new Set(parsed.keys.map(k => k.kid)).size !== parsed.keys.length) throw unavailable();
  return { keys: parsed.keys };
}

export function createPinnedJwksProvider({
  issuer, jwksUrl, fetchFn = globalThis.fetch, now = () => Date.now(),
  ttlMs = 30000, timeoutMs = 3000, maxBytes = 65536,
} = {}) {
  const url = pinnedUrl(issuer, jwksUrl);
  if (typeof fetchFn !== 'function' || typeof now !== 'function' ||
      !Number.isSafeInteger(ttlMs) || ttlMs < 1000 || ttlMs > 300000 ||
      !Number.isSafeInteger(timeoutMs) || timeoutMs < 500 || timeoutMs > 10000 ||
      !Number.isSafeInteger(maxBytes) || maxBytes < 4096 || maxBytes > 131072) throw unavailable();

  let cached;
  let cachedAt = 0;
  let expiresAt = 0;
  let inflight;
  return async function getJwks() {
    const current = now();
    if (!Number.isSafeInteger(current) || current < 0 || (cached && current < cachedAt)) throw unavailable();
    if (cached && current < expiresAt) return structuredClone(cached);
    if (!inflight) {
      inflight = (async () => {
        try {
          const response = await fetchFn(url, {
            method: 'GET', redirect: 'error', credentials: 'omit',
            headers: { accept: 'application/json' },
            signal: AbortSignal.timeout(timeoutMs),
          });
          const next = await readBoundedJson(response, maxBytes);
          const receivedAt = now();
          if (!Number.isSafeInteger(receivedAt) || receivedAt < current) throw unavailable();
          cached = next;
          cachedAt = receivedAt;
          expiresAt = receivedAt + ttlMs;
          return structuredClone(next);
        } catch {
          // Never use an expired JWKS as an availability fallback.
          cached = undefined;
          throw unavailable();
        }
      })().finally(() => { inflight = undefined; });
    }
    return structuredClone(await inflight);
  };
}
