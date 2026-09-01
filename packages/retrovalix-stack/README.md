# ValixStack

An independent, safety-first implementation inspired by publicly described prediction-market workflows. It is not affiliated with RetroValix, Horizon, Claude, or Polymarket and does not claim to reproduce any private strategy.

## Included

- Deterministic synthetic-data generator
- CSV backtester with probability-edge signals
- Paper broker with cash, positions, fees, slippage, and risk limits
- Guarded live adapter that refuses to trade unless every safety gate is explicitly enabled
- Architecture, roadmap, operational checklist, and Claude/Codex master prompt
- Standard-library-only Python runtime and unit tests

## Quick start

```bash
python -m valixstack.cli generate --out data/sample.csv --rows 1000
python -m valixstack.cli backtest --csv data/sample.csv
python -m valixstack.cli paper --csv data/sample.csv
python -m unittest discover -s tests -v
```

Run from the project root with:

```bash
export PYTHONPATH="$PWD/src"
```

## Live mode

Live mode is intentionally a non-executing adapter in this starter. The command performs configuration validation and then stops. Real-money execution must be implemented against current official venue documentation, reviewed, tested on a sandbox, and enabled with all explicit gates.

```bash
python -m valixstack.cli live-check
```

Never place private keys in source files. Trading can lose the entire allocated capital. Backtest results do not predict future performance.

