// Candidate-only PostgreSQL membership lookup. Never trust JWT role claims.
// Use a dedicated non-superuser login with EXECUTE-only membership lookup rights.
import { FinancialIdentityError } from './tenant-identity.mjs';

const denied = () => new FinancialIdentityError();
const unavailable = () => new FinancialIdentityError('Membership service unavailable', 503);
const validId = value => typeof value === 'string' && value.length > 0 &&
  value.length <= 128 && value === value.trim() && !/[\x00-\x1f\x7f]/.test(value);
const loginPattern = /^[a-z][a-z0-9_]{0,62}$/;

export function createPgMembershipLookup({ pool, expectedLoginRole } = {}) {
  if (!pool || typeof pool.connect !== 'function' ||
      typeof expectedLoginRole !== 'string' || !loginPattern.test(expectedLoginRole) ||
      ['postgres', 'zeaz_financial_runtime', 'zeaz_financial_membership_reader'].includes(expectedLoginRole)) {
    throw unavailable();
  }

  // No authorization cache: every verified JWT must be checked against current
  // authoritative membership state, including revocation, before ledger access.
  return async function lookupMembership({ subject, tenantId } = {}) {
    if (!validId(subject) || !validId(tenantId)) throw denied();
    let client;
    let discard = false;
    try {
      client = await pool.connect();
      const identity = await client.query(`
        SELECT session_user AS login_role, current_user AS active_role,
               rolsuper, rolbypassrls, rolcreaterole, rolcreatedb, rolreplication,
               pg_has_role(session_user, 'zeaz_financial_runtime', 'member') AS financial_runtime_member
        FROM pg_roles WHERE rolname = session_user`);
      const role = identity.rows?.[0];
      if (identity.rows?.length !== 1 || role.login_role !== expectedLoginRole ||
          role.active_role !== expectedLoginRole || role.rolsuper !== false ||
          role.rolbypassrls !== false || role.rolcreaterole !== false ||
          role.rolcreatedb !== false || role.rolreplication !== false ||
          role.financial_runtime_member !== false) throw unavailable();

      const result = await client.query(
        'SELECT membership_active, membership_role FROM zeaz_financial.lookup_billing_membership($1, $2)',
        [subject, tenantId],
      );
      if (!Array.isArray(result.rows) || result.rows.length > 1) throw unavailable();
      if (result.rows.length === 0) return { active: false, role: null };
      const row = result.rows[0];
      if (typeof row.membership_active !== 'boolean' ||
          !['billing_writer', 'viewer'].includes(row.membership_role)) throw unavailable();
      return { active: row.membership_active, role: row.membership_role };
    } catch {
      discard = true;
      throw unavailable();
    } finally {
      if (client) client.release(discard);
    }
  };
}
