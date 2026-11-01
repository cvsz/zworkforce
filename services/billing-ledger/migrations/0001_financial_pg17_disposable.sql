-- Candidate-only PostgreSQL 17 financial schema. Never apply to a customer database.
-- Admission runner must verify a new disposable database before invoking this migration.
BEGIN;
CREATE SCHEMA zeaz_financial;
REVOKE ALL ON SCHEMA zeaz_financial FROM PUBLIC;
CREATE ROLE zeaz_financial_runtime NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS;
GRANT USAGE ON SCHEMA zeaz_financial TO zeaz_financial_runtime;

CREATE TABLE zeaz_financial.usage_events (
  tenant_id text NOT NULL CHECK (length(tenant_id) BETWEEN 1 AND 128),
  usage_id text NOT NULL CHECK (length(usage_id) BETWEEN 1 AND 128),
  idempotency_key text NOT NULL CHECK (length(idempotency_key) BETWEEN 1 AND 256),
  subject_id text NOT NULL,
  model text NOT NULL,
  input_tokens bigint NOT NULL CHECK (input_tokens BETWEEN 0 AND 9007199254740991),
  output_tokens bigint NOT NULL CHECK (output_tokens BETWEEN 0 AND 9007199254740991),
  recorded_at timestamptz NOT NULL,
  PRIMARY KEY (tenant_id, usage_id),
  UNIQUE (tenant_id, idempotency_key)
);
CREATE TABLE zeaz_financial.invoice_intents (
  tenant_id text NOT NULL CHECK (length(tenant_id) BETWEEN 1 AND 128),
  intent_id uuid NOT NULL,
  idempotency_key text NOT NULL CHECK (length(idempotency_key) BETWEEN 1 AND 256),
  amount_minor bigint NOT NULL CHECK (amount_minor BETWEEN 1 AND 9007199254740991),
  currency text NOT NULL CHECK (currency ~ '^[A-Z]{3}$'),
  status text NOT NULL CHECK (status = 'requires_payment_processor'),
  created_at timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (tenant_id, intent_id),
  UNIQUE (tenant_id, idempotency_key)
);
CREATE TABLE zeaz_financial.audit_events (
  audit_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  tenant_id text NOT NULL,
  entity_type text NOT NULL CHECK (entity_type IN ('usage', 'invoice_intent')),
  entity_id text NOT NULL,
  operation text NOT NULL CHECK (operation = 'created'),
  occurred_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (tenant_id, entity_type, entity_id, operation)
);
ALTER TABLE zeaz_financial.usage_events ENABLE ROW LEVEL SECURITY;
ALTER TABLE zeaz_financial.usage_events FORCE ROW LEVEL SECURITY;
ALTER TABLE zeaz_financial.invoice_intents ENABLE ROW LEVEL SECURITY;
ALTER TABLE zeaz_financial.invoice_intents FORCE ROW LEVEL SECURITY;
ALTER TABLE zeaz_financial.audit_events ENABLE ROW LEVEL SECURITY;

CREATE POLICY usage_read ON zeaz_financial.usage_events FOR SELECT TO zeaz_financial_runtime
  USING (tenant_id = current_setting('zeaz.tenant_id', true));
CREATE POLICY usage_insert ON zeaz_financial.usage_events FOR INSERT TO zeaz_financial_runtime
  WITH CHECK (tenant_id = current_setting('zeaz.tenant_id', true));
CREATE POLICY invoice_read ON zeaz_financial.invoice_intents FOR SELECT TO zeaz_financial_runtime
  USING (tenant_id = current_setting('zeaz.tenant_id', true));
CREATE POLICY invoice_insert ON zeaz_financial.invoice_intents FOR INSERT TO zeaz_financial_runtime
  WITH CHECK (tenant_id = current_setting('zeaz.tenant_id', true));
CREATE POLICY audit_read ON zeaz_financial.audit_events FOR SELECT TO zeaz_financial_runtime
  USING (tenant_id = current_setting('zeaz.tenant_id', true));

CREATE FUNCTION zeaz_financial.audit_insert() RETURNS trigger
LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, zeaz_financial AS $$
BEGIN
  IF TG_TABLE_NAME = 'usage_events' THEN
    INSERT INTO zeaz_financial.audit_events(tenant_id, entity_type, entity_id, operation)
      VALUES (NEW.tenant_id, 'usage', NEW.usage_id, 'created');
  ELSIF TG_TABLE_NAME = 'invoice_intents' THEN
    INSERT INTO zeaz_financial.audit_events(tenant_id, entity_type, entity_id, operation)
      VALUES (NEW.tenant_id, 'invoice_intent', NEW.intent_id::text, 'created');
  ELSE
    RAISE EXCEPTION 'Unsupported audit source';
  END IF;
  RETURN NEW;
END $$;
REVOKE ALL ON FUNCTION zeaz_financial.audit_insert() FROM PUBLIC;
CREATE TRIGGER usage_audit AFTER INSERT ON zeaz_financial.usage_events
  FOR EACH ROW EXECUTE FUNCTION zeaz_financial.audit_insert();
CREATE TRIGGER invoice_audit AFTER INSERT ON zeaz_financial.invoice_intents
  FOR EACH ROW EXECUTE FUNCTION zeaz_financial.audit_insert();

CREATE FUNCTION zeaz_financial.reject_audit_mutation() RETURNS trigger
LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, zeaz_financial AS $$
BEGIN
  RAISE EXCEPTION 'Audit records are append-only';
END $$;
REVOKE ALL ON FUNCTION zeaz_financial.reject_audit_mutation() FROM PUBLIC;
CREATE TRIGGER audit_immutable BEFORE UPDATE OR DELETE ON zeaz_financial.audit_events
  FOR EACH ROW EXECUTE FUNCTION zeaz_financial.reject_audit_mutation();

GRANT SELECT, INSERT ON zeaz_financial.usage_events TO zeaz_financial_runtime;
GRANT SELECT, INSERT ON zeaz_financial.invoice_intents TO zeaz_financial_runtime;
GRANT SELECT ON zeaz_financial.audit_events TO zeaz_financial_runtime;
COMMIT;
