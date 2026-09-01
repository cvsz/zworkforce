"""Compatibility package for archived source modules merged under ztrader.abt."""

from pathlib import Path

__path__ = [
    str(Path(__file__).resolve().parents[1] / "ztrader" / "abt"),
]
