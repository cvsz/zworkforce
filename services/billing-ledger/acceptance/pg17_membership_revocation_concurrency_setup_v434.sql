-- Synthetic concurrent revocation fixtures, disposable database only.
\set ON_ERROR_STOP on
INSERT INTO zeaz_financial.tenant_memberships(subject_id, tenant_id, membership_role, active)
VALUES ('subject-e', 'tenant-e', 'billing_writer', true),
       ('subject-f', 'tenant-f', 'billing_writer', true);
