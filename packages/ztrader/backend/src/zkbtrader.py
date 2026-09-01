"""Compatibility module for the archived market package merged into ztrader."""

from pathlib import Path

__path__ = [
    str(Path(__file__).resolve().parent / "ztrader" / "market"),
]

try:
    from ztrader.market import __version__
except ImportError:
    __version__ = "0.0.0"
