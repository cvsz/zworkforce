from __future__ import annotations

from dataclasses import dataclass, field
import json
import random
import re
import time
import urllib.error
import urllib.request
from email.utils import parsedate_to_datetime
from typing import Any

from .config import ProviderConfig


@dataclass
class Usage:
    input_tokens: int = 0
    cached_tokens: int = 0
    output_tokens: int = 0


@dataclass
class ToolCall:
    id: str
    name: str
    arguments: dict[str, Any]


@dataclass
class ProviderResult:
    content: str
    provider_name: str
    model: str
    usage: Usage = field(default_factory=Usage)
    tool_calls: list[ToolCall] = field(default_factory=list)
    raw_message: dict[str, Any] = field(default_factory=dict)


class ProviderError(RuntimeError):
    def __init__(self, message: str, retryable: bool = True):
        super().__init__(message)
        self.retryable = retryable


class MockEndpoint:
    def __init__(self, cfg: ProviderConfig):
        self.cfg = cfg

    def chat(self, tier: str, messages: list[dict[str, Any]], tools: list[dict[str, Any]]) -> ProviderResult:
        model = self.cfg.model_for_tier(tier) or f"mock-{tier}"
        latest = next((m.get("content", "") for m in reversed(messages) if m.get("role") == "user"), "")
        words = len(str(latest).split())
        content = f"[mock:{model}] Task completed. Received {words} words."
        return ProviderResult(
            content=content,
            provider_name=self.cfg.name,
            model=model,
            usage=Usage(max(1, words * 2), 0, max(1, len(content.split()) * 2)),
            raw_message={"role": "assistant", "content": content},
        )


class ZworkforceLocalEndpoint:
    def __init__(self, cfg: ProviderConfig):
        self.cfg = cfg

    def chat(self, tier: str, messages: list[dict[str, Any]], tools: list[dict[str, Any]]) -> ProviderResult:
        import os
        import shutil
        import subprocess

        model = self.cfg.model_for_tier(tier) or "deepseek/deepseek-v4-flash"
        # Prefer the in-repo zktcoder free-model CLI; fall back to the legacy zwf-coder binary.
        executable = shutil.which("zktcoder") or shutil.which("zwf-coder") or "/usr/local/bin/zwf-coder"
        if not os.path.exists(executable):
            raise ProviderError(f"zWorkforce native coding engine binary not found on system", retryable=False)

        # Build prompt representation from conversation messages
        prompt_lines = []
        for m in messages:
            role = m.get("role", "user")
            content = m.get("content", "")
            if isinstance(content, list):
                content = "\n".join(str(part.get("text", "")) if isinstance(part, dict) else str(part) for part in content)
            prompt_lines.append(f"[{role.upper()}]: {content}")
        prompt_text = "\n\n".join(prompt_lines)

        env = {k: os.environ[k] for k in ("PATH", "HOME", "LANG", "LC_ALL", "TZ") if k in os.environ}
        env.setdefault("PATH", "/usr/local/bin:/usr/bin:/bin")
        env.setdefault("HOME", os.path.expanduser("~"))

        try:
            proc = subprocess.run(
                [executable],
                input=prompt_text,
                capture_output=True,
                text=True,
                timeout=self.cfg.timeout_seconds,
                shell=False,
                env=env,
            )
            output = proc.stdout.strip() or proc.stderr.strip()
            if proc.returncode != 0 and not output:
                raise ProviderError(f"zwf-coder exited with code {proc.returncode}", retryable=True)
            words = len(output.split())
            in_words = len(prompt_text.split())
            return ProviderResult(
                content=output or f"[zworkforce:coder] Execution completed successfully with model {model}.",
                provider_name=self.cfg.name,
                model=model,
                usage=Usage(max(1, in_words * 2), 0, max(1, words * 2)),
                raw_message={"role": "assistant", "content": output},
            )
        except subprocess.TimeoutExpired as exc:
            raise ProviderError(f"zwf-coder request timed out after {self.cfg.timeout_seconds}s", retryable=True) from exc
        except Exception as exc:
            raise ProviderError(f"zwf-coder invocation error: {_clean_error(str(exc))}", retryable=True) from exc


