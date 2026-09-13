from __future__ import annotations

import os
import re
from typing import Any

import httpx


class ProviderError(RuntimeError):
    pass


class DexScreenerProvider:
    def __init__(self, client: httpx.AsyncClient):
        self.client = client
        self.base_url = os.getenv("DEXSCREENER_BASE_URL", "https://api.dexscreener.com").rstrip("/")

    async def token_pairs(self, chain: str, token_address: str) -> list[dict[str, Any]]:
        response = await self.client.get(
            f"{self.base_url}/token-pairs/v1/{chain}/{token_address}"
        )
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, list):
            raise ProviderError("DexScreener returned unexpected token-pairs payload")
        return payload

    async def latest_profiles(self) -> list[dict[str, Any]]:
        response = await self.client.get(f"{self.base_url}/token-profiles/latest/v1")
        response.raise_for_status()
        payload = response.json()
        if isinstance(payload, list):
            return payload
        if isinstance(payload, dict):
            return [payload]
        raise ProviderError("DexScreener returned unexpected profiles payload")

    async def trending_metas(self) -> list[dict[str, Any]]:
        response = await self.client.get(f"{self.base_url}/metas/trending/v1")
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, list):
            raise ProviderError("DexScreener returned unexpected metas payload")
        return payload


class GoPlusProvider:
    def __init__(self, client: httpx.AsyncClient):
        self.client = client
        self.base_url = os.getenv("GOPLUS_BASE_URL", "https://api.gopluslabs.io").rstrip("/")
        self.token = os.getenv("GOPLUS_API_TOKEN", "").strip()

    async def token_security(self, chain_id: str, token_address: str) -> dict[str, Any]:
        headers = {"Authorization": f"Bearer {self.token}"} if self.token else {}
        response = await self.client.get(
            f"{self.base_url}/api/v1/token_security/{chain_id}",
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


class ZaimanProvider:
    """Authenticated OpenAI-compatible gateway for ZeaZ model routing."""

    def __init__(self, client: httpx.AsyncClient):
        self.client = client
        self.base_url = os.getenv("ZAIMAN_BASE_URL", "").strip().rstrip("/")
        self.api_key = os.getenv("ZAIMAN_API_KEY", "").strip()
        self.model = os.getenv("ZAIMAN_MODEL", "").strip()

    @property
    def enabled(self) -> bool:
        return bool(self.base_url and self.api_key and self.model)

    async def summarize_evidence(self, symbol: str, excerpts: list[str]) -> str | None:
        if not self.enabled or not excerpts:
            return None

        prompt = (
            "Analyze only the supplied social evidence for crypto token "
            f"{symbol}. Do not claim live social-network access. Identify the dominant "
            "narrative, organic-vs-shilled clues, red flags, and whether attention looks "
            "EARLY, HEATING_UP, CROWDED, FADING, or DEAD. Be concise.\n\nEvidence:\n"
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
            if not isinstance(item, dict):
                continue
            for content in item.get("content", []):
                if not isinstance(content, dict):
                    continue
                text = content.get("text")
                if isinstance(text, str):
                    chunks.append(text)
        return "\n".join(chunks).strip() or None


class ZKsatoProvider:
    """Authenticated client for the canonical zksato advisory-intent boundary."""

    def __init__(self, client: httpx.AsyncClient):
        self.client = client
        self.base_url = os.getenv("ZKSATO_BASE_URL", "").strip().rstrip("/")
        self.api_key = os.getenv("ZKSATO_API_KEY", "").strip()

    @property
    def enabled(self) -> bool:
        return bool(self.base_url and self.api_key)

    async def submit_advisory(self, intent: dict[str, Any]) -> dict[str, Any]:
        if not self.enabled:
            raise ProviderError("zksato integration is not configured")
        trace_id = str(intent.get("trace_id") or "").strip()
        headers = {
            "X-API-Key": self.api_key,
            "Content-Type": "application/json",
        }
        if trace_id:
            headers["X-Request-ID"] = trace_id
        response = await self.client.post(
            f"{self.base_url}/v1/integrations/ztrader/advisory-intents",
            headers=headers,
            json=intent,
        )
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, dict):
            raise ProviderError("zksato returned unexpected advisory payload")
        if payload.get("execution_allowed") is not False:
            raise ProviderError("zksato advisory boundary violated execution safety invariant")
        return payload


_COLLECTOR_VERSION = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._+:/-]{0,127}$")


class ZWalletProvider:
    """Authenticated read-only client for canonical zWallet on-chain evidence."""

    def __init__(self, client: httpx.AsyncClient):
        self.client = client
        self.base_url = os.getenv("ZWALLET_BASE_URL", "").strip().rstrip("/")
        self.service_token = os.getenv("ZWALLET_SERVICE_TOKEN", "").strip()
        self.evidence_version = os.getenv("ZWALLET_EVIDENCE_VERSION", "1.0").strip()
        if self.evidence_version not in {"1.0", "1.1"}:
            raise ProviderError("unsupported zWallet evidence contract version")

    @property
    def enabled(self) -> bool:
        return bool(self.base_url and self.service_token)

    async def onchain_evidence(
        self,
        *,
        trace_id: str,
        chain: str,
        address: str,
    ) -> dict[str, Any]:
        if not self.enabled:
            raise ProviderError("zWallet integration is not configured")
        response = await self.client.post(
            f"{self.base_url}/v1/integrations/ztrader/onchain-evidence",
            headers={
                "Authorization": f"Bearer {self.service_token}",
                "Content-Type": "application/json",
                "X-Request-ID": trace_id,
            },
            json={
                "version": self.evidence_version,
                "trace_id": trace_id,
                "chain": chain,
                "address": address,
            },
        )
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, dict):
            raise ProviderError("zWallet returned unexpected evidence payload")
        if payload.get("trace_id") != trace_id:
            raise ProviderError("zWallet evidence trace_id mismatch")
        if payload.get("version") != self.evidence_version:
            raise ProviderError("zWallet evidence contract version mismatch")
        if self.evidence_version == "1.1":
            collector_version = payload.get("collector_version")
            if not isinstance(collector_version, str) or not _COLLECTOR_VERSION.fullmatch(
                collector_version
            ):
                raise ProviderError("zWallet evidence collector_version is missing or invalid")
        return payload


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
