from __future__ import annotations

import os
from typing import Any

import httpx


class ProviderError(RuntimeError):
    pass


class DexScreenerProvider:
    def __init__(self, client: httpx.AsyncClient):
        self.client = client
        self.base_url = os.getenv("DEXSCREENER_BASE_URL", "https://api.dexscreener.com").rstrip("/")

    async def token_pairs(self, chain: str, token_address: str) -> list[dict[str, Any]]:
        url = f"{self.base_url}/token-pairs/v1/{chain}/{token_address}"
        response = await self.client.get(url)
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, list):
            raise ProviderError("DexScreener returned unexpected payload")
        return payload


class GoPlusProvider:
    def __init__(self, client: httpx.AsyncClient):
        self.client = client
        self.base_url = os.getenv("GOPLUS_BASE_URL", "https://api.gopluslabs.io").rstrip("/")
        self.token = os.getenv("GOPLUS_API_TOKEN", "").strip()

    async def token_security(self, chain_id: str, token_address: str) -> dict[str, Any]:
        headers = {"Authorization": f"Bearer {self.token}"} if self.token else {}
        url = f"{self.base_url}/api/v1/token_security/{chain_id}"
        response = await self.client.get(
            url,
            params={"contract_addresses": token_address},
            headers=headers,
        )
        response.raise_for_status()
        payload = response.json()
        result = payload.get("result", {}) if isinstance(payload, dict) else {}
        item = result.get(token_address.lower()) or result.get(token_address) or {}
        if not isinstance(item, dict):
            raise ProviderError("GoPlus returned unexpected payload")
        return item


class XAIProvider:
    def __init__(self, client: httpx.AsyncClient):
        self.client = client
        self.base_url = os.getenv("XAI_BASE_URL", "https://api.x.ai/v1").rstrip("/")
        self.api_key = os.getenv("XAI_API_KEY", "").strip()
        self.model = os.getenv("XAI_MODEL", "grok-4.6")

    @property
    def enabled(self) -> bool:
        return bool(self.api_key)

    async def summarize_evidence(self, symbol: str, excerpts: list[str]) -> str | None:
        if not self.enabled or not excerpts:
            return None

        prompt = (
            "Analyze only the supplied social evidence for crypto token "
            f"{symbol}. Do not claim live X access. Identify the dominant narrative, "
            "organic-vs-shilled clues, red flags, and whether attention looks EARLY, "
            "HEATING_UP, CROWDED, FADING, or DEAD. Be concise.\n\nEvidence:\n"
            + "\n".join(f"- {text[:1000]}" for text in excerpts[:40])
        )
        response = await self.client.post(
            f"{self.base_url}/responses",
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            json={"model": self.model, "input": prompt, "store": False},
        )
        response.raise_for_status()
        payload = response.json()

        if isinstance(payload.get("output_text"), str):
            return payload["output_text"]

        chunks: list[str] = []
        for item in payload.get("output", []):
            for content in item.get("content", []):
                text = content.get("text")
                if isinstance(text, str):
                    chunks.append(text)
        return "\n".join(chunks).strip() or None
