from __future__ import annotations

import asyncio
import os
import time
from typing import Any

import httpx

from .discovery import discover
from .models import (
    DiscoveryRequest,
    DiscoveryResponse,
    IntelligenceRequest,
    LiveDiscoveryRequest,
    MarketSnapshot,
    SecuritySnapshot,
    TokenRef,
)
from .providers import DexScreenerProvider, GoPlusProvider, ProviderError, XAIProvider
from .scoring import analyze

_PROVIDER_ERRORS = (httpx.HTTPError, ProviderError, TypeError, ValueError)


def _num(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _flag(value: Any) -> bool | None:
    if value is None or value == "":
        return None
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes"}


def market_from_pairs(pairs: list[dict[str, Any]]) -> MarketSnapshot | None:
    if not pairs:
        return None

    best = max(
        pairs,
        key=lambda pair: _num((pair.get("liquidity") or {}).get("usd")) or 0,
    )
    liquidity = _num((best.get("liquidity") or {}).get("usd"))
    volume = _num((best.get("volume") or {}).get("h24"))
    tx24 = (best.get("txns") or {}).get("h24") or {}
    buys = _num(tx24.get("buys")) or 0
    sells = _num(tx24.get("sells")) or 0
    ratio = buys / max(sells, 1)
    changes = best.get("priceChange") or {}

    pair_created_at = _num(best.get("pairCreatedAt"))
    age_minutes = None
    if pair_created_at:
        age_minutes = max(0.0, (time.time() * 1000 - pair_created_at) / 60_000)

    return MarketSnapshot(
        price_usd=_num(best.get("priceUsd")),
        market_cap_usd=_num(best.get("marketCap")),
        fdv_usd=_num(best.get("fdv")),
        liquidity_usd=liquidity,
        volume_24h_usd=volume,
        buy_sell_ratio=ratio,
        price_change_5m_pct=_num(changes.get("m5")),
        price_change_1h_pct=_num(changes.get("h1")),
        price_change_24h_pct=_num(changes.get("h24")),
        pair_age_minutes=age_minutes,
    )


def security_from_goplus(item: dict[str, Any]) -> SecuritySnapshot:
    holders = item.get("holders") or []
    top10 = 0.0
    if isinstance(holders, list):
        for holder in holders[:10]:
            pct = _num(holder.get("percent")) if isinstance(holder, dict) else None
            if pct is not None:
                top10 += pct * 100 if pct <= 1 else pct

    buy_tax = _num(item.get("buy_tax"))
    sell_tax = _num(item.get("sell_tax"))
    if buy_tax is not None and buy_tax <= 1:
        buy_tax *= 100
    if sell_tax is not None and sell_tax <= 1:
        sell_tax *= 100

    return SecuritySnapshot(
        top10_holder_pct=top10 or None,
        liquidity_locked=None,
        honeypot=_flag(item.get("is_honeypot")),
        mintable=_flag(item.get("is_mintable")),
        blacklistable=_flag(item.get("is_blacklisted")),
        pausable=_flag(item.get("transfer_pausable")),
        buy_tax_pct=buy_tax,
        sell_tax_pct=sell_tax,
        open_source=_flag(item.get("is_open_source")),
    )


async def enrich_and_analyze(req: IntelligenceRequest):
    timeout = float(os.getenv("HTTP_TIMEOUT_SECONDS", "12"))
    evidence: dict[str, Any] = {}
    errors: list[str] = []

    async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
        if req.token.address:
            try:
                pairs = await DexScreenerProvider(client).token_pairs(
                    req.token.chain,
                    req.token.address,
                )
                evidence["dexscreener_pairs"] = len(pairs)
                if req.market is None:
                    req.market = market_from_pairs(pairs)
            except _PROVIDER_ERRORS as exc:
                errors.append(f"dexscreener:{exc.__class__.__name__}")

        if req.token.address and req.token.goplus_chain_id:
            try:
                item = await GoPlusProvider(client).token_security(
                    req.token.goplus_chain_id,
                    req.token.address,
                )
                evidence["goplus"] = bool(item)
                if req.security is None and item:
                    req.security = security_from_goplus(item)
            except _PROVIDER_ERRORS as exc:
                errors.append(f"goplus:{exc.__class__.__name__}")

        result = analyze(req)

        if req.use_grok_summary and req.social:
            try:
                result.grok_summary = await XAIProvider(client).summarize_evidence(
                    req.token.symbol,
                    req.social.excerpts,
                )
            except _PROVIDER_ERRORS as exc:
                errors.append(f"xai:{exc.__class__.__name__}")

    if errors:
        evidence["provider_errors"] = errors
        result.scores.confidence = max(0, result.scores.confidence - 8 * len(errors))
    result.evidence = evidence
    return result


async def live_discovery(payload: LiveDiscoveryRequest) -> DiscoveryResponse:
    timeout = float(os.getenv("HTTP_TIMEOUT_SECONDS", "12"))
    async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
        provider = DexScreenerProvider(client)
        profiles = await provider.latest_profiles()
        allowed = {chain.lower() for chain in payload.chains}
        profiles = [
            profile
            for profile in profiles
            if str(profile.get("chainId", "")).lower() in allowed
            and profile.get("tokenAddress")
        ][: payload.limit * 4]

        semaphore = asyncio.Semaphore(8)

        async def candidate(profile: dict[str, Any]) -> IntelligenceRequest | None:
            async with semaphore:
                chain = str(profile.get("chainId", ""))
                address = str(profile.get("tokenAddress", ""))
                try:
                    pairs = await provider.token_pairs(chain, address)
                except _PROVIDER_ERRORS:
                    return None
                market = market_from_pairs(pairs)
                if market is None:
                    return None
                best = max(
                    pairs,
                    key=lambda pair: _num((pair.get("liquidity") or {}).get("usd")) or 0,
                )
                base_token = best.get("baseToken") or {}
                symbol = str(base_token.get("symbol") or address[:8])
                return IntelligenceRequest(
                    token=TokenRef(symbol=symbol, chain=chain, address=address),
                    market=market,
                    source_freshness_minutes=1,
                )

        results = await asyncio.gather(*(candidate(profile) for profile in profiles))

    requests = [result for result in results if result is not None]
    if not requests:
        return DiscoveryResponse(candidates=[], filtered_count=0)

    return discover(
        DiscoveryRequest(
            candidates=requests,
            max_market_cap_usd=payload.max_market_cap_usd,
            min_liquidity_usd=payload.min_liquidity_usd,
            limit=payload.limit,
        )
    )


async def trending_narratives() -> list[dict[str, Any]]:
    timeout = float(os.getenv("HTTP_TIMEOUT_SECONDS", "12"))
    async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
        return await DexScreenerProvider(client).trending_metas()
