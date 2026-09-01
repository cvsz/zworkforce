from __future__ import annotations

import argparse
import csv
import json
import random
from pathlib import Path

from .backtest import load_ticks, run_backtest
from .live import LiveGate


def generate(path: Path, rows: int, seed: int) -> None:
    rng = random.Random(seed)
    path.parent.mkdir(parents=True, exist_ok=True)
    reference = 100_000.0
    spot = reference
    previous = spot
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["timestamp", "spot", "reference", "up_ask", "down_ask", "volatility", "momentum"])
        for index in range(rows):
            spot *= 1.0 + rng.gauss(0, 0.00025)
            momentum = (spot - previous) / previous
            modelish = min(0.95, max(0.05, 0.5 + 90 * (spot - reference) / reference))
            noise = rng.uniform(-0.04, 0.04)
            up_ask = min(0.98, max(0.02, modelish + noise))
            down_ask = min(0.98, max(0.02, 1.01 - up_ask + rng.uniform(-0.01, 0.01)))
            writer.writerow([index, spot, reference, up_ask, down_ask, 0.00025, momentum])
            previous = spot


def main() -> None:
    parser = argparse.ArgumentParser(prog="valixstack")
    sub = parser.add_subparsers(dest="command", required=True)
    gen = sub.add_parser("generate")
    gen.add_argument("--out", type=Path, default=Path("data/sample.csv"))
    gen.add_argument("--rows", type=int, default=1000)
    gen.add_argument("--seed", type=int, default=7)
    for name in ("backtest", "paper"):
        command = sub.add_parser(name)
        command.add_argument("--csv", type=Path, required=True)
        command.add_argument("--cash", type=float, default=1000.0)
    sub.add_parser("live-check")
    args = parser.parse_args()
    if args.command == "generate":
        generate(args.out, args.rows, args.seed)
        print(args.out)
    elif args.command in ("backtest", "paper"):
        result = run_backtest(load_ticks(args.csv), args.cash)
        print(json.dumps(result.__dict__, default=lambda value: value.value, indent=2))
    else:
        LiveGate.from_environment().validate()


if __name__ == "__main__":
    main()

