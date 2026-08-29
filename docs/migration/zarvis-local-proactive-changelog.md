# Z.A.R.V.I.S. local proactive scheduler slice

- Added loopback-only owner policy and suggestion console.
- Added durable read-only local health schedules with IANA timezone and missed-run handling.
- Added server-side quiet hours, daily notification budgets, confidence thresholds, cooldowns, and fingerprint deduplication.
- Added explainable delivered and suppressed notification decisions with source and evidence.
- Added revocation, useful/irrelevant/false-positive feedback, and restart recovery.
- Added approval-only action handoff that cannot execute autonomously.
- Added separate proactive-worker credential, schemas, regression tests, architecture, threat model, runbook, validation record, local Compose services, installer upgrade, and end-to-end evidence.

This fragment should be folded into the root `CHANGELOG.md` during local release consolidation.
