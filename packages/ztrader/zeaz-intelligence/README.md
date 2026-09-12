# ZeaZ zTrader Intelligence v1.0

A production-oriented crypto intelligence sidecar for zTrader. It combines narrative velocity, market discovery, smart-money flow analysis, contract/liquidity risk, portfolio risk budgeting, backtesting, alerts, persistence, realtime events and provider enrichment.

It is intentionally **decision-support first**. Social hype never maps directly to a real-money order.

## Engines

- Narrative: 5m/1h/24h attention acceleration, organic-vs-shilled heuristics
- Discovery: low-cap filters, liquidity quality, ranked candidates
- Market: DexScreener pair/profile enrichment and trending metas
- Smart money: whale flow, known-smart-money net flow, wallet clusters
- Rug/risk: honeypot, mintability, blacklist/pause, taxes, concentration, LP/deployer inputs
- Scoring: Opportunity / Risk / Confidence 0-100
- Trade plan: deterministic entry/DCA/TP/stop simulation with bounded loss budget
- Portfolio: Conservative / Moderate / Aggressive allocation with reserve and per-asset caps
- Evaluation: historical forward-return signal backtest
- Alerts: threshold/narrative/whale-state gates
- Policy: paper-trade gate; live execution is always false in this service
- State: SQLite analysis history and watchlist
- Realtime: Server-Sent Events
- Observability: Prometheus /metrics

## Verdicts

Narrative:
`EARLY / HEATING_UP / CROWDED / FADING / DEAD`

Whales:
`ACCUMULATING / NEUTRAL / DISTRIBUTING`

Rug risk:
`LOW / MEDIUM / HIGH / EXTREME`

Decision support:
`WATCH / WAIT / RESEARCH_MORE / AVOID`

Discovery:
`EARLY / WATCH / SKIP`

Trade-plan simulation:
`ENTER / WAIT / TAKE_PROFIT / EXIT`

## API

- GET /health
- GET /metrics
- POST /v1/analyze
- POST /v1/enrich
- POST /v1/narrative/velocity
- GET /v1/narratives/live
- POST /v1/discover
- POST /v1/discover/live
- POST /v1/wallets/analyze
- POST /v1/trade-plan
- POST /v1/portfolio
- POST /v1/backtest
- POST /v1/alerts/evaluate
- POST /v1/policy/evaluate
- GET /v1/history/{symbol}
- POST /v1/watchlist
- GET /v1/watchlist
- GET /v1/events

## Local run

```bash
cd packages/ztrader/zeaz-intelligence
cp .env.example .env
python3 -m venv .venv
source .venv/bin/activate
make install
make lint
make test
make run
```

## Docker

```bash
cp .env.example .env
docker compose up -d --build
curl -fsS http://127.0.0.1:8218/health
```

The container runs non-root, drops all Linux capabilities, uses no-new-privileges, has a read-only root filesystem and persists only /app/data.

## Kubernetes

```bash
kubectl apply -f deploy/k8s.yaml
```

Provide optional secrets separately:

```bash
kubectl create secret generic ztrader-intelligence-secrets \
  --from-literal=XAI_API_KEY='...' \
  --from-literal=GOPLUS_API_TOKEN='...'
```

## Provider behavior

DexScreener is used for live pair, latest-profile and trending-meta data. GoPlus is optional for contract-risk enrichment. xAI/Grok is optional and summarizes only supplied social evidence; the service does not pretend a generic model call is a live X firehose.

Provider failures do not fabricate values. They are recorded in evidence and reduce confidence.

## Execution boundary

```text
data -> intelligence -> risk/confidence policy
     -> paper trade -> forward validation
     -> exposure check -> explicit approval
     -> external execution gateway
```

This sidecar never enables live execution by itself.
