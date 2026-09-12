# ZeaZ zTrader Intelligence Sidecar

Additive crypto intelligence service for zTrader. It does **decision support**, not blind auto-buy execution.

## Capabilities

- Narrative stage: EARLY / HEATING_UP / CROWDED / FADING / DEAD
- Whale state: ACCUMULATING / NEUTRAL / DISTRIBUTING
- Rug risk: LOW / MEDIUM / HIGH / EXTREME
- Opportunity / Risk / Confidence scores (0-100)
- DexScreener market enrichment
- Optional GoPlus contract-risk enrichment
- Optional Grok/xAI narrative summarization from supplied social evidence
- Explicit invalidation signals and next metrics to watch

## Safety model

The service never converts social hype directly into a real-money market order. Outputs are:
WATCH / WAIT / RESEARCH_MORE / AVOID.

Use paper trading/backtesting and policy approval before execution.

## Quick start

```bash
cd packages/ztrader/zeaz-intelligence
cp .env.example .env
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
uvicorn ztrader_intel.api:app --host 0.0.0.0 --port 8218
```

Health:

```bash
curl http://127.0.0.1:8218/health
```

Analyze supplied normalized data:

```bash
curl -s http://127.0.0.1:8218/v1/analyze \
  -H 'content-type: application/json' \
  -d '{
    "token":{"symbol":"TEST","chain":"solana"},
    "market":{"market_cap_usd":450000,"liquidity_usd":80000,"volume_24h_usd":120000,"buy_sell_ratio":1.8},
    "social":{"mention_growth_5m":45,"mention_growth_1h":30,"mention_growth_24h":12,"sentiment_score":0.55,"organic_score":0.8},
    "whales":{"net_flow_usd":80000,"accumulating_wallets":4,"distributing_wallets":1},
    "security":{"top10_holder_pct":24,"insider_pct":5,"liquidity_locked":true,"honeypot":false,"mintable":false}
  }'
```

Live DEX enrichment:

```bash
curl -s -X POST http://127.0.0.1:8218/v1/enrich \
  -H 'content-type: application/json' \
  -d '{"token":{"symbol":"TOKEN","chain":"solana","address":"TOKEN_ADDRESS"}}'
```

GoPlus enrichment is enabled when `GOPLUS_CHAIN_ID` is supplied in the request and optionally `GOPLUS_API_TOKEN` in the environment.

Grok/xAI is used only to summarize **evidence you provide**. This service does not claim that a plain model call equals live X firehose access.

## Integrating with zTrader

Treat this as a sidecar:

```text
zTrader -> HTTP -> zeaz-intelligence:8218
                  -> DexScreener
                  -> GoPlus (optional)
                  -> xAI/Grok (optional)
```

Recommended execution gate:

```text
signal
 -> intelligence
 -> risk threshold
 -> confidence threshold
 -> portfolio exposure check
 -> paper/forward validation
 -> explicit policy approval
 -> execution gateway
```
