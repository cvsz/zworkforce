from __future__ import annotations

from fastapi import FastAPI

from . import __version__
from .models import IntelligenceRequest, IntelligenceResponse
from .scoring import analyze
from .service import enrich_and_analyze

app = FastAPI(
    title="ZeaZ zTrader Intelligence",
    version=__version__,
    description="Narrative, whale, rug-risk and opportunity scoring sidecar for zTrader.",
)


@app.get("/health")
async def health():
    return {"status": "ok", "service": "ztrader-intelligence", "version": __version__}


@app.post("/v1/analyze", response_model=IntelligenceResponse)
async def analyze_payload(payload: IntelligenceRequest):
    return analyze(payload)


@app.post("/v1/enrich", response_model=IntelligenceResponse)
async def enrich(payload: IntelligenceRequest):
    return await enrich_and_analyze(payload)
