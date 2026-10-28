import { createHash } from "node:crypto";

function safeStoreError(message, status) {
  const error = new Error(message);
  error.status = status;
  error.publicMessage = message;
  return error;
}

function storageUnavailable() {
  return safeStoreError("Persistent billing storage is unavailable", 503);
}

function idempotencyConflict() {
  return safeStoreError("Idempotency key conflicts with an existing request", 409);
}

function stableFingerprint(value, excludedKeys = []) {
  const stable = Object.fromEntries(
    Object.entries(value)
      .filter(([key]) => !excludedKeys.includes(key))
      .sort(([left], [right]) => left.localeCompare(right)),
  );
  return createHash("sha256").update(JSON.stringify(stable)).digest("hex");
}

/**
 * PostgreSQL-backed store. The caller owns the pool lifecycle and must apply
 * migrations/001_durable_billing_ledger.sql before enabling mutation routes.
 */
export class PostgresLedgerStore {
  durable = true;

  constructor({ pool }) {
    if (!pool || typeof pool.query !== "function") {
      throw new TypeError("PostgresLedgerStore requires a PostgreSQL pool");
    }
    this.pool = pool;
  }

  async assertReady() {
    // Probe the database on every readiness request; a cached success would
    // falsely keep a failed database marked ready after a connection loss.
    try {
      const { rows } = await this.pool.query(
        `SELECT version,
                to_regclass('billing_usage_records') IS NOT NULL AS usage_table_present,
                to_regclass('billing_invoice_intents') IS NOT NULL AS invoice_table_present,
                EXISTS (
                  SELECT 1
                    FROM pg_constraint
                   WHERE conname = 'billing_usage_records_tenant_idempotency_pk'
                     AND conrelid = to_regclass('billing_usage_records')
                     AND contype = 'p'
                ) AS usage_idempotency_pk_present,
                EXISTS (
                  SELECT 1
                    FROM pg_constraint
                   WHERE conname = 'billing_invoice_intents_tenant_idempotency_pk'
                     AND conrelid = to_regclass('billing_invoice_intents')
                     AND contype = 'p'
                ) AS invoice_idempotency_pk_present
           FROM billing_schema_migrations
          WHERE version = $1`,
        [1],
      );
      const schema = rows?.[0];
      if (
        !schema ||
        schema.usage_table_present !== true ||
        schema.invoice_table_present !== true ||
        schema.usage_idempotency_pk_present !== true ||
        schema.invoice_idempotency_pk_present !== true
      ) {
        throw storageUnavailable();
      }
      return true;
    } catch {
      throw storageUnavailable();
    }
  }

  async #query(sql, params) {
    await this.assertReady();
    try {
      return await this.pool.query(sql, params);
    } catch {
      throw storageUnavailable();
    }
  }

  async recordUsage(record) {
    const fingerprint = stableFingerprint(record, ["recorded_at"]);
    const inserted = await this.#query(
      `INSERT INTO billing_usage_records
         (tenant_id, idempotency_key, usage_id, input_tokens, output_tokens, payload_hash, record)
       VALUES ($1, $2, $3, $4, $5, $6, $7::jsonb)
       ON CONFLICT (tenant_id, idempotency_key) DO NOTHING
       RETURNING record`,
      [
        record.tenant_id,
        record.idempotency_key,
        record.usage_id,
        record.input_tokens,
        record.output_tokens,
        fingerprint,
        JSON.stringify(record),
      ],
    );

    if (inserted.rows[0]) {
      return { duplicate: false, record: inserted.rows[0].record };
    }

    const existing = await this.#query(
      `SELECT payload_hash, record
         FROM billing_usage_records
        WHERE tenant_id = $1 AND idempotency_key = $2`,
      [record.tenant_id, record.idempotency_key],
    );
    const row = existing.rows[0];
    if (!row) throw storageUnavailable();
    if (row.payload_hash !== fingerprint) throw idempotencyConflict();
    return { duplicate: true, record: row.record };
  }

  async createInvoiceIntent(intent) {
    const fingerprint = stableFingerprint(intent, ["intent_id", "created_at"]);
    const inserted = await this.#query(
      `INSERT INTO billing_invoice_intents
         (tenant_id, idempotency_key, intent_id, payload_hash, currency, amount_minor, status, intent)
       VALUES ($1, $2, $3, $4, $5, $6, $7, $8::jsonb)
       ON CONFLICT (tenant_id, idempotency_key) DO NOTHING
       RETURNING intent`,
      [
        intent.tenant_id,
        intent.idempotency_key,
        intent.intent_id,
        fingerprint,
        intent.currency,
        intent.amount_minor,
        intent.status,
        JSON.stringify(intent),
      ],
    );

    if (inserted.rows[0]) return inserted.rows[0].intent;

    const existing = await this.#query(
      `SELECT payload_hash, intent
         FROM billing_invoice_intents
        WHERE tenant_id = $1 AND idempotency_key = $2`,
      [intent.tenant_id, intent.idempotency_key],
    );
    const row = existing.rows[0];
    if (!row) throw storageUnavailable();
    if (row.payload_hash !== fingerprint) throw idempotencyConflict();
    return row.intent;
  }

  async setCredits() {
    // The existing setter has no operation idempotency key or append-only audit
    // record. Keep it unavailable until that API contract is replaced safely.
    throw safeStoreError(
      "Credit mutations are disabled pending an append-only audited adjustment contract",
      503,
    );
  }

  async close() {
    await this.pool.end();
  }
}
