# SAGI Atomic Approval Consumption / Replay-safe Execution

**Status: experimental reference adapter, NOT production wiring.** The
`AtomicApprovalStore` is an SQLite local reference implementation for a
single-action conditional claim. Approval records must originate in the
canonical zWorkforce approval service. This adapter does not verify issuer
authority, four-eyes separation or approval signatures by itself.

## Guarantees and failure semantics

- A matching pending approval can be claimed by at most one competing worker.
- The action identity includes request digest, tenant, actor, session, plan digest,
  action and target. Expired claims cannot start.
- Duplicate inserts fail; claims never reset to approved.
- Failed or uncertain claimed actions do not retry automatically.
- This is **at-most-once dispatch** from a local DB, not exactly-once external side effects.
  A crash after the DB claim and before browser execution results in an
  ambiguous claim, requiring operator reconciliation.
- The adapter does not have session leasing, true recovery, Postgres transaction
  integration, screenshot freshness or an outbox; all remain required.

## Network-isolated worker deployment contract

Deploy Chromium only in a disposable unprivileged container/network namespace:
read-only root filesystem, non-root UID, dropped capabilities, no host mounts,
no shared browser profile, seccomp/AppArmor, pids/memory/CPU quotas, default
network deny and an explicit egress proxy. Enforce destination hostname AND
resolved IP at the proxy/firewall including DNS rebinding, redirects, private
networks and cloud metadata; browser routing alone is insufficient.

The current `sagi_browser_runtime.py` remains read-only. No click/type/scroll
production action is enabled by this PR. A credible E2E run must start the real
container in an isolated network, launch Chromium, exercise an allowlisted
test page, then prove internal/metadata/network escapes and duplicate claims
are denied, and record logs/screenshots with redaction and retention limits.

## Validation

`PYTHONPATH=. python3 -m unittest tests.test_sagi_atomic_approval -v`

Full repository tests and actual isolated browser E2E remain mandatory.
