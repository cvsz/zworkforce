# SAGI Computer Use production admission — DENY BY DEFAULT

This branch defines an independent evidence validation contract only.
It is **not** wired into production deployment and does **not** attest
that any of the listed checks has passed. The caller must retrieve signed
or access-controlled evidence from an independent deployment authority.

Required exact-release evidence:
- action-specific canonical human approval and independent reviewer
- atomic browser effect claim with worker-generation fencing
- durable audit plus crash/unknown-state reconciliation
- tenant isolation and expiring session credentials
- actual cluster CNI egress enforcement and filtering proxy
- in-flight emergency stop demonstrated against active Chromium
- trusted screenshot freshness verified at action dispatch
- live Chromium E2E on immutable worker image
- negative network-isolation E2E for private/metadata addresses and bypass paths
- independent security approval on the exact candidate commit

The existing SQLite experimental claim implementation, BrowserEffectMixin
without fencing, README-only network-isolation requirements and test harness
without real staging runs do not fulfill the corresponding requirements.

Do not enable live clicking, typing, file uploads, external posting, payments
or production mutation until all gates are independently evidenced. Do not
merge a PR solely because individual GitHub Actions jobs are green.

Repository release evidence in `docs/PRODUCTION-EVIDENCE.md` remains separate
and is not automatically satisfied by this SAGI contract.
