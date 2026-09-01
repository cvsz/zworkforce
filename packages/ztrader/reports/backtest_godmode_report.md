# 📈 zTrader Quantitative Backtest & Safety Report
**Generated Date**: 2026-07-29 02:40:06 UTC
**Scope**: Multi-Agent & Quantitative Strategy Simulation for Binance.TH Integration

## 1. Executive Summary
All quantitative and AI multi-agent strategies underwent 90-day simulated backtesting. Performance metrics including Sharpe Ratio, Sortino Ratio, Max Drawdown, Win Rate, and Profit Factor were evaluated prior to live trading approval request.

## 2. Quantitative Performance Breakdown

| Asset Pair | Strategy | Total Return % | Sharpe Ratio | Sortino Ratio | Max Drawdown % | Win Rate % | Profit Factor | Total Trades |
|---|---|---|---|---|---|---|---|---|
| BTC/USDT | MA Crossover | -6.07% | -0.05 | -0.07 | 17.89% | 50.28% | 0.98 | 2134 |
| BTC/USDT | TradingAgents (Groq) | 0.0% | 0.0 | 0.0 | 0.0% | 0.0% | 1.0 | 0 |
| ETH/USDT | MA Crossover | -16.97% | -0.17 | -0.23 | 30.62% | 50.19% | 0.96 | 2126 |
| ETH/USDT | TradingAgents (Groq) | 0.0% | 0.0 | 0.0 | 0.0% | 0.0% | 1.0 | 0 |
| SOL/USDT | MA Crossover | -27.69% | -0.23 | -0.3 | 43.01% | 50.19% | 0.95 | 2108 |
| SOL/USDT | TradingAgents (Groq) | 0.0% | 0.0 | 0.0 | 0.0% | 0.0% | 1.0 | 0 |
| BNB/USDT | MA Crossover | -17.3% | -0.32 | -0.43 | 25.65% | 49.88% | 0.94 | 2101 |
| BNB/USDT | TradingAgents (Groq) | 0.0% | 0.0 | 0.0 | 0.0% | 0.0% | 1.0 | 0 |

## 3. Binance.TH Exchange Integration & Safety Gates
```ini
EXECUTION_MODE=paper
LIVE_TRADING_ENABLED=false
GLOBAL_KILL_SWITCH=true
EXCHANGE_ID=binance_th
BINANCE_TH_OPERATOR_APPROVAL=PENDING_FORM_APPROVAL
```

### Safety Compliance Checklist:
- [x] Deterministic 90-day Backtest Simulation Completed
- [x] Pre-trade Risk Gate & Max Notional Enforcement Verified
- [x] Global Kill Switch Initialized in Fail-Closed Mode
- [ ] Operator Approval Form Signed for https://www.binance.th/th

