"""Lightweight console entry point for the zcoder API service."""

from __future__ import annotations

import argparse
from collections.abc import Sequence


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the zcoder API service")
    parser.add_argument("--host", default=None)
    parser.add_argument("--port", type=int, default=None)
    parser.add_argument("--workers", type=int, default=None)
    return parser


def cli(argv: Sequence[str] | None = None) -> None:
    args = build_parser().parse_args(argv)
    from .main import run_server

    run_server(host=args.host, port=args.port, workers=args.workers)


if __name__ == "__main__":
    cli()
