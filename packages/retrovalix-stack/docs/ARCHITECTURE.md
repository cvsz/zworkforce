# Architecture

## Data plane

1. Spot adapters ingest timestamped reference prices.
2. Venue adapters ingest market metadata and order books.
3. A feature engine calculates distance-to-reference, momentum, volatility, depth, and imbalance.
4. A calibrated model estimates outcome probability.
5. Strategy policy converts model-vs-market divergence into order intents.
6. Risk policy rejects intents outside exposure, loss, staleness, or sizing limits.
7. Broker adapters execute in backtest, paper, sandbox, or explicitly approved live mode.
8. An immutable event journal records inputs, decisions, orders, fills, and reconciliation.

## Control plane

- Configuration and secret references
- Mode and live-safety gates
- Kill switch and circuit breakers
- Metrics, alerting, audit logs, and daily reconciliation
- Model/version registry and reproducible backtests

## Production target

Recommended components when advancing beyond this standard-library prototype:

- Python 3.12 async services
- PostgreSQL/TimescaleDB for events and research datasets
- Redis only for ephemeral locks/cache, never as the ledger of record
- Object storage for raw immutable snapshots
- Prometheus, Grafana, and OpenTelemetry
- Container deployment with one active execution leader
- Secret manager or hardware-backed signer

These recommendations are project design choices, not claims about RetroValix's private stack.

