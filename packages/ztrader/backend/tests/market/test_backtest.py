from ztrader.engine.backtest import BacktestEngine
from ztrader.engine.strategy import Candle, MovingAverageCrossoverStrategy


def test_backtest_engine_runs_deterministically() -> None:
    candles = [
        Candle(timestamp="t1", open=1, high=1, low=1, close=10, volume=1),
        Candle(timestamp="t2", open=1, high=1, low=1, close=11, volume=1),
        Candle(timestamp="t3", open=1, high=1, low=1, close=12, volume=1),
        Candle(timestamp="t4", open=1, high=1, low=1, close=13, volume=1),
        Candle(timestamp="t5", open=1, high=1, low=1, close=14, volume=1),
    ]
    strategy = MovingAverageCrossoverStrategy(symbol="BTC/USDT", notional=25.0)

    result = BacktestEngine(allowed_symbols=("BTC/USDT",), starting_usdt=1000.0).run(strategy, candles)

    assert result.strategy_id == "ma-crossover-paper"
    assert result.candles_seen == 5
    assert result.orders_created == 1
    assert result.ending_usdt < 1000.0
    assert isinstance(result.sharpe_ratio, float)
    assert isinstance(result.max_drawdown_pct, float)
    assert isinstance(result.win_rate_pct, float)

