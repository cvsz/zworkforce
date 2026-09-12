from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import json
import os
from typing import Any


DASHBOARD_EVENT_DEFAULT_RETENTION_SECONDS = 7 * 24 * 60 * 60
DASHBOARD_EVENT_MAX_RETENTION_SECONDS = 365 * 24 * 60 * 60


@dataclass(frozen=True)
class Rate:
    input: float
    cached: float
    output: float


@dataclass(frozen=True)
class BootstrapKey:
    secret: str
    role: str
    tenant_id: str = "default"
    name: str = "bootstrap"
    scopes: tuple[str, ...] = ("*",)


@dataclass(frozen=True)
class ProviderConfig:
    name: str
    kind: str
    base_url: str = ""
    api_key: str = ""
    priority: int = 100
    timeout_seconds: int = 90
    retries: int = 2
    models: dict[str, str] = field(default_factory=dict)
    enabled: bool = True

    def model_for_tier(self, tier: str) -> str:
        return self.models.get(tier, "")


@dataclass(frozen=True)
class Settings:
    env: str = "development"
    host: str = "0.0.0.0"
    port: int = 9569
    data_dir: Path = Path("./data")
    workspace_root: Path = Path(".")
    default_tenant: str = "default"

    embedded_workers: int = 1
    worker_poll_ms: int = 250
    lease_seconds: int = 60
    lease_heartbeat_seconds: int = 15
    dashboard_event_retention_seconds: int = DASHBOARD_EVENT_DEFAULT_RETENTION_SECONDS
    max_attempts: int = 3
    retry_base_seconds: int = 2
    max_delegation_depth: int = 8

    providers: tuple[ProviderConfig, ...] = ()
    bootstrap_keys: tuple[BootstrapKey, ...] = ()
    metrics_bearer: str = ""

    http_allowlist: tuple[str, ...] = ()
    http_allow_private: bool = False
    http_mutating_enabled: bool = False
    http_max_redirects: int = 2
    shell_enabled: bool = False
    shell_allowlist: tuple[str, ...] = ("git", "python", "python3", "node", "npm")
    shell_env_allowlist: tuple[str, ...] = ("PATH", "HOME", "LANG", "LC_ALL", "TZ")
    tool_timeout_seconds: int = 30
    tool_max_output_bytes: int = 262_144
    workspace_write_max_bytes: int = 1_048_576
    workspace_read_enabled: bool = True
    workspace_write_enabled: bool = True

    max_request_bytes: int = 1_048_576
    api_rate_limit_per_minute: int = 240
    cors_origins: tuple[str, ...] = ()
    trust_proxy_identity: bool = False
    proxy_identity_secret: str = ""

    global_daily_budget_credits: float = 0.0
    provider_circuit_failures: int = 3
    provider_circuit_seconds: int = 30
    skill_signing_key: str = ""

    doom_loop_max_identical_calls: int = 3
    doom_loop_max_consecutive_failures: int = 5

    rates: dict[str, Rate] = field(default_factory=lambda: {
        "sol": Rate(125.0, 12.5, 750.0),
        "terra": Rate(50.0, 5.0, 300.0),
        "luna": Rate(5.0, 0.5, 30.0),
    })

    @property
    def database_path(self) -> Path:
        return self.data_dir / "zworkforce.sqlite3"

    def first_model_for_tier(self, tier: str) -> str:
        for provider in sorted((p for p in self.providers if p.enabled), key=lambda p: p.priority):
            model = provider.model_for_tier(tier)
            if model:
                return model
        return tier

    @classmethod
    def from_env(cls) -> "Settings":
        env = os.getenv("ZWORKFORCE_ENV", "development").strip().lower()
        default_tenant = _slug(os.getenv("ZWORKFORCE_DEFAULT_TENANT", "default"), "tenant")

        def f(name: str, default: float) -> float:
            return float(os.getenv(name, str(default)))

        def i(name: str, default: int, minimum: int | None = None) -> int:
            value = int(os.getenv(name, str(default)))
            return max(minimum, value) if minimum is not None else value

        def b(name: str, default: bool = False) -> bool:
            return os.getenv(name, str(default)).strip().lower() in {"1", "true", "yes", "on"}

        def csv(name: str, default: str = "") -> tuple[str, ...]:
            return tuple(x.strip() for x in os.getenv(name, default).split(",") if x.strip())

        rates = {
            "sol": Rate(f("ZWORKFORCE_SOL_INPUT_CREDITS", 125), f("ZWORKFORCE_SOL_CACHED_CREDITS", 12.5), f("ZWORKFORCE_SOL_OUTPUT_CREDITS", 750)),
            "terra": Rate(f("ZWORKFORCE_TERRA_INPUT_CREDITS", 50), f("ZWORKFORCE_TERRA_CACHED_CREDITS", 5), f("ZWORKFORCE_TERRA_OUTPUT_CREDITS", 300)),
            "luna": Rate(f("ZWORKFORCE_LUNA_INPUT_CREDITS", 5), f("ZWORKFORCE_LUNA_CACHED_CREDITS", .5), f("ZWORKFORCE_LUNA_OUTPUT_CREDITS", 30)),
        }

        providers = _providers_from_env(env)
        bootstrap_keys = _keys_from_env(env, default_tenant)

        trust_proxy = b("ZWORKFORCE_TRUST_PROXY_IDENTITY")
        proxy_secret = os.getenv("ZWORKFORCE_PROXY_IDENTITY_SECRET", "")
        if env == "production" and trust_proxy and len(proxy_secret) < 24:
            raise ValueError("ZWORKFORCE_PROXY_IDENTITY_SECRET must be at least 24 characters when proxy identity is enabled")

        skill_key = os.getenv("ZWORKFORCE_SKILL_SIGNING_KEY", "")
        if env == "production" and skill_key and len(skill_key) < 24:
            raise ValueError("ZWORKFORCE_SKILL_SIGNING_KEY must be at least 24 characters")

        metrics_bearer = os.getenv("ZWORKFORCE_METRICS_BEARER", "").strip()
        if env == "production" and metrics_bearer and len(metrics_bearer) < 24:
            raise ValueError("ZWORKFORCE_METRICS_BEARER must be at least 24 characters when configured")

        return cls(
            env=env,
            host=os.getenv("ZWORKFORCE_HOST", "0.0.0.0"),
            port=i("ZWORKFORCE_PORT", 9569, 1),
            data_dir=Path(os.getenv("ZWORKFORCE_DATA_DIR", "./data")).expanduser().resolve(),
            workspace_root=Path(os.getenv("ZWORKFORCE_WORKSPACE_ROOT", ".")).expanduser().resolve(),
            default_tenant=default_tenant,
            embedded_workers=i("ZWORKFORCE_EMBEDDED_WORKERS", 1 if env != "production" else 0, 0),
            worker_poll_ms=i("ZWORKFORCE_WORKER_POLL_MS", 250, 25),
            lease_seconds=i("ZWORKFORCE_LEASE_SECONDS", 60, 10),
            lease_heartbeat_seconds=i("ZWORKFORCE_LEASE_HEARTBEAT_SECONDS", 15, 2),
            dashboard_event_retention_seconds=min(
                i("ZWORKFORCE_DASHBOARD_EVENT_RETENTION_SECONDS", DASHBOARD_EVENT_DEFAULT_RETENTION_SECONDS, 60),
                DASHBOARD_EVENT_MAX_RETENTION_SECONDS,
            ),
            max_attempts=i("ZWORKFORCE_MAX_ATTEMPTS", 3, 1),
            retry_base_seconds=i("ZWORKFORCE_RETRY_BASE_SECONDS", 2, 1),
            max_delegation_depth=i("ZWORKFORCE_MAX_DELEGATION_DEPTH", 8, 1),
            providers=providers,
            bootstrap_keys=bootstrap_keys,
            metrics_bearer=metrics_bearer,
            http_allowlist=tuple(x.lower().rstrip(".") for x in csv("ZWORKFORCE_HTTP_ALLOWLIST")),
            http_allow_private=b("ZWORKFORCE_HTTP_ALLOW_PRIVATE"),
            http_mutating_enabled=b("ZWORKFORCE_HTTP_MUTATING_ENABLED"),
            http_max_redirects=i("ZWORKFORCE_HTTP_MAX_REDIRECTS", 2, 0),
            shell_enabled=b("ZWORKFORCE_SHELL_ENABLED"),
            shell_allowlist=csv("ZWORKFORCE_SHELL_ALLOWLIST", "git,python,python3,node,npm"),
            shell_env_allowlist=csv("ZWORKFORCE_SHELL_ENV_ALLOWLIST", "PATH,HOME,LANG,LC_ALL,TZ"),
            tool_timeout_seconds=i("ZWORKFORCE_TOOL_TIMEOUT_SECONDS", 30, 1),
            tool_max_output_bytes=i("ZWORKFORCE_TOOL_MAX_OUTPUT_BYTES", 262144, 4096),
            workspace_write_max_bytes=i("ZWORKFORCE_WORKSPACE_WRITE_MAX_BYTES", 1048576, 1024),
            workspace_read_enabled=b("ZWORKFORCE_WORKSPACE_READ_ENABLED", True),
            workspace_write_enabled=b("ZWORKFORCE_WORKSPACE_WRITE_ENABLED", True),
            max_request_bytes=i("ZWORKFORCE_MAX_REQUEST_BYTES", 1048576, 1024),
            api_rate_limit_per_minute=i("ZWORKFORCE_API_RATE_LIMIT_PER_MINUTE", 240, 1),
            cors_origins=csv("ZWORKFORCE_CORS_ORIGINS"),
            trust_proxy_identity=trust_proxy,
            proxy_identity_secret=proxy_secret,
            global_daily_budget_credits=max(0.0, f("ZWORKFORCE_GLOBAL_DAILY_BUDGET_CREDITS", 0)),
            provider_circuit_failures=i("ZWORKFORCE_PROVIDER_CIRCUIT_FAILURES", 3, 1),
            provider_circuit_seconds=i("ZWORKFORCE_PROVIDER_CIRCUIT_SECONDS", 30, 1),
            skill_signing_key=skill_key,
            doom_loop_max_identical_calls=i("ZWORKFORCE_DOOM_LOOP_MAX_IDENTICAL_CALLS", 3, 1),
            doom_loop_max_consecutive_failures=i("ZWORKFORCE_DOOM_LOOP_MAX_CONSECUTIVE_FAILURES", 5, 1),
            rates=rates,
        )


