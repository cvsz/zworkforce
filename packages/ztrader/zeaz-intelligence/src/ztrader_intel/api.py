from __future__ import annotations

from fastapi import FastAPI, Query
from fastapi.responses import StreamingResponse
from prometheus_fastapi_instrumentator import Instrumentator

from . import __version__
from .alerts import evaluate_alert
from .backtest import evaluate_signals
from .discovery import discover
from .events import event_bus
from .models import (
    AlertRequest,
    AttentionVelocity,
    BacktestRequest,
    BacktestResponse,
    DiscoveryRequest,
    DiscoveryResponse,
    IntelligenceRequest,
    IntelligenceResponse,
    LiveDiscoveryRequest,
    PortfolioRequest,
    PortfolioResponse,
    SmartMoneyRequest,
    SmartMoneyResponse,
    SocialSnapshot,
    TradePlanRequest,
    TradePlanResponse,
    WatchlistEntry,
)
from .narrative import attention_velocity
from .policy import execution_policy
from .portfolio import build_portfolio
from .scoring import analyze
from .service import enrich_and_analyze, live_discovery, trending_narratives
from .store import AnalysisStore
from .trade_plan import build_trade_plan
from .wallets import analyze_wallet_flows

app = FastAPI(
    title="ZeaZ zTrader Intelligence",
    version=__version__,
    description=(
        "Narrative, discovery, smart-money, rug-risk, portfolio, backtest and "
        "decision-support sidecar for zTrader."
    ),
)
Instrumentator().instrument(app).expose(app, endpoint="/metrics", include_in_schema=False)
store = AnalysisStore()


async def _record(result: IntelligenceResponse) -> IntelligenceResponse:
    store.save(result)
    await event_bus.publish(result.model_dump_json())
    return result


@app.get("/health")
async def health():
    return {
        "status": "ok",
        "service": "ztrader-intelligence",
        "version": __version__,
        "live_execution": False,
    }


@app.post("/v1/analyze", response_model=IntelligenceResponse)
async def analyze_payload(payload: IntelligenceRequest):
    return await _record(analyze(payload))


@app.post("/v1/enrich", response_model=IntelligenceResponse)
async def enrich(payload: IntelligenceRequest):
    return await _record(await enrich_and_analyze(payload))


@app.post("/v1/narrative/velocity", response_model=AttentionVelocity)
async def narrative_velocity(payload: SocialSnapshot):
    return attention_velocity(payload)


@app.get("/v1/narratives/live")
async def narratives_live():
    return {"narratives": await trending_narratives()}


@app.post("/v1/discover", response_model=DiscoveryResponse)
async def discover_candidates(payload: DiscoveryRequest):
    return discover(payload)


@app.post("/v1/discover/live", response_model=DiscoveryResponse)
async def discover_live(payload: LiveDiscoveryRequest):
    return await live_discovery(payload)


@app.post("/v1/wallets/analyze", response_model=SmartMoneyResponse)
async def wallets_analyze(payload: SmartMoneyRequest):
    return analyze_wallet_flows(payload)


@app.post("/v1/trade-plan", response_model=TradePlanResponse)
async def trade_plan(payload: TradePlanRequest):
    return build_trade_plan(payload)


@app.post("/v1/portfolio", response_model=PortfolioResponse)
async def portfolio(payload: PortfolioRequest):
    return build_portfolio(payload)


@app.post("/v1/backtest", response_model=BacktestResponse)
async def backtest(payload: BacktestRequest):
    return evaluate_signals(payload)


@app.post("/v1/alerts/evaluate")
async def alerts_evaluate(payload: AlertRequest):
    return evaluate_alert(payload.intelligence, payload.rule)


@app.post("/v1/policy/evaluate")
async def policy_evaluate(payload: IntelligenceResponse):
    return execution_policy(payload)


@app.get("/v1/history/{symbol}")
async def history(
    symbol: str,
    chain: str | None = None,
    limit: int = Query(default=100, ge=1, le=1000),
):
    return {"items": store.history(symbol=symbol, chain=chain, limit=limit)}


@app.post("/v1/watchlist")
async def watchlist_add(payload: WatchlistEntry):
    store.upsert_watchlist(payload)
    return {"status": "stored", "entry": payload}


@app.get("/v1/watchlist", response_model=list[WatchlistEntry])
async def watchlist_list():
    return store.list_watchlist()


@app.get("/v1/events")
async def events():
    async def stream():
        yield ": ztrader-intelligence connected\n\n"
        async for message in event_bus.stream():
            yield f"event: intelligence\ndata: {message}\n\n"

    return StreamingResponse(stream(), media_type="text/event-stream")
