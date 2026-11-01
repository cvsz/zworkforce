-- Disposable-only PG17 acceptance for a dedicated NO-SUPERUSER LOGIN.
-- Never execute on production or a persistent database.
\set ON_ERROR_STOP on
CREATE ROLE zeaz_financial_app_test LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS;
GRANT zeaz_financial_runtime TO zeaz_financial_app_test;
SET SESSION AUTHORIZATION zeaz_financial_app_test;
BEGIN;
SET LOCAL ROLE zeaz_financial_runtime;
DO $$
BEGIN
  IF current_user <> 'zeaz_financial_runtime' OR session_user <> 'zeaz_financial_app_test' THEN
    RAISE EXCEPTION 'Dedicated runtime role identity contract failed';
  END IF;
END $$;
SELECT set_config('zeaz.tenant_id', 'tenant-runtime-role', true);
INSERT INTO zeaz_financial.usage_events
  (tenant_id,usage_id,idempotency_key,subject_id,model,input_tokens,output_tokens,recorded_at)
VALUES ('tenant-runtime-role','runtime-usage','runtime-key','synthetic','test',1,2,now());
DO $$
BEGIN
  IF (SELECT count(*) FROM zeaz_financial.audit_events) <> 1 THEN
    RAISE EXCEPTION 'Dedicated login transactional audit contract failed';
  END IF;
END $$;
COMMIT;
DO $$
BEGIN
  IF current_user <> 'zeaz_financial_app_test' OR session_user <> 'zeaz_financial_app_test' THEN
    RAISE EXCEPTION 'SET LOCAL ROLE leaked across transaction boundary';
  END IF;
  IF coalesce(current_setting('zeaz.tenant_id', true), '') <> '' THEN
    RAISE EXCEPTION 'Tenant context leaked across transaction boundary';
  END IF;
END $$;
RESET SESSION AUTHORIZATION;
SELECT 'PG17_DEDICATED_LOGIN_ROLE_ACCEPTANCE_PASS' AS result;
