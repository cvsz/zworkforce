// Candidate-only identity boundary. Not wired to HTTP, payments, or production.
// An authenticated tenant requires a verified JWT AND an independent membership lookup.
import { createPublicKey, verify as verifySignature } from 'node:crypto';

export class FinancialIdentityError extends Error {
  constructor(message = 'Financial identity denied', status = 403) {
    super(message);
    this.name = 'FinancialIdentityError';
    this.status = status;
  }
}

const deny = () => new FinancialIdentityError();
const stringId = (value, max = 128) =>
  typeof value === 'string' && value.length > 0 && value.length <= max &&
  value === value.trim() && !/[\x00-\x1f\x7f]/.test(value);

function parsePart(part) {
  if (typeof part !== 'string' || !/^[A-Za-z0-9_-]+$/.test(part)) throw deny();
  const bytes = Buffer.from(part, 'base64url');
  if (bytes.toString('base64url') !== part) throw deny();
  return JSON.parse(bytes.toString('utf8'));
}

export function createFinancialTenantResolver({ issuer, audience, getJwks, lookupMembership, now = () => Date.now(), maxTokenSeconds = 3600 } = {}) {
  if (!stringId(issuer, 1024) || !issuer.startsWith('https://') ||
      !stringId(audience, 256) || typeof getJwks !== 'function' ||
      typeof lookupMembership !== 'function' || typeof now !== 'function' ||
      !Number.isSafeInteger(maxTokenSeconds) || maxTokenSeconds < 60 || maxTokenSeconds > 3600) {
    throw new FinancialIdentityError('Identity verifier configuration missing', 503);
  }

  return async function resolveTenant(principal) {
    // Only a raw bearer token is accepted; never trust pre-decoded claims.
    const token = principal?.token;
    if (typeof token !== 'string' || token.length > 16384 || token.length < 20) throw deny();
    const parts = token.split('.');
    if (parts.length !== 3) throw deny();
    let header, claims;
    try { header = parsePart(parts[0]); claims = parsePart(parts[1]); }
    catch { throw deny(); }
    if (!header || typeof header !== 'object' || Array.isArray(header) ||
        header.alg !== 'RS256' || header.typ !== 'JWT' || !stringId(header.kid, 128) ||
        Object.keys(header).some(k => !['alg', 'typ', 'kid'].includes(k)) ||
        !claims || typeof claims !== 'object' || Array.isArray(claims)) throw deny();

    const seconds = Math.floor(now() / 1000);
    if (!Number.isSafeInteger(seconds) || seconds < 0) throw new FinancialIdentityError('Clock unavailable', 503);
    const { iss, aud, sub, tenant_id: tenant, exp, iat, nbf, scope } = claims;
    if (iss !== issuer || !(aud === audience || (Array.isArray(aud) && aud.length > 0 && aud.every(value => stringId(value, 256)) && aud.includes(audience))) ||
        !stringId(sub) || !stringId(tenant) || !Number.isSafeInteger(exp) ||
        !Number.isSafeInteger(iat) || !Number.isSafeInteger(nbf) ||
        exp <= seconds || iat > seconds + 30 || nbf > seconds + 30 ||
        iat > exp || nbf > exp || exp - iat > maxTokenSeconds ||
        typeof scope !== 'string' || !scope.split(' ').includes('billing:write')) throw deny();

    // JWKs must come from a separately configured trusted issuer source. Never
    // follow header-supplied URLs, embedded JWKs, or algorithm negotiation.
    let jwks;
    try { jwks = await getJwks(); } catch { throw new FinancialIdentityError('Trusted key service unavailable', 503); }
    const keys = jwks?.keys;
    if (!Array.isArray(keys) || keys.length === 0 || keys.length > 100) throw deny();
    const matches = keys.filter(k => k && k.kid === header.kid);
    if (matches.length !== 1) throw deny();
    const key = matches[0];
    if (key.kty !== 'RSA' || key.alg !== 'RS256' || key.use !== 'sig' ||
        !stringId(key.n, 2048) || !stringId(key.e, 16) ||
        Object.keys(key).some(k => !['kid', 'kty', 'alg', 'use', 'n', 'e', 'key_ops'].includes(k)) ||
        (key.key_ops !== undefined && (!Array.isArray(key.key_ops) || key.key_ops.length !== 1 || key.key_ops[0] !== 'verify'))) throw deny();
    let verified = false;
    try {
      const publicKey = createPublicKey({ key, format: 'jwk' });
      if (publicKey.asymmetricKeyType !== 'rsa' || !Number.isSafeInteger(publicKey.asymmetricKeyDetails?.modulusLength) || publicKey.asymmetricKeyDetails.modulusLength < 2048) throw deny();
      const signature = Buffer.from(parts[2], 'base64url');
      if (!/^[A-Za-z0-9_-]+$/.test(parts[2]) || signature.toString('base64url') !== parts[2]) throw deny();
      verified = verifySignature('RSA-SHA256', Buffer.from(parts[0] + '.' + parts[1]), publicKey, signature);
    } catch { throw deny(); }
    if (!verified) throw deny();

    // The membership service must consult an authoritative server-side store.
    // Never accept roles, membership, or authorization from token claims.
    let membership;
    try { membership = await lookupMembership({ subject: sub, tenantId: tenant }); }
    catch { throw new FinancialIdentityError('Membership service unavailable', 503); }
    if (!membership || membership.active !== true || membership.role !== 'billing_writer') throw deny();
    return tenant;
  };
}
