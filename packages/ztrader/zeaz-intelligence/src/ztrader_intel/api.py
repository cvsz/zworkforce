from __future__ import annotations

import os
import secrets
from typing import Annotated

import httpx
from fastapi import Depends, FastAPI, Header, HTTPException, Query
from fastapi.responses import StreamingResponse
from prometheus_fastapi_instrumentator import Instrumentator

from . import __version__
from .alerts import evaluate_alert
from .backtest import evaluate_signals
from .discovery import discover
from .events import event_bus
from .models import (
    AdvisoryIntentSubmission,
    AlertRequest,
    AttentionVelocity,
    BacktestRequest,
    BacktestResponse,
    DiscoveryRequest,
    DiscoveryResponse,
    IntelligenceRequest,
    IntelligenceResponse,
    LiveDiscoveryRequest,
    OnchainEvidenceLookup,
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
from .providers import ProviderError
from .service import (
    enrich_and_analyze,
    fetch_canonical_onchain_evidence,
    live_discovery,
    submit_canonical_advisory_intent,
    trending_narratives,
)
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


def _integration_token(
    authorization: Annotated[str | None, Header()] = None,
    x_api_key: Annotated[str | None, Header(alias="X-API-Key")] = None,
) -> str:
    expected = os.getenv("ZTRADER_INTEL_SERVICE_TOKEN", "").strip()
    if not expected:
        raise HTTPException(status_code=503, detail="integration authentication is not configured")

    supplied = ""
    if authorization and authorization.lower().startswith("bearer "):
        supplied = authorization[7:].strip()
    elif x_api_key:
        supplied = x_api_key.strip()

    if not supplied or not secrets.compare_digest(supplied, expected):
        raise HTTPException(status_code=401, detail="invalid integration credentials")
    return supplied


IntegrationToken = Annotated[str, Depends(_integration_token)]


def _verify_advisory_scope(
    payload: AdvisoryIntentSubmission,
    tenant_id: Annotated[str | None, Header(alias="X-Tenant-ID")] = None,
    account_ref: Annotated[str | None, Header(alias="X-Account-Ref")] = None,
) -> None:
    if not tenant_id or not account_ref:
        raise HTTPException(status_code=400, detail="tenant/account scope headers are required")
    if not secrets.compare_digest(tenant_id, payload.intent.tenant_id):
        raise HTTPException(status_code=403, detail="tenant scope mismatch")
    if not secrets.compare_digest(account_ref, payload.intent.account_ref):
        raise HTTPException(status_code=403, detail="account scope mismatch")



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


@app.post("/v1/integrations/zwallet/evidence")
async def canonical_onchain_evidence(
    payload: OnchainEvidenceLookup,
    _token: IntegrationToken,
):
    try:
        return await fetch_canonical_onchain_evidence(payload)
    except (ProviderError, httpx.HTTPError) as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@app.post("/v1/integrations/zksato/advisory", status_code=202)
async def canonical_advisory_submission(
    payload: AdvisoryIntentSubmission,
    _token: IntegrationToken,
    _scope: Annotated[None, Depends(_verify_advisory_scope)],
):
    try:
        return await submit_canonical_advisory_intent(payload.intent)
    except (ProviderError, httpx.HTTPError) as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@app.get("/v1/events")
async def events():
    async def stream():
        yield ": ztrader-intelligence connected\n\n"
        async for message in event_bus.stream():
            yield f"event: intelligence\ndata: {message}\n\n"

    return StreamingResponse(stream(), media_type="text/event-stream")
