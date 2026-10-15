-- Candidate migration. Apply only to an isolated staging database after review.
-- This migration creates new tables and never changes or deletes existing billing data.
BEGIN;
CREATE SCHEMA IF NOT EXISTS zeaz_billing;
CREATE TABLE IF NOT EXISTS zeaz_billing.usage_records (
    tenant_id text NOT NULL,
    idempotency_key text NOT NULL,
    fingerprint char(64) NOT NULL,
    payload jsonb NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (tenant_id, idempotency_key),
    CONSTRAINT usage_tenant_not_blank CHECK (length(btrim(tenant_id)) BETWEEN 1 AND 128),
    CONSTRAINT usage_key_not_blank CHECK (length(btrim(idempotency_key)) BETWEEN 1 AND 256),
    CONSTRAINT usage_payload_object CHECK (jsonb_typeof(payload) = 'object')
);
CREATE TABLE IF NOT EXISTS zeaz_billing.invoice_intents (
    tenant_id text NOT NULL,
    idempotency_key text NOT NULL,
    fingerprint char(64) NOT NULL,
    payload jsonb NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (tenant_id, idempotency_key),
    CONSTRAINT invoice_tenant_not_blank CHECK (length(btrim(tenant_id)) BETWEEN 1 AND 128),
    CONSTRAINT invoice_key_not_blank CHECK (length(btrim(idempotency_key)) BETWEEN 1 AND 256),
    CONSTRAINT invoice_payload_object CHECK (jsonb_typeof(payload) = 'object')
);
ALTER TABLE zeaz_billing.usage_records ENABLE ROW LEVEL SECURITY;
ALTER TABLE zeaz_billing.usage_records FORCE ROW LEVEL SECURITY;
ALTER TABLE zeaz_billing.invoice_intents ENABLE ROW LEVEL SECURITY;
ALTER TABLE zeaz_billing.invoice_intents FORCE ROW LEVEL SECURITY;
DO $migration$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE schemaname='zeaz_billing' AND tablename='usage_records' AND policyname='usage_tenant_scope') THEN
        CREATE POLICY usage_tenant_scope ON zeaz_billing.usage_records
            USING (tenant_id = current_setting('zeaz.tenant_id', true))
            WITH CHECK (tenant_id = current_setting('zeaz.tenant_id', true));
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE schemaname='zeaz_billing' AND tablename='invoice_intents' AND policyname='invoice_tenant_scope') THEN
        CREATE POLICY invoice_tenant_scope ON zeaz_billing.invoice_intents
            USING (tenant_id = current_setting('zeaz.tenant_id', true))
            WITH CHECK (tenant_id = current_setting('zeaz.tenant_id', true));
    END IF;
END
$migration$;
COMMIT;
