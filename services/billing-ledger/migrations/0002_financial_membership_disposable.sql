-- Candidate-only migration for an attested disposable PostgreSQL 17 database.
-- Do not apply to customer or persistent databases. No production IdP wiring.
BEGIN;
CREATE TABLE zeaz_financial.tenant_memberships (
  subject_id text NOT NULL CHECK (length(subject_id) BETWEEN 1 AND 128),
  tenant_id text NOT NULL CHECK (length(tenant_id) BETWEEN 1 AND 128),
  membership_role text NOT NULL CHECK (membership_role IN ('billing_writer', 'viewer')),
  active boolean NOT NULL DEFAULT false,
  revoked_at timestamptz,
  updated_at timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (subject_id, tenant_id),
  CONSTRAINT active_membership_not_revoked CHECK (NOT active OR revoked_at IS NULL)
);
REVOKE ALL ON zeaz_financial.tenant_memberships FROM PUBLIC;

-- The application login may execute exactly one narrow, parameterized lookup;
-- it cannot SELECT or mutate the underlying membership table.
CREATE ROLE zeaz_financial_membership_reader NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS;
GRANT USAGE ON SCHEMA zeaz_financial TO zeaz_financial_membership_reader;
CREATE FUNCTION zeaz_financial.lookup_billing_membership(p_subject text, p_tenant text)
RETURNS TABLE(membership_active boolean, membership_role text)
LANGUAGE sql STABLE SECURITY DEFINER SET search_path = pg_catalog, zeaz_financial AS $$
  SELECT m.active, m.membership_role
  FROM zeaz_financial.tenant_memberships AS m
  WHERE m.subject_id = p_subject AND m.tenant_id = p_tenant
$$;
REVOKE ALL ON FUNCTION zeaz_financial.lookup_billing_membership(text, text) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION zeaz_financial.lookup_billing_membership(text, text) TO zeaz_financial_membership_reader;
COMMIT;
