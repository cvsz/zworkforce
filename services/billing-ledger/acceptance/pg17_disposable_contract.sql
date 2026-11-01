-- Synthetic-only SQL acceptance. Execute after migration in a new disposable PG17 database.
\set ON_ERROR_STOP on
SET ROLE zeaz_financial_runtime;
DO $$
DECLARE denied boolean := false;
BEGIN
  BEGIN
    INSERT INTO zeaz_financial.usage_events VALUES
      ('tenant-a','no-context','no-context','subject','model',1,1,now());
  EXCEPTION WHEN insufficient_privilege THEN denied := true;
  END;
  IF NOT denied THEN RAISE EXCEPTION 'missing tenant context accepted'; END IF;
END $$;

BEGIN;
SET LOCAL zeaz.tenant_id = 'tenant-a';
INSERT INTO zeaz_financial.usage_events VALUES
  ('tenant-a','usage-1','request-1','subject','model',5,7,now());
INSERT INTO zeaz_financial.invoice_intents
  (tenant_id,intent_id,idempotency_key,amount_minor,currency,status)
VALUES ('tenant-a','00000000-0000-4000-8000-000000000001','invoice-1',1200,'USD','requires_payment_processor');
DO $$
DECLARE denied boolean;
BEGIN
  denied := false;
  BEGIN
    INSERT INTO zeaz_financial.usage_events VALUES
      ('tenant-a','usage-1','new-key','subject','model',5,7,now());
  EXCEPTION WHEN unique_violation THEN denied := true;
  END;
  IF NOT denied THEN RAISE EXCEPTION 'duplicate usage identity accepted'; END IF;
  denied := false;
  BEGIN
    INSERT INTO zeaz_financial.usage_events VALUES
      ('tenant-a','usage-2','request-1','subject','model',5,7,now());
  EXCEPTION WHEN unique_violation THEN denied := true;
  END;
  IF NOT denied THEN RAISE EXCEPTION 'duplicate idempotency key accepted'; END IF;
  denied := false;
  BEGIN
    INSERT INTO zeaz_financial.usage_events VALUES
      ('tenant-a','unsafe-count','unsafe-count','subject','model',9007199254740992,0,now());
  EXCEPTION WHEN check_violation THEN denied := true;
  END;
  IF NOT denied THEN RAISE EXCEPTION 'unsafe token count accepted'; END IF;
  denied := false;
  BEGIN
    INSERT INTO zeaz_financial.invoice_intents
      (tenant_id,intent_id,idempotency_key,amount_minor,currency,status)
    VALUES ('tenant-a','00000000-0000-4000-8000-000000000002','invoice-2',100,'USD','paid');
  EXCEPTION WHEN check_violation THEN denied := true;
  END;
  IF NOT denied THEN RAISE EXCEPTION 'forged paid invoice accepted'; END IF;
  denied := false;
  BEGIN
    INSERT INTO zeaz_financial.invoice_intents
      (tenant_id,intent_id,idempotency_key,amount_minor,currency,status)
    VALUES ('tenant-a','00000000-0000-4000-8000-000000000003','invoice-3',9007199254740992,'USD','requires_payment_processor');
  EXCEPTION WHEN check_violation THEN denied := true;
  END;
  IF NOT denied THEN RAISE EXCEPTION 'unsafe invoice amount accepted'; END IF;
  IF (SELECT count(*) FROM zeaz_financial.audit_events) <> 2 THEN
    RAISE EXCEPTION 'transactional audit count mismatch';
  END IF;
END $$;
COMMIT;

BEGIN;
SET LOCAL zeaz.tenant_id = 'tenant-b';
DO $$
DECLARE denied boolean := false;
BEGIN
  IF (SELECT count(*) FROM zeaz_financial.usage_events) <> 0
    OR (SELECT count(*) FROM zeaz_financial.invoice_intents) <> 0
    OR (SELECT count(*) FROM zeaz_financial.audit_events) <> 0 THEN
    RAISE EXCEPTION 'cross-tenant read accepted';
  END IF;
  BEGIN
    INSERT INTO zeaz_financial.usage_events VALUES
      ('tenant-a','cross-tenant','cross-tenant','subject','model',1,1,now());
  EXCEPTION WHEN insufficient_privilege THEN denied := true;
  END;
  IF NOT denied THEN RAISE EXCEPTION 'cross-tenant write accepted'; END IF;
END $$;
INSERT INTO zeaz_financial.usage_events VALUES
  ('tenant-b','usage-1','request-1','subject','model',1,1,now());
COMMIT;

BEGIN;
SET LOCAL zeaz.tenant_id = 'tenant-a';
INSERT INTO zeaz_financial.usage_events VALUES
  ('tenant-a','rolled-back','rolled-back','subject','model',1,1,now());
ROLLBACK;
BEGIN;
SET LOCAL zeaz.tenant_id = 'tenant-a';
DO $$
BEGIN
  IF (SELECT count(*) FROM zeaz_financial.usage_events) <> 1
    OR (SELECT count(*) FROM zeaz_financial.audit_events) <> 2 THEN
    RAISE EXCEPTION 'rollback persisted financial data or audit';
  END IF;
END $$;
COMMIT;
RESET ROLE;

DO $$
DECLARE denied boolean := false;
BEGIN
  BEGIN
    UPDATE zeaz_financial.audit_events SET entity_type='usage' WHERE audit_id=1;
  EXCEPTION WHEN raise_exception THEN denied := true;
  END;
  IF NOT denied THEN RAISE EXCEPTION 'audit update accepted'; END IF;
END $$;
SELECT 'PG17_FINANCIAL_SQL_ACCEPTANCE_PASS' AS result;
