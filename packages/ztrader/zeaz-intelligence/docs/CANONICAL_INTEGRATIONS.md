# zTrader Advisory Intent Contract v1

This contract is the only supported boundary from zTrader intelligence into deterministic execution.

## Safety invariants

- The payload is advisory only.
- `mode` is fixed to `paper` in v1.
- zTrader cannot enable live execution.
- zksato remains authoritative for risk, sizing, approvals, kill switches, broker state and reconciliation.
- Missing/stale evidence lowers confidence; it is never treated as safe evidence.
- Every request should carry a trace identifier when available.

## Flow

```text
zworkforce/zTrader
  -> advisory intent
  -> zksato validation/risk
  -> paper execution or deny
```

Live execution requires a separately governed policy after backtest, OOS, paper and forward-validation evidence.

## Canonical dependencies

- execution/risk: cvsz/zksato
- on-chain/wallet: cvsz/zwallet
- AI gateway: cvsz/zaiman
- dashboard: cvsz/zdash