def _slug(value: str, label: str) -> str:
    value = value.strip().lower()
    if not value or len(value) > 63 or not value[0].isalnum() or any(c not in "abcdefghijklmnopqrstuvwxyz0123456789-" for c in value):
        raise ValueError(f"invalid {label} slug: {value!r}")
    return value


def _providers_from_env(env: str) -> tuple[ProviderConfig, ...]:
    raw = os.getenv("ZWORKFORCE_PROVIDERS_JSON", "").strip()
    if raw:
        try:
            items = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ValueError("ZWORKFORCE_PROVIDERS_JSON must be valid JSON") from exc
        if not isinstance(items, list) or not items:
            raise ValueError("ZWORKFORCE_PROVIDERS_JSON must be a non-empty array")
        providers: list[ProviderConfig] = []
        seen: set[str] = set()
        for idx, item in enumerate(items):
            if not isinstance(item, dict):
                raise ValueError("each provider must be an object")
            name = _slug(str(item.get("name") or f"provider-{idx+1}"), "provider")
            if name in seen:
                raise ValueError(f"duplicate provider name: {name}")
            seen.add(name)
            kind = str(item.get("kind", "openai-compatible")).strip().lower()
            if kind not in {"mock", "openai-compatible", "zworkforce-local", "zworkforce-native"}:
                raise ValueError(f"unsupported provider kind: {kind}")
            if env == "production" and kind == "mock":
                raise ValueError("mock providers are not allowed in production")
            models = item.get("models") or {}
            if not isinstance(models, dict):
                raise ValueError(f"provider {name} models must be an object")
            models = {tier: str(models.get(tier, "")) for tier in ("luna", "terra", "sol")}
            api_key = str(item.get("api_key") or "")
            api_key_env = str(item.get("api_key_env") or "")
            if api_key_env:
                api_key = os.getenv(api_key_env, "")
            base_url = str(item.get("base_url") or "").rstrip("/")
            if kind == "openai-compatible" and (not base_url or not any(models.values())):
                raise ValueError(f"provider {name} requires base_url and at least one model")
            if kind in {"zworkforce-local", "zworkforce-native"} and not any(models.values()):
                models = {"luna": "deepseek/deepseek-v4-flash", "terra": "openai/gpt-5.6-luna", "sol": "deepseek/deepseek-v4-pro"}
            if env == "production" and kind == "openai-compatible" and not api_key:
                raise ValueError(f"provider {name} API key is missing in production")
            providers.append(ProviderConfig(
                name=name,
                kind=kind,
                base_url=base_url,
                api_key=api_key,
                priority=int(item.get("priority", 100 + idx)),
                timeout_seconds=max(1, int(item.get("timeout_seconds", 90))),
                retries=max(1, int(item.get("retries", 2))),
                models=models,
                enabled=bool(item.get("enabled", True)),
            ))
        return tuple(sorted(providers, key=lambda p: p.priority))

    legacy_kind = os.getenv("ZWORKFORCE_PROVIDER", "mock").strip().lower()
    if legacy_kind == "mock":
        if env == "production":
            raise ValueError("mock providers are not allowed in production")
        return (ProviderConfig(name="mock", kind="mock", priority=100, models={"luna": "mock-luna", "terra": "mock-terra", "sol": "mock-sol"}),)
    if legacy_kind != "openai-compatible":
        raise ValueError("ZWORKFORCE_PROVIDER must be mock or openai-compatible")
    key = os.getenv("ZWORKFORCE_PROVIDER_API_KEY", "")
    if env == "production" and not key:
        raise ValueError("ZWORKFORCE_PROVIDER_API_KEY is required in production")
    return (ProviderConfig(
        name="primary",
        kind="openai-compatible",
        base_url=os.getenv("ZWORKFORCE_PROVIDER_BASE_URL", "https://api.openai.com/v1").rstrip("/"),
        api_key=key,
        priority=100,
        models={
            "sol": os.getenv("ZWORKFORCE_MODEL_SOL", "gpt-5.6"),
            "terra": os.getenv("ZWORKFORCE_MODEL_TERRA", "gpt-5.6-terra"),
            "luna": os.getenv("ZWORKFORCE_MODEL_LUNA", "gpt-5.6-luna"),
        },
    ),)


