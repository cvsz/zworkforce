import os
import tempfile
import unittest
from pathlib import Path

from valixstack.backtest import load_ticks, run_backtest
from valixstack.broker import PaperBroker, RiskRejected
from valixstack.cli import generate
from valixstack.core import RiskLimits, Side
from valixstack.live import LiveGate


class StackTests(unittest.TestCase):
    def test_generate_and_backtest(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "ticks.csv"
            generate(path, 200, 7)
            result = run_backtest(load_ticks(path))
            self.assertGreaterEqual(result.fills, 0)
            self.assertLessEqual(result.max_exposure, RiskLimits().max_market_exposure_usd)

    def test_order_limit(self):
        broker = PaperBroker(100, RiskLimits(max_order_usd=5))
        with self.assertRaises(RiskRejected):
            broker.buy(Side.UP, 0.5, 6)

    def test_live_is_locked_by_default(self):
        keys = ["VALIX_ENABLE_LIVE", "VALIX_ACKNOWLEDGE_TOTAL_LOSS", "VALIX_ADAPTER_REVIEWED", "VALIX_KILL_SWITCH_READY"]
        old = {key: os.environ.pop(key, None) for key in keys}
        try:
            with self.assertRaises(RuntimeError):
                LiveGate.from_environment().validate()
        finally:
            for key, value in old.items():
                if value is not None:
                    os.environ[key] = value


if __name__ == "__main__":
    unittest.main()

