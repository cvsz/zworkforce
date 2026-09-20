from __future__ import annotations

import os
from typing import Any

import httpx

from .models import OrderBook


class PolymarketClient:
    """Read-only HTTP client boundary.

    Endpoint paths remain configurable so deployments can pin the exact
    Polymarket API surface/version they use without changing intelligence code.
    This client never signs or submits orders.
    """

    def __init__(self, client: httpx.AsyncClient):
        self.client = client
        self.base_url = os.getenv("POLYMARKET_API_BASE_URL", "").rstrip("/")
        if not self.base_url:
            raise ValueError("POLYMARKET_API_BASE_URL is not configured")

    async def get_json(self, path: str, **params: Any) -> Any:
        response = await self.client.get(f"{self.base_url}/{path.lstrip('/')}", params=params)
        response.raise_for_status()
        return response.json()

    async def order_book(self, path: str, token_id: str) -> OrderBook:
        payload = await self.get_json(path, token_id=token_id)
        if not isinstance(payload, dict):
            raise TypeError("Polymarket order-book payload must be an object")
        bids = payload.get("bids", [])
        asks = payload.get("asks", [])
        return OrderBook(token_id=token_id, bids=bids, asks=asks)
