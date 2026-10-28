# Reader's Guide — ZEARN / zTrader Paper Trading Reference

## Purpose

This guide records the approved reference material for the zTrader Paper Trading work in `cvsz/zworkforce`. ZEARN is the reference for product boundaries, paper-first execution, risk controls, auditability, and production-readiness gates. This file is a reading and traceability guide; it does not assert that ZEARN components are implemented in zTrader.

## Primary references

1. **[ZEARN README](https://github.com/cvsz/zearn/blob/main/README.md)** — product scope, architecture, dashboard surfaces, safe defaults, and live-execution gates.
2. **[ZEARN AGENTS.md](https://github.com/cvsz/zearn/blob/main/AGENTS.md)** — mandatory engineering and safety invariants for agents working on ZEARN.
3. **[ZEARN production readiness](https://github.com/cvsz/zearn/blob/main/docs/production-readiness.md)** — P0/P1/P2 requirements and the evidence rule for live-funds gates.
4. **[zTrader Paper Trading implementation](packages/ztrader/zeaz-intelligence/src/ztrader_intel/paper_trading.py)** — current local simulation ledger.
5. **[zTrader API implementation](packages/ztrader/zeaz-intelligence/src/ztrader_intel/api.py)** — service authentication, tenant-bound authentication, and Paper Trading routes.
6. **[zTrader package README](packages/ztrader/zeaz-intelligence/README.md)** — local setup and package-specific usage/limitations.
7. **[Master trading plan](master-trading-247.md)** — current scope, sequencing, and acceptance expectations.

## Reference principles to preserve

- Default to Paper Trading; live execution stays disabled and no real exchange/broker order path is added in this scope.
- A caller-provided tenant identifier is not identity. Every mutation and read must require service authentication and a tenant credential bound to the normalized tenant.
- Treat passing unit tests and CI as necessary but insufficient evidence for operational readiness.
- Record and test idempotency, authorization failures, cross-tenant denial, restart persistence, transaction rollback, and migration behavior.
- Simulated results must disclose modeling limits: fees and slippage are assumptions; they do not prove market-quality fills, profitability, or live-execution safety.
- Do not claim guaranteed returns, lossless performance, or production readiness without implementation, tests, and operational evidence.
- Keep credentials and signing material out of browser bundles, logs, fixtures, prompts, and source control.
- Document and exercise persistent-volume backup, restore, and recovery before relying on the ledger operationally.

## Current zTrader scope

The implementation in PR #340 is a SQLite-backed simulated ledger for accounts, orders, positions, cash, fees, and PnL. The API is expected to remain paper-only. The current ledger uses floating-point / SQLite REAL accounting and does not yet enforce aggregate exposure, drawdown/kill-switch, or stale-price admission limits. Therefore it must not be treated as authoritative financial accounting or as the risk engine for any live strategy.

## Readiness checklist

- [ ] Service authentication and tenant-bound authorization required on all Paper Trading routes.
- [ ] Negative tests cover missing/invalid service credentials, missing tenant token, token mismatch, and cross-tenant create/read/order attempts.
- [ ] Financial calculations use a documented precision/rounding policy; migration and regression tests cover the stored representation.
- [ ] Risk admission has explicit limits for per-position and aggregate exposure, drawdown/daily loss, and stale/missing prices; violations fail closed.
- [ ] Idempotency and concurrent requests cannot create duplicate ledger effects.
- [ ] SQLite persistent-volume backup and restore procedure is documented and exercised against a disposable test database.
- [ ] Exact-head CI, CodeQL, Dependency Review, integration checks, and Windows client checks pass.
- [ ] Independent review approves the exact current head and all required threads/findings are resolved.
- [ ] Paper-only configuration remains explicit; no live order submission, signer, or real-funds operation is enabled.

## SQLite backup and restore drill

Use only a stopped or quiesced disposable Paper Trading instance for a filesystem copy. For a running SQLite database, prefer SQLite's online backup API rather than copying only the main database file, especially if WAL mode is enabled.

Example using Python's standard library (replace paths with the configured disposable test database):

```bash
python - <<'PY'
import sqlite3

source = "./data/ztrader_paper.db"
backup = "./data/ztrader_paper.backup.db"

with sqlite3.connect(source) as src, sqlite3.connect(backup) as dst:
    src.backup(dst)

with sqlite3.connect(backup) as check:
    result = check.execute("PRAGMA integrity_check").fetchone()[0]
    if result != "ok":
        raise SystemExit(f"backup integrity check failed: {result}")
    print("backup integrity_check:", result)
PY
```

For a restore drill, stop the disposable service, preserve the original test database, restore the backup to a separate path, initialize the application against that restored path, and verify expected account/order counts and tenant boundaries. Record the tested commit, commands, results, and recovery time. Do not overwrite a production volume as part of this drill.

## Decision rule

Keep PR #340 in Draft and keep live execution disabled until all blocking financial-correctness, risk-control, backup/restore, exact-head CI, and independent-review requirements are evidenced. A checklist item is not complete merely because it is documented.
