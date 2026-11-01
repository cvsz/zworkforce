-- Synthetic data only. Run after migration 0002 on disposable PostgreSQL 17.
\set ON_ERROR_STOP on
CREATE ROLE zeaz_financial_membership_app_test LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS;
GRANT zeaz_financial_membership_reader TO zeaz_financial_membership_app_test;
INSERT INTO zeaz_financial.tenant_memberships(subject_id, tenant_id, membership_role, active)
VALUES ('subject-a', 'tenant-a', 'billing_writer', true),
       ('subject-a', 'tenant-b', 'viewer', true),
       ('subject-b', 'tenant-a', 'billing_writer', false),
       ('subject-c', 'tenant-c', 'billing_writer', true),
       ('subject-c', 'tenant-d', 'viewer', true);
SET SESSION AUTHORIZATION zeaz_financial_membership_app_test;
DO $$
BEGIN
  IF has_table_privilege(current_user, 'zeaz_financial.tenant_memberships', 'SELECT') OR
     has_table_privilege(current_user, 'zeaz_financial.tenant_memberships', 'INSERT') OR
     has_table_privilege(current_user, 'zeaz_financial.usage_events', 'SELECT') OR
     pg_has_role(current_user, 'zeaz_financial_runtime', 'member') THEN
    RAISE EXCEPTION 'Membership reader violates least privilege';
  END IF;
  IF (SELECT count(*) FROM zeaz_financial.lookup_billing_membership('subject-a','tenant-a')
      WHERE membership_active AND membership_role = 'billing_writer') <> 1 THEN
    RAISE EXCEPTION 'Active membership lookup failed';
  END IF;
  IF (SELECT count(*) FROM zeaz_financial.lookup_billing_membership('subject-a','tenant-b')
      WHERE membership_role = 'viewer') <> 1 THEN
    RAISE EXCEPTION 'Role isolation lookup failed';
  END IF;
  IF (SELECT count(*) FROM zeaz_financial.lookup_billing_membership('subject-z','tenant-a')) <> 0 THEN
    RAISE EXCEPTION 'Unknown subject unexpectedly authorized';
  END IF;
END $$;
RESET SESSION AUTHORIZATION;
UPDATE zeaz_financial.tenant_memberships
  SET active = false, revoked_at = now(), updated_at = now()
  WHERE subject_id = 'subject-a' AND tenant_id = 'tenant-a';
SET SESSION AUTHORIZATION zeaz_financial_membership_app_test;
DO $$
BEGIN
  IF (SELECT count(*) FROM zeaz_financial.lookup_billing_membership('subject-a','tenant-a')
      WHERE membership_active) <> 0 THEN
    RAISE EXCEPTION 'Revoked membership remained active';
  END IF;
END $$;
RESET SESSION AUTHORIZATION;
SELECT 'PG17_MEMBERSHIP_REVOCATION_ACCEPTANCE_PASS' AS result;
