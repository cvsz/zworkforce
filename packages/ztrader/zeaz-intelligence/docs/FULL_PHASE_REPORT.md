# zTrader Crypto Intelligence — Full Phase Implementation Report

## Scope

This package implements the intelligence stack discussed for zTrader while preserving a strict separation between research/scoring and real-money execution.

## Phase 01 — Foundation

Status: COMPLETE

- FastAPI service
- typed Pydantic contracts
- health endpoint
- Docker/Compose
- provider abstraction
- unit-test and lint CI

## Phase 02 — Narrative Intelligence

Status: COMPLETE

- 5m/1h/24h acceleration model
- unique-author growth input
- sentiment input
- organic score
- repeated-content, bot and influencer-concentration penalties
- lifecycle labels: EARLY / HEATING_UP / CROWDED / FADING / DEAD
- optional Grok evidence summarization

Important limitation: true X mention counts require an upstream licensed/authorized X-data source. The engine accepts normalized social evidence without inventing missing metrics.

## Phase 03 — Token Discovery

Status: COMPLETE

- low-cap ceiling
- minimum-liquidity filter
- liquidity/market-cap quality
- buy/sell pressure
- volume/liquidity quality
- candidate ranking
- EARLY / WATCH / SKIP verdict
- live latest-token-profile discovery through DexScreener

Market-only candidates cannot be classified EARLY without social evidence; they remain WATCH/SKIP with reduced confidence.

## Phase 04 — Whale / Smart-Money

Status: COMPLETE

- net wallet flow
- known-smart-money flow
- new smart-money entries
- accumulation/distribution wallet counts
- linked-cluster aggregation
- manipulation concentration score
- ACCUMULATING / NEUTRAL / DISTRIBUTING state

The wallet engine uses supplied normalized transfer evidence and does not label a wallet smart money merely because it is large.

## Phase 05 — Rug / Contract / Liquidity Risk

Status: COMPLETE at engine level

Inputs supported:
- honeypot
- mintability
- blacklist capability
- transfer pause
- buy/sell tax
- source verification
- top-10 holder concentration
- insider concentration
- LP lock and lock percentage
- owner-renounced status
- deployer history
- suspicious deployer flag
- linked-wallet risk
- thin liquidity
- abnormal volume/liquidity
- extremely new pair

GoPlus enrichment populates fields that are available from its response. Additional chain-specific deployer/LP collectors can feed the same schema.

## Phase 06 — Unified Scoring

Status: COMPLETE

Outputs:
- Opportunity Score / 100
- Risk Score / 100
- Confidence Score / 100
- narrative state
- whale state
- rug-risk label
- WATCH / WAIT / RESEARCH_MORE / AVOID
- invalidation conditions
- next metrics to watch

Confidence decreases when evidence is missing/stale or providers fail.

## Phase 07 — Trade Plan and Portfolio

Status: COMPLETE as deterministic decision support

Trade-plan simulator:
- entry zone
- DCA levels
- take-profit levels
- stop
- max position from loss budget
- risk/reward estimate
- ENTER / WAIT / TAKE_PROFIT / EXIT simulation verdict

Portfolio allocator:
- Conservative / Moderate / Aggressive
- reserve allocation
- per-asset caps
- risk-aware scoring
- max-loss budget
- rebalance trigger

No order is placed.

## Phase 08 — Backtesting / Evaluation

Status: COMPLETE

- historical signal threshold replay
- triggered-signal count
- win rate
- average/median forward return
- max drawdown
- positive precision

This provides a measurable way to test whether narrative/opportunity signals actually have predictive value.

## Phase 09 — Alerts / Persistence / Realtime

Status: COMPLETE

- rule-based alert evaluation
- SQLite analysis history
- watchlist persistence
- Server-Sent Events
- Prometheus endpoint

## Phase 10 — Deployment / Hardening

Status: COMPLETE

- non-root Docker runtime
- read-only root filesystem
- dropped Linux capabilities
- no-new-privileges
- persistent data volume
- Kubernetes Deployment/Service/PVC
- probes
- resource requests/limits
- seccomp RuntimeDefault
- service-account token disabled

## Execution Policy

Live execution is deliberately outside this package.

Paper-trade eligibility requires:
- risk < 55
- confidence >= 60
- opportunity >= 65
- rug risk not HIGH/EXTREME
- whales not DISTRIBUTING
- action WATCH

Live execution always returns false and requires an external gateway with:
1. successful paper/forward validation
2. portfolio exposure checks
3. explicit human/configured policy approval
4. exchange kill switch

## External Data Boundaries

Implemented live:
- DexScreener pair data
- DexScreener latest profiles
- DexScreener trending metas
- optional GoPlus token security
- optional xAI/Grok summarization

Normalized-input adapters:
- X/social mention streams
- chain-specific holder/deployer/LP collectors
- exchange flow labeling
- known smart-money labels

This boundary is intentional: unavailable data lowers confidence rather than being fabricated.

## Quality Gates

Dedicated workflow validates:
- install
- Ruff
- pytest
- Docker build

Monorepo required gates remain authoritative before merge.
