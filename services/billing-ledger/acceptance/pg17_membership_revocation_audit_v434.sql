-- Disposable PostgreSQL 17 only. Runs AFTER v433 membership driver acceptance.
\set ON_ERROR_STOP on
CREATE ROLE zeaz_financial_membership_revoker_app_test
  LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS;
GRANT zeaz_financial_membership_revoker TO zeaz_financial_membership_revoker_app_test;

SET SESSION AUTHORIZATION zeaz_financial_membership_revoker_app_test;
DO $test$
DECLARE
  v_conflict boolean := false;
BEGIN
  IF has_table_privilege(current_user, 'zeaz_financial.tenant_memberships', 'SELECT')
     OR has_table_privilege(current_user, 'zeaz_financial.tenant_memberships', 'UPDATE')
     OR has_table_privilege(current_user, 'zeaz_financial.membership_revocation_audit', 'SELECT')
     OR has_table_privilege(current_user, 'zeaz_financial.membership_revocation_audit', 'INSERT')
     OR has_table_privilege(current_user, 'zeaz_financial.membership_revocation_audit', 'UPDATE')
     OR has_table_privilege(current_user, 'zeaz_financial.membership_revocation_audit', 'DELETE')
     OR has_table_privilege(current_user, 'zeaz_financial.usage_events', 'SELECT')
     OR pg_has_role(current_user, 'zeaz_financial_runtime', 'member') THEN
    RAISE EXCEPTION 'Revoker login violates least privilege';
  END IF;
  IF NOT has_function_privilege(current_user,
    'zeaz_financial.revoke_billing_membership(text,text,text,text)', 'EXECUTE') THEN
    RAISE EXCEPTION 'Revoker function grant missing';
  END IF;
  IF NOT zeaz_financial.revoke_billing_membership(
    'v434-revoke-subject-c-tenant-c', 'subject-c', 'tenant-c',
    'Operator-approved tenant offboarding') THEN
    RAISE EXCEPTION 'First revocation must change membership';
  END IF;
  IF zeaz_financial.revoke_billing_membership(
    'v434-revoke-subject-c-tenant-c', 'subject-c', 'tenant-c',
    'Operator-approved tenant offboarding') THEN
    RAISE EXCEPTION 'Idempotent replay must not create a new event';
  END IF;
  BEGIN
    PERFORM zeaz_financial.revoke_billing_membership(
      'v434-revoke-subject-c-tenant-c', 'subject-c', 'tenant-d',
      'Operator-approved tenant offboarding');
  EXCEPTION WHEN unique_violation THEN
    v_conflict := true;
  END;
  IF NOT v_conflict THEN
    RAISE EXCEPTION 'Conflicting request id must be rejected';
  END IF;
END
$test$;
RESET SESSION AUTHORIZATION;

DO $test$
BEGIN
  IF (SELECT count(*) FROM zeaz_financial.membership_revocation_audit
      WHERE request_id = 'v434-revoke-subject-c-tenant-c'
        AND subject_id = 'subject-c' AND tenant_id = 'tenant-c'
        AND actor_login::text = 'zeaz_financial_membership_revoker_app_test'
        AND reason = 'Operator-approved tenant offboarding'
        AND revoked_at IS NOT NULL) <> 1 THEN
    RAISE EXCEPTION 'Missing or duplicate revocation audit event';
  END IF;
  IF (SELECT count(*) FROM zeaz_financial.tenant_memberships
      WHERE subject_id = 'subject-c' AND tenant_id = 'tenant-c'
        AND active = false AND revoked_at IS NOT NULL) <> 1 THEN
    RAISE EXCEPTION 'Revocation not durable';
  END IF;
  IF (SELECT count(*) FROM zeaz_financial.tenant_memberships
      WHERE subject_id = 'subject-c' AND tenant_id = 'tenant-d'
        AND active = true AND revoked_at IS NULL) <> 1 THEN
    RAISE EXCEPTION 'Cross-tenant membership modified';
  END IF;
  IF has_function_privilege('zeaz_financial_membership_app_test',
    'zeaz_financial.revoke_billing_membership(text,text,text,text)', 'EXECUTE') THEN
    RAISE EXCEPTION 'Membership reader can revoke';
  END IF;
END
$test$;

-- The revocation and audit must both roll back if the caller aborts.
BEGIN;
SET SESSION AUTHORIZATION zeaz_financial_membership_revoker_app_test;
SELECT zeaz_financial.revoke_billing_membership(
  'v434-rollback-subject-c-tenant-d', 'subject-c', 'tenant-d',
  'Disposable rollback verification');
ROLLBACK;

DO $test$
BEGIN
  IF EXISTS (SELECT 1 FROM zeaz_financial.membership_revocation_audit
      WHERE request_id = 'v434-rollback-subject-c-tenant-d') THEN
    RAISE EXCEPTION 'Audit survived rolled-back transaction';
  END IF;
  IF (SELECT count(*) FROM zeaz_financial.tenant_memberships
      WHERE subject_id = 'subject-c' AND tenant_id = 'tenant-d'
        AND active = true AND revoked_at IS NULL) <> 1 THEN
    RAISE EXCEPTION 'Membership did not roll back';
  END IF;
END
$test$;
-- The existing membership reader must observe revocation immediately.
SET SESSION AUTHORIZATION zeaz_financial_membership_app_test;
DO $test$
BEGIN
  IF (SELECT count(*) FROM zeaz_financial.lookup_billing_membership(
      'subject-c', 'tenant-c') WHERE membership_active) <> 0 THEN
    RAISE EXCEPTION 'Membership reader observed stale authorization';
  END IF;
END
$test$;
RESET SESSION AUTHORIZATION;
SELECT 'PG17_AUDITED_MEMBERSHIP_REVOCATION_ACCEPTANCE_PASS' AS result;