def _keys_from_env(env: str, default_tenant: str) -> tuple[BootstrapKey, ...]:
    raw = os.getenv("ZWORKFORCE_API_KEYS", "").strip()
    if not raw:
        if env == "production":
            raise ValueError("ZWORKFORCE_API_KEYS is required in production")
        return (
            BootstrapKey("dev-admin", "superadmin", default_tenant, "dev-admin"),
            BootstrapKey("dev-operator", "operator", default_tenant, "dev-operator"),
            BootstrapKey("dev-viewer", "viewer", default_tenant, "dev-viewer"),
        )
    keys: list[BootstrapKey] = []
    allowed_roles = {"viewer", "operator", "admin", "superadmin"}
    for idx, entry in enumerate(raw.split(","), 1):
        parts = entry.split(":")
        if len(parts) < 2 or len(parts) > 5:
            raise ValueError("ZWORKFORCE_API_KEYS entries must use secret:role[:tenant[:name[:scope1|scope2]]]")
        secret, role = parts[0].strip(), parts[1].strip().lower()
        if not secret or role not in allowed_roles:
            raise ValueError("invalid bootstrap API key entry")
        tenant = _slug(parts[2] if len(parts) >= 3 and parts[2] else default_tenant, "tenant")
        name = parts[3].strip() if len(parts) >= 4 and parts[3] else f"bootstrap-{idx}"
        scopes = tuple(s for s in (parts[4].split("|") if len(parts) >= 5 and parts[4] else ["*"]) if s)
        if env == "production" and len(secret) < 24:
            raise ValueError(f"production API key {name!r} must be at least 24 characters")
        keys.append(BootstrapKey(secret, role, tenant, name, scopes))
    return tuple(keys)
