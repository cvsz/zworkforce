// Candidate-only PostgreSQL financial store. Not wired to HTTP or production.
// The injected resolveTenant MUST validate a server-authenticated principal;
// neither a request body nor a caller-supplied tenant string is an authority.
import { isDeepStrictEqual } from 'node:util';

export class PgFinancialStoreError extends Error {
  constructor(message, status = 400) {
    super(message);
    this.name = 'PgFinancialStoreError';
    this.status = status;
  }
}

const usageFields = new Set(['event_type', 'event_version', 'tenant_id', 'usage_id', 'idempotency_key', 'subject_id', 'model', 'input_tokens', 'output_tokens', 'recorded_at']);
const invoiceFields = new Set(['tenant_id', 'intent_id', 'idempotency_key', 'amount_minor', 'currency', 'status', 'created_at']);
const runtimeRole = 'zeaz_financial_runtime';

function boundedString(value, name, max = 256) {
  if (typeof value !== 'string' || !value.trim() || value !== value.trim() || value.length > max) {
    throw new PgFinancialStoreError(`Invalid ${name}`);
  }
  return value;
}
function checkFields(record, fields) {
  if (!record || typeof record !== 'object' || Array.isArray(record) || Object.keys(record).some(key => !fields.has(key))) {
    throw new PgFinancialStoreError('Unsupported financial payload fields');
  }
}
function safeCount(value, name, min = 0) {
  if (!Number.isSafeInteger(value) || value < min) throw new PgFinancialStoreError(`Invalid ${name}`);
}
function dateString(value, name) {
  // Financial timestamps must have an explicit timezone and a valid calendar date.
  // Restrict fractions to milliseconds to avoid silently discarding precision.
  const match = typeof value === 'string' &&
    /^(\d{4})-(\d{2})-(\d{2})T(?:[01]\d|2[0-3]):[0-5]\d:[0-5]\d(?:\.\d{1,3})?(Z|([+-])(0\d|1[0-4]):([0-5]\d))$/.exec(value);
  if (!match) throw new PgFinancialStoreError(`Invalid ${name}`);
  const year = Number(match[1]);
  const month = Number(match[2]);
  const day = Number(match[3]);
  const leap = year % 4 === 0 && (year % 100 !== 0 || year % 400 === 0);
  const daysInMonth = [31, leap ? 29 : 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31];
  if (month < 1 || month > 12 || day < 1 || day > daysInMonth[month - 1] ||
      (match[5] && Number(match[6]) === 14 && Number(match[7]) !== 0) ||
      (match[5] === '-' && Number(match[6]) === 0 && Number(match[7]) === 0)) {
    throw new PgFinancialStoreError(`Invalid ${name}`);
  }
  const epoch = Date.parse(value);
  if (!Number.isFinite(epoch)) throw new PgFinancialStoreError(`Invalid ${name}`);
  return new Date(epoch).toISOString();
}
function asDate(value) { return value instanceof Date ? value.toISOString() : new Date(value).toISOString(); }
function usageRow(row) {
  return {
    event_type: 'ai.usage.recorded.v1', event_version: 'v1', tenant_id: row.tenant_id,
    usage_id: row.usage_id, idempotency_key: row.idempotency_key,
    subject_id: row.subject_id, model: row.model,
    input_tokens: Number(row.input_tokens), output_tokens: Number(row.output_tokens),
    recorded_at: asDate(row.recorded_at),
  };
}
function invoiceRow(row) {
  return {
    tenant_id: row.tenant_id, intent_id: row.intent_id, idempotency_key: row.idempotency_key,
    amount_minor: Number(row.amount_minor), currency: row.currency,
    status: row.status, created_at: asDate(row.created_at),
  };
}

export class PgFinancialStore {
  constructor({ pool, resolveTenant, expectedLoginRole } = {}) {
    if (!pool || typeof pool.connect !== 'function' || typeof resolveTenant !== 'function' ||
        typeof expectedLoginRole !== 'string' || !/^[a-z][a-z0-9_]{0,62}$/.test(expectedLoginRole) ||
        expectedLoginRole === runtimeRole) {
      throw new PgFinancialStoreError('Pool and trusted tenant resolver are required', 503);
    }
    this.pool = pool;
    this.resolveTenant = resolveTenant;
    this.expectedLoginRole = expectedLoginRole;
  }

