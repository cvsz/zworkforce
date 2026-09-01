import sys
from pathlib import Path

# Ensure repository root is on sys.path for package imports during tests
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ztrader.abt.tools.metaultra.example_module import ExampleStrategy  # noqa: E402


def test_example_strategy_signals():
    s = ExampleStrategy({"name": "test"})
    assert s.generate_signals() == [{"signal": "hold", "strategy": "test"}]


def test_on_tick_prints(capsys):
    s = ExampleStrategy({"name": "test"})
    s.on_tick({"price": 1.23})
    captured = capsys.readouterr()
    assert "test received tick" in captured.out
