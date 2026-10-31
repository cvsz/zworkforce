BEGIN;

CREATE TABLE IF NOT EXISTS billing_schema_migrations (
  version integer PRIMARY KEY,
  applied_at timestamptz NOT NULL DEFAULT clock_timestamp()
);

CREATE TABLE IF NOT EXISTS billing_usage_records (
  tenant_id text NOT NULL CHECK (length(btrim(tenant_id)) > 0),
  idempotency_key text NOT NULL CHECK (length(btrim(idempotency_key)) > 0),
  usage_id text NOT NULL CHECK (length(btrim(usage_id)) > 0),
  input_tokens bigint NOT NULL CHECK (input_tokens BETWEEN 0 AND 9007199254740991),
  output_tokens bigint NOT NULL CHECK (output_tokens BETWEEN 0 AND 9007199254740991),
  payload_hash char(64) NOT NULL CHECK (payload_hash ~ '^[0-9a-f]{64}$'),
  record jsonb NOT NULL,
  created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
  CONSTRAINT billing_usage_records_tenant_idempotency_pk
    PRIMARY KEY (tenant_id, idempotency_key)
);

CREATE INDEX IF NOT EXISTS billing_usage_records_tenant_created_idx
  ON billing_usage_records (tenant_id, created_at DESC);

CREATE TABLE IF NOT EXISTS billing_invoice_intents (
  tenant_id text NOT NULL CHECK (length(btrim(tenant_id)) > 0),
  idempotency_key text NOT NULL CHECK (length(btrim(idempotency_key)) > 0),
  intent_id text NOT NULL UNIQUE CHECK (length(btrim(intent_id)) > 0),
  payload_hash char(64) NOT NULL CHECK (payload_hash ~ '^[0-9a-f]{64}$'),
  currency char(3) NOT NULL CHECK (currency ~ '^[A-Z]{3}$'),
  amount_minor bigint NOT NULL CHECK (amount_minor BETWEEN 1 AND 9007199254740991),
  status text NOT NULL CHECK (status = 'requires_payment_processor'),
  intent jsonb NOT NULL,
  created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
  CONSTRAINT billing_invoice_intents_tenant_idempotency_pk
    PRIMARY KEY (tenant_id, idempotency_key)
);

CREATE INDEX IF NOT EXISTS billing_invoice_intents_tenant_created_idx
  ON billing_invoice_intents (tenant_id, created_at DESC);

INSERT INTO billing_schema_migrations (version)
VALUES (1)
ON CONFLICT (version) DO NOTHING;

COMMIT;
