-- Disposable-only PostgreSQL 17 candidate. NEVER run on customer or persistent databases.
-- Operator-gated revocation; the caller cannot mutate membership or audit tables directly.
BEGIN;

CREATE TABLE zeaz_financial.membership_revocation_audit (
  request_id text PRIMARY KEY CHECK (request_id ~ '^[A-Za-z0-9_-]{16,128}$'),
  subject_id text NOT NULL CHECK (length(subject_id) BETWEEN 1 AND 128),
  tenant_id text NOT NULL CHECK (length(tenant_id) BETWEEN 1 AND 128),
  reason text NOT NULL CHECK (length(reason) BETWEEN 8 AND 256),
  actor_login name NOT NULL,
  revoked_at timestamptz NOT NULL,
  recorded_at timestamptz NOT NULL DEFAULT clock_timestamp()
);
REVOKE ALL ON zeaz_financial.membership_revocation_audit FROM PUBLIC;

CREATE ROLE zeaz_financial_membership_revoker
  NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS;
GRANT USAGE ON SCHEMA zeaz_financial TO zeaz_financial_membership_revoker;

CREATE FUNCTION zeaz_financial.revoke_billing_membership(
  p_request_id text, p_subject text, p_tenant text, p_reason text
) RETURNS boolean
LANGUAGE plpgsql VOLATILE SECURITY DEFINER
SET search_path = pg_catalog, zeaz_financial
AS $function$
DECLARE
  v_existing record;
  v_revoked_at timestamptz;
BEGIN
  IF p_request_id IS NULL OR p_request_id !~ '^[A-Za-z0-9_-]{16,128}$'
     OR p_subject IS NULL OR length(p_subject) NOT BETWEEN 1 AND 128
     OR p_subject <> btrim(p_subject) OR p_subject ~ '[[:cntrl:]]'
     OR p_tenant IS NULL OR length(p_tenant) NOT BETWEEN 1 AND 128
     OR p_tenant <> btrim(p_tenant) OR p_tenant ~ '[[:cntrl:]]'
     OR p_reason IS NULL OR length(p_reason) NOT BETWEEN 8 AND 256
     OR p_reason <> btrim(p_reason) OR p_reason ~ '[[:cntrl:]]' THEN
    RAISE EXCEPTION 'Invalid membership revocation request' USING ERRCODE = '22023';
  END IF;

  -- Serialize same-key concurrent retries; a hash collision only reduces throughput.
  PERFORM pg_catalog.pg_advisory_xact_lock(pg_catalog.hashtextextended(p_request_id, 0));
  SELECT a.subject_id, a.tenant_id, a.reason, a.actor_login
    INTO v_existing
    FROM zeaz_financial.membership_revocation_audit AS a
   WHERE a.request_id = p_request_id;
  IF FOUND THEN
    IF v_existing.subject_id IS DISTINCT FROM p_subject
       OR v_existing.tenant_id IS DISTINCT FROM p_tenant
       OR v_existing.reason IS DISTINCT FROM p_reason
       OR v_existing.actor_login::text IS DISTINCT FROM session_user::text THEN
      RAISE EXCEPTION 'Conflicting membership revocation replay' USING ERRCODE = '23505';
    END IF;
    RETURN false;
  END IF;

  UPDATE zeaz_financial.tenant_memberships
     SET active = false, revoked_at = clock_timestamp(), updated_at = clock_timestamp()
   WHERE subject_id = p_subject AND tenant_id = p_tenant
     AND active = true AND revoked_at IS NULL
  RETURNING revoked_at INTO v_revoked_at;
  IF NOT FOUND THEN
    RAISE EXCEPTION 'Membership not active or not found' USING ERRCODE = 'P0002';
  END IF;

  -- The update and immutable-to-app audit insert share one transaction.
  INSERT INTO zeaz_financial.membership_revocation_audit
    (request_id, subject_id, tenant_id, reason, actor_login, revoked_at)
  VALUES (p_request_id, p_subject, p_tenant, p_reason, session_user, v_revoked_at);
  RETURN true;
END
$function$;

REVOKE ALL ON FUNCTION zeaz_financial.revoke_billing_membership(text, text, text, text) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION zeaz_financial.revoke_billing_membership(text, text, text, text)
  TO zeaz_financial_membership_revoker;
COMMIT;
