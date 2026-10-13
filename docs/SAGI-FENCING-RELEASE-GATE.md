# SAGI worker fencing: implementation boundary

This PR implements a fail-closed lease-generation **validation contract**
and negative tests, **not** a production fencing system.

Production work remains:
1. Add a durable worker-generation column/table using the repository-native
   SQLite/PostgreSQL migrations and backfill strategy. Only canonical DB
   transactions may allocate monotonic generations.
2. Change claim/finish/reconcile paths to reject a stale generation in the
   **same transaction** as effect-state writes. Keep legacy endpoints from
   bypassing the required generation after rollout.
3. Bind approval to exact tenant, actor, session, plan, action, target, screen
   digest and browser-effect id before the irreversible UI input.
4. Kill Chromium and network access for revoked leases or emergency stops.
5. Demonstrate two-worker concurrency, stale-worker finish denial, power-loss
   recovery, and unknown-outcome reconciliation on SQLite and PostgreSQL.
6. Deploy into real CNI-enforced deny-all networking with audited proxy and
   verify that DNS, RFC1918, metadata and public bypass attempts fail.
7. Record immutable-image, policy, runtime, run IDs and E2E evidence before GO.

Local validation contracts cannot replace transaction-level fencing or
operator-owned staging evidence. Keep interactive mutations disabled.
