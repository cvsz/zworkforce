-- Assert real-driver concurrency produced exactly one audit event per membership.
\set ON_ERROR_STOP on
DO $test$
BEGIN
  IF (SELECT count(*) FROM zeaz_financial.membership_revocation_audit
      WHERE subject_id = 'subject-e' AND tenant_id = 'tenant-e'
        AND request_id = 'v434-concurrent-same-identity') <> 1 THEN
    RAISE EXCEPTION 'Concurrent same-key revocation audit cardinality mismatch';
  END IF;
  IF (SELECT count(*) FROM zeaz_financial.membership_revocation_audit
      WHERE subject_id = 'subject-f' AND tenant_id = 'tenant-f'
        AND request_id IN ('v434-concurrent-distinct-a', 'v434-concurrent-distinct-b')) <> 1 THEN
    RAISE EXCEPTION 'Concurrent distinct-key revocation audit cardinality mismatch';
  END IF;
  IF (SELECT count(*) FROM zeaz_financial.tenant_memberships
      WHERE (subject_id, tenant_id) IN (('subject-e','tenant-e'),('subject-f','tenant-f'))
        AND active = false AND revoked_at IS NOT NULL) <> 2 THEN
    RAISE EXCEPTION 'Concurrent revocation state mismatch';
  END IF;
END
$test$;
SELECT 'PG17_MEMBERSHIP_REVOCATION_CONCURRENCY_PASS' AS result;
