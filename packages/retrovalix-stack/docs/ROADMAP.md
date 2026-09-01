# Roadmap

## Phase 0 — Research baseline

- Define market rules and settlement semantics
- Establish clean data contracts and timestamp discipline
- Reproduce deterministic backtests including fees and slippage

## Phase 1 — Paper trading

- Live read-only market feed
- Simulated execution against order-book snapshots
- Reconciliation, latency metrics, and shadow decisions
- Minimum 30 days without safety violations

## Phase 2 — Venue sandbox

- Implement current official API adapter
- Idempotent client order IDs and cancel/replace behavior
- Disconnect, stale-feed, partial-fill, and restart tests
- Independent code and security review

## Phase 3 — Limited live canary

- Separate funded wallet with strictly limited capital
- Human approval, tiny limits, and automatic daily shutdown
- Compare expected vs realized fees, slippage, and fill rate
- Roll back on any reconciliation mismatch

## Phase 4 — Production hardening

- High-availability read path, single execution leader
- Disaster recovery and signer rotation
- Model monitoring and strategy retirement rules
- Compliance review for operator jurisdiction and venue terms