  async withTenant(principal, claimedTenant, action) {
    // The resolver must perform independent AuthN/AuthZ; a tenant claim is not proof.
    const tenant = boundedString(await this.resolveTenant(principal), 'verified tenant', 128);
    if (tenant !== claimedTenant) throw new PgFinancialStoreError('Tenant authorization mismatch', 403);
    const client = await this.pool.connect();
    let started = false;
    let discardConnection = false;
    let commitAttempted = false;
    try {
      await client.query('BEGIN');
      started = true;
      // The migration creates a NOLOGIN runtime role. Operators provision a
      // separate non-privileged LOGIN that is a member of that role.
      const identity = await client.query(`
        SELECT session_user AS login_role, rolsuper, rolbypassrls,
               rolcreaterole, rolcreatedb, rolreplication
        FROM pg_roles WHERE rolname = session_user`);
      const login = identity.rows?.[0];
      if (identity.rows?.length !== 1 || login.login_role !== this.expectedLoginRole ||
          login.rolsuper !== false || login.rolbypassrls !== false ||
          login.rolcreaterole !== false || login.rolcreatedb !== false ||
          login.rolreplication !== false) {
        throw new PgFinancialStoreError('Dedicated least-privilege PostgreSQL login required', 503);
      }
      await client.query('SET LOCAL ROLE zeaz_financial_runtime');
      const role = await client.query('SELECT current_user AS current_role');
      if (role.rows?.length !== 1 || role.rows[0].current_role !== runtimeRole) {
        throw new PgFinancialStoreError('PostgreSQL runtime role activation failed', 503);
      }
      await client.query("SELECT set_config('zeaz.tenant_id', $1, true)", [tenant]);
      const result = await action(client, tenant);
      commitAttempted = true;
      await client.query('COMMIT');
      return result;
    } catch (error) {
      // A failed BEGIN/COMMIT or ROLLBACK leaves the session state uncertain.
      if (!started || commitAttempted) discardConnection = true;
      if (started) {
        try { await client.query('ROLLBACK'); } catch { discardConnection = true; }
      }
      if (error?.code === '23505') throw new PgFinancialStoreError('Conflicting financial identity', 409);
      throw error;
    } finally {
      client.release(discardConnection ? new Error('Financial transaction session state uncertain') : undefined);
    }
  }

  async recordUsage(principal, record) {
    checkFields(record, usageFields);
    const tenant = boundedString(record.tenant_id, 'tenant_id', 128);
    boundedString(record.usage_id, 'usage_id', 128);
    boundedString(record.idempotency_key, 'idempotency_key');
    boundedString(record.subject_id, 'subject_id');
    boundedString(record.model, 'model');
    safeCount(record.input_tokens, 'input_tokens');
    safeCount(record.output_tokens, 'output_tokens');
    const timestamp = dateString(record.recorded_at, 'recorded_at');
    if (record.event_type !== 'ai.usage.recorded.v1' || record.event_version !== 'v1') {
      throw new PgFinancialStoreError('Unsupported usage event version');
    }
    return this.withTenant(principal, tenant, async client => {
      const inserted = await client.query(`
        INSERT INTO zeaz_financial.usage_events
          (tenant_id, usage_id, idempotency_key, subject_id, model, input_tokens, output_tokens, recorded_at)
        VALUES ($1,$2,$3,$4,$5,$6,$7,$8)
        ON CONFLICT DO NOTHING RETURNING *`,
      [tenant, record.usage_id, record.idempotency_key, record.subject_id, record.model,
        record.input_tokens, record.output_tokens, timestamp]);
      if (inserted.rows.length === 1) return { duplicate: false, record: usageRow(inserted.rows[0]) };
      const existing = await client.query(`
        SELECT * FROM zeaz_financial.usage_events WHERE tenant_id=$1 AND idempotency_key=$2`,
      [tenant, record.idempotency_key]);
      if (existing.rows.length !== 1) throw new PgFinancialStoreError('Conflicting usage identity', 409);
      const previous = usageRow(existing.rows[0]);
      const { recorded_at: _previousTimestamp, ...previousSemantics } = previous;
      const { recorded_at: _incomingTimestamp, ...incomingSemantics } = record;
      if (!isDeepStrictEqual(previousSemantics, incomingSemantics)) {
        throw new PgFinancialStoreError('Conflicting usage idempotency replay', 409);
      }
      return { duplicate: true, record: previous };
    });
  }

  async createInvoiceIntent(principal, intent) {
    checkFields(intent, invoiceFields);
    const tenant = boundedString(intent.tenant_id, 'tenant_id', 128);
    boundedString(intent.idempotency_key, 'idempotency_key');
    if (typeof intent.intent_id !== 'string' || !/^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i.test(intent.intent_id)) {
      throw new PgFinancialStoreError('Invalid invoice UUID');
    }
    safeCount(intent.amount_minor, 'amount_minor', 1);
    if (typeof intent.currency !== 'string' || !/^[A-Z]{3}$/.test(intent.currency)) throw new PgFinancialStoreError('Invalid currency');
    if (intent.status !== 'requires_payment_processor') throw new PgFinancialStoreError('Invoice settlement not authorized', 503);
    const timestamp = dateString(intent.created_at, 'created_at');
    return this.withTenant(principal, tenant, async client => {
      const inserted = await client.query(`
        INSERT INTO zeaz_financial.invoice_intents
          (tenant_id,intent_id,idempotency_key,amount_minor,currency,status,created_at)
        VALUES ($1,$2,$3,$4,$5,$6,$7)
        ON CONFLICT DO NOTHING RETURNING *`,
      [tenant, intent.intent_id, intent.idempotency_key, intent.amount_minor, intent.currency, intent.status, timestamp]);
      if (inserted.rows.length === 1) return invoiceRow(inserted.rows[0]);
      const existing = await client.query(`
        SELECT * FROM zeaz_financial.invoice_intents WHERE tenant_id=$1 AND idempotency_key=$2`,
      [tenant, intent.idempotency_key]);
      if (existing.rows.length !== 1) throw new PgFinancialStoreError('Conflicting invoice identity', 409);
      const previous = invoiceRow(existing.rows[0]);
      const { intent_id: _oldId, created_at: _oldCreated, ...previousSemantics } = previous;
      const { intent_id: _newId, created_at: _newCreated, ...incomingSemantics } = intent;
      if (!isDeepStrictEqual(previousSemantics, incomingSemantics)) {
        throw new PgFinancialStoreError('Conflicting invoice idempotency replay', 409);
      }
      return previous;
    });
  }
}