class OpenAICompatibleEndpoint:
    def __init__(self, cfg: ProviderConfig):
        self.cfg = cfg

    def chat(self, tier: str, messages: list[dict[str, Any]], tools: list[dict[str, Any]]) -> ProviderResult:
        model = self.cfg.model_for_tier(tier)
        if not model:
            raise ProviderError(f"provider {self.cfg.name} has no {tier} model", retryable=False)
        if not self.cfg.api_key:
            raise ProviderError(f"provider {self.cfg.name} API key is missing", retryable=False)
        body: dict[str, Any] = {"model": model, "messages": messages, "temperature": 0.2}
        if tools:
            body.update({"tools": tools, "tool_choice": "auto"})
        payload = json.dumps(body, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
        last_error = "unknown provider error"
        for attempt in range(self.cfg.retries):
            req = urllib.request.Request(
                self.cfg.base_url + "/chat/completions",
                data=payload,
                headers={
                    "Authorization": f"Bearer {self.cfg.api_key}",
                    "Content-Type": "application/json",
                    "Accept": "application/json",
                    "User-Agent": "zWorkforce/2.0",
                },
                method="POST",
            )
            try:
                with urllib.request.urlopen(req, timeout=self.cfg.timeout_seconds) as resp:
                    raw = resp.read(8 * 1024 * 1024)
                data = json.loads(raw)
                return self._parse(data, model)
            except urllib.error.HTTPError as exc:
                body_text = exc.read(4096).decode(errors="replace")
                last_error = f"HTTP {exc.code}: {_clean_error(body_text)}"
                retryable = exc.code in {408, 409, 425, 429, 500, 502, 503, 504}
                if not retryable:
                    raise ProviderError(f"provider {self.cfg.name} {last_error}", retryable=False) from exc
                if attempt + 1 < self.cfg.retries:
                    time.sleep(_retry_delay(exc.headers.get("Retry-After"), attempt))
            except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
                last_error = _clean_error(str(exc))
                if attempt + 1 < self.cfg.retries:
                    time.sleep(min(0.25 * (2**attempt) + random.random() * 0.1, 3.0))
        raise ProviderError(f"provider {self.cfg.name} request failed: {last_error}", retryable=True)

    def _parse(self, data: dict[str, Any], model: str) -> ProviderResult:
        choices = data.get("choices") or []
        if not choices:
            raise ProviderError(f"provider {self.cfg.name} returned no choices", retryable=True)
        msg = choices[0].get("message") or {}
        usage_raw = data.get("usage") or {}
        prompt_details = usage_raw.get("prompt_tokens_details") or usage_raw.get("input_tokens_details") or {}
        input_tokens = int(usage_raw.get("prompt_tokens", usage_raw.get("input_tokens", 0)) or 0)
        output_tokens = int(usage_raw.get("completion_tokens", usage_raw.get("output_tokens", 0)) or 0)
        cached_tokens = int(prompt_details.get("cached_tokens", 0) or 0)
        calls: list[ToolCall] = []
        for call in msg.get("tool_calls") or []:
            fn = call.get("function") or {}
            raw_args = fn.get("arguments") or "{}"
            try:
                args = json.loads(raw_args) if isinstance(raw_args, str) else dict(raw_args)
            except (json.JSONDecodeError, TypeError, ValueError):
                args = {"_raw": str(raw_args)[:4000]}
            calls.append(ToolCall(str(call.get("id") or "tool"), str(fn.get("name") or ""), args))
        content = msg.get("content") or ""
        if isinstance(content, list):
            content = "\n".join(str(part.get("text", "")) if isinstance(part, dict) else str(part) for part in content)
        return ProviderResult(
            content=str(content),
            provider_name=self.cfg.name,
            model=model,
            usage=Usage(input_tokens, cached_tokens, output_tokens),
            tool_calls=calls,
            raw_message=msg,
        )


class ProviderPool:
    def __init__(self, settings, db):
        self.settings = settings
        self.db = db
        self.configs = tuple(sorted((p for p in settings.providers if p.enabled), key=lambda p: p.priority))
        if not self.configs:
            raise ValueError("at least one enabled provider is required")
        self.endpoints = {
            p.name: MockEndpoint(p) if p.kind == "mock" else (ZworkforceLocalEndpoint(p) if p.kind in {"zworkforce-local", "zworkforce-native"} else OpenAICompatibleEndpoint(p))
            for p in self.configs
        }

    def preview(self, tier: str) -> tuple[str, str]:
        for cfg in self.configs:
            model = cfg.model_for_tier(tier)
            if model:
                return cfg.name, model
        return "", tier

    def chat(self, tier: str, messages: list[dict[str, Any]], tools: list[dict[str, Any]], tenant_id: str | None = None) -> ProviderResult:
        candidates = [p for p in self.configs if p.model_for_tier(tier)]
        if not candidates:
            raise ProviderError(f"no provider has a model configured for tier {tier}", retryable=False)
        errors: list[str] = []
        attempted = 0
        for cfg in candidates:
            if not self.db.provider_available(cfg.name):
                continue
            attempted += 1
            started = time.monotonic()
            try:
                result = self.endpoints[cfg.name].chat(tier, messages, tools)
                latency = (time.monotonic() - started) * 1000
                self.db.record_provider_success(cfg.name, latency, tenant_id)
                return result
            except ProviderError as exc:
                latency = (time.monotonic() - started) * 1000
                self.db.record_provider_failure(
                    cfg.name,
                    latency,
                    str(exc),
                    self.settings.provider_circuit_failures,
                    self.settings.provider_circuit_seconds,
                    tenant_id,
                )
                errors.append(f"{cfg.name}: {exc}")
                if not exc.retryable:
                    continue
        if attempted == 0:
            raise ProviderError("all configured providers are temporarily circuit-open", retryable=True)
        raise ProviderError("all provider candidates failed: " + "; ".join(errors), retryable=True)

    def models(self) -> list[dict[str, Any]]:
        health = {x["name"]: x for x in self.db.list_provider_health()}
        out = []
        for cfg in self.configs:
            out.append({
                "name": cfg.name,
                "kind": cfg.kind,
                "priority": cfg.priority,
                "models": dict(cfg.models),
                "available": self.db.provider_available(cfg.name),
                "health": health.get(cfg.name, {}),
            })
        return out


def build_provider(settings, db) -> ProviderPool:
    return ProviderPool(settings, db)


def _clean_error(text: str) -> str:
    text = text.replace("\r", " ").replace("\n", " ").strip()
    # Provider responses occasionally echo credentials or headers. Never persist those in task/provider errors.
    text = re.sub(r"(?i)(authorization\s*[:=]\s*bearer\s+)[^\s,;]+", r"\1[REDACTED]", text)
    text = re.sub(r"(?i)((?:api[_-]?key|token|secret|password)\s*[:=]\s*)[\"']?[^\s,;\"']+", r"\1[REDACTED]", text)
    text = re.sub(r"\b(?:sk|zwf)_[A-Za-z0-9_-]{12,}\b", "[REDACTED]", text)
    return text[:1000]


def _retry_delay(header: str | None, attempt: int) -> float:
    if header:
        try:
            return max(0.0, min(float(header), 30.0))
        except ValueError:
            try:
                dt = parsedate_to_datetime(header)
                return max(0.0, min(dt.timestamp() - time.time(), 30.0))
            except Exception:
                pass
    return min(0.5 * (2**attempt) + random.random() * 0.25, 5.0)
