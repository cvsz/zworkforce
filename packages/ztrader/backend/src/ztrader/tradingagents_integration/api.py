"""FastAPI endpoints exposing TradingAgents analysis to the ztrader frontend."""

from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from .adapter import TradingAgentsStrategy
from .data_providers import get_available_data_sources, get_data_source_summary
from .model_catalog import get_provider_summary, get_configured_providers

router = APIRouter(prefix="/api/v1/tradingagents", tags=["tradingagents"])


class AnalysisRequest(BaseModel):
    symbol: str = Field(..., min_length=1, max_length=20)
    date: Optional[str] = None
    llm_provider: str = Field(default="openai", max_length=50)


class AnalysisResponse(BaseModel):
    symbol: str
    signal: str
    confidence: float
    reasoning: str
    analysis_date: str
    risk_score: float
    agents_used: list[str]
    supporting_data: dict[str, Any]


@router.post("/analyze", response_model=AnalysisResponse)
async def analyze_symbol(request: AnalysisRequest):
    """Run TradingAgents' multi-agent analysis on a symbol."""
    try:
        strategy = TradingAgentsStrategy(
            llm_provider=request.llm_provider,
            debug=False,
        )
        signal = strategy.analyze(request.symbol, request.date)
        return AnalysisResponse(
            symbol=signal.symbol,
            signal=signal.signal,
            confidence=signal.confidence,
            reasoning=signal.reasoning,
            analysis_date=signal.analysis_date,
            risk_score=signal.risk_score,
            agents_used=signal.agents_used,
            supporting_data=signal.supporting_data,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/health")
async def health():
    """Health check for TradingAgents integration."""
    return {"status": "ok", "service": "tradingagents-integration"}


@router.get("/providers")
async def list_data_providers():
    """List all available TradingAgents data sources and their status."""
    return {
        "available": get_data_source_summary(),
        "total": len(get_available_data_sources()),
    }


@router.get("/strategies")
async def list_strategies():
    """List available TradingAgents strategies."""
    return {
        "strategies": [
            {
                "id": "tradingagents",
                "name": "TradingAgents LLM Strategy",
                "description": "Multi-agent LLM-powered trading analysis",
                "providers": [p.key for p in get_configured_providers()],
            }
        ]
    }


@router.get("/models")
async def list_models():
    """List all available LLM providers and their supported models."""
    return {
        "providers": get_provider_summary(),
        "total": len(get_provider_summary()),
        "configured": len(get_configured_providers()),
    }