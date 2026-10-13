# SAGI Approval Request Boundary

**Status:** forward-roadmap experimental, stacked on PR #270. No runtime integration.

`create_approval_request` constructs a deterministic request identifier scoped
to loop, tenant, actor, plan digest, action, target and step. It creates
request **metadata only**, not authorization. In particular, this implementation
does not read, grant, approve, consume or replay-protect real approvals.

Next requirements: canonical durable approval adapter, expiry and nonce
validation, four-eyes separation, target-specific permission checks,
transactional replay protection, canonical queue gating, independent audit,
and negative/HA integration tests. Treat changed plans as new approvals;
never use this fingerprint as a bearer token or secret.
