from __future__ import annotations

from dataclasses import dataclass
import datetime
import json
import os
import socket
import urllib.error
import urllib.parse
import urllib.request
from typing import Any


@dataclass(frozen=True)
class ZarvisVoiceConfig:
    enabled: bool
    gateway_url: str
    service_token: str
    websocket_allowlist: tuple[str, ...]
    model: str
    timeout_seconds: float


class ZarvisVoiceError(RuntimeError):
    def __init__(self, message: str, *, status: int = 502, code: str = "voice_unavailable") -> None:
        super().__init__(message)
        self.status = status
        self.code = code


def _bool_env(name: str, default: bool = False) -> bool:
    return os.getenv(name, str(default)).strip().lower() in {"1", "true", "yes", "on"}


def _origin(value: str, *, schemes: set[str]) -> str:
    parsed = urllib.parse.urlsplit(value.strip())
    if parsed.scheme not in schemes or not parsed.hostname or parsed.username or parsed.password:
        raise ValueError(f"invalid URL: {value!r}")
    port = f":{parsed.port}" if parsed.port else ""
    return f"{parsed.scheme}://{parsed.hostname}{port}"


def _gateway_url(value: str) -> str:
    if not value:
        return ""
    parsed = urllib.parse.urlsplit(value.strip())
    if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username or parsed.password:
        raise ValueError("ZWORKFORCE_ZARVIS_VOICE_GATEWAY_URL must be an http(s) URL without credentials")
    if parsed.query or parsed.fragment:
        raise ValueError("ZWORKFORCE_ZARVIS_VOICE_GATEWAY_URL must not contain query or fragment components")
    return value.strip().rstrip("/")


def load_voice_config() -> ZarvisVoiceConfig:
    gateway = _gateway_url(
        os.getenv("ZWORKFORCE_ZARVIS_VOICE_GATEWAY_URL", "").strip()
        or os.getenv("Z_PLATFORM_VOICE_GATEWAY_URL", "").strip()
    )
    token = (
        os.getenv("ZWORKFORCE_ZARVIS_VOICE_SERVICE_TOKEN", "").strip()
        or os.getenv("Z_PLATFORM_SERVICE_TOKEN", "").strip()
    )
    raw_allowlist = os.getenv("ZWORKFORCE_ZARVIS_VOICE_WS_ALLOWLIST", "").strip()
    allowlist: list[str] = []
    for raw in raw_allowlist.split(",") if raw_allowlist else ():
        value = _origin(raw, schemes={"ws", "wss"})
        if value not in allowlist:
            allowlist.append(value)
    timeout = float(os.getenv("ZWORKFORCE_ZARVIS_VOICE_TIMEOUT_SECONDS", "5"))
    if not 0.25 <= timeout <= 30:
        raise ValueError("ZWORKFORCE_ZARVIS_VOICE_TIMEOUT_SECONDS must be between 0.25 and 30")
    model = os.getenv("ZWORKFORCE_ZARVIS_VOICE_MODEL", "default").strip() or "default"
    if len(model) > 256:
        raise ValueError("ZWORKFORCE_ZARVIS_VOICE_MODEL must be <= 256 characters")
    return ZarvisVoiceConfig(
        enabled=_bool_env("ZWORKFORCE_ZARVIS_VOICE_ENABLED"),
        gateway_url=gateway,
        service_token=token,
        websocket_allowlist=tuple(allowlist),
        model=model,
        timeout_seconds=timeout,
    )


class ZarvisVoiceService:
    def __init__(self, config: ZarvisVoiceConfig | None = None, *, opener: Any = None) -> None:
        self.config = config or load_voice_config()
        self._opener = opener or urllib.request.urlopen
        if self.config.enabled and not self.config.gateway_url:
            raise ValueError("Z.A.R.V.I.S. voice is enabled but the voice gateway URL is missing")
        if self.config.enabled and not self.config.service_token:
            raise ValueError("Z.A.R.V.I.S. voice is enabled but the voice service token is missing")
        if self.config.enabled and os.getenv("ZWORKFORCE_ENV", "development").strip().lower() == "production" and not self.config.websocket_allowlist:
            raise ValueError("ZWORKFORCE_ZARVIS_VOICE_WS_ALLOWLIST is required in production when voice is enabled")

    @property
    def csp_connect_sources(self) -> tuple[str, ...]:
        return self.config.websocket_allowlist if self.config.enabled else ()

    @property
    def microphone_enabled(self) -> bool:
        return self.config.enabled

    def snapshot(self) -> dict[str, Any]:
        return {
            "enabled": self.config.enabled,
            "configured": bool(self.config.gateway_url and self.config.service_token),
            "model": self.config.model if self.config.enabled else None,
            "websocket_origins": list(self.config.websocket_allowlist),
            "transport": "realtime-pcm16" if self.config.enabled else None,
        }

    def issue_session(self, *, tenant_id: str, subject_id: str, request_id: str, model: str | None = None) -> dict[str, Any]:
        if not self.config.enabled:
            raise ZarvisVoiceError("Z.A.R.V.I.S. voice is disabled", status=503, code="voice_disabled")
        if not self.config.gateway_url or not self.config.service_token:
            raise ZarvisVoiceError("Z.A.R.V.I.S. voice is not configured", status=503, code="voice_not_configured")

        selected_model = (model or self.config.model).strip()
        if not selected_model or len(selected_model) > 256:
            raise ZarvisVoiceError("invalid voice model", status=400, code="invalid_voice_model")
        body = json.dumps({"model": selected_model}, separators=(",", ":")).encode("utf-8")
        request = urllib.request.Request(
            f"{self.config.gateway_url}/v1/voice/tickets",
            data=body,
            headers={
                "Authorization": f"Bearer {self.config.service_token}",
                "Content-Type": "application/json",
                "Accept": "application/json",
                "X-Tenant-Id": tenant_id,
                "X-Subject-Id": subject_id,
                "X-Request-Id": request_id,
            },
            method="POST",
        )
        try:
            with self._opener(request, timeout=self.config.timeout_seconds) as response:
                raw = response.read(64 * 1024 + 1)
                if len(raw) > 64 * 1024:
                    raise ZarvisVoiceError("voice gateway response is too large", code="voice_gateway_invalid_response")
        except urllib.error.HTTPError as exc:
            status = 503 if exc.code in {429, 503} else 502
            raise ZarvisVoiceError("voice gateway rejected the session request", status=status, code="voice_gateway_rejected") from exc
        except (urllib.error.URLError, TimeoutError, socket.timeout, OSError) as exc:
            raise ZarvisVoiceError("voice gateway is unavailable", status=503, code="voice_gateway_unavailable") from exc

        try:
            payload = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ZarvisVoiceError("voice gateway returned invalid JSON", code="voice_gateway_invalid_response") from exc
        if not isinstance(payload, dict):
            raise ZarvisVoiceError("voice gateway returned an invalid response", code="voice_gateway_invalid_response")

        ticket = payload.get("ticket")
        expires_at = payload.get("expires_at")
        websocket_url = payload.get("websocket_url")
        if self.config.service_token and self.config.service_token in json.dumps(payload):
            raise ZarvisVoiceError("voice gateway echoed the service token", code="voice_gateway_invalid_response")

        if not isinstance(ticket, str) or not ticket or len(ticket) > 4096:
            raise ZarvisVoiceError("voice gateway returned an invalid ticket", code="voice_gateway_invalid_response")
        if not isinstance(expires_at, str) or not expires_at or len(expires_at) > 128:
            raise ZarvisVoiceError("voice gateway returned an invalid expiry", code="voice_gateway_invalid_response")
        if not isinstance(websocket_url, str) or len(websocket_url) > 2048:
            raise ZarvisVoiceError("voice gateway returned an invalid WebSocket URL", code="voice_gateway_invalid_response")

        try:
            websocket_origin = _origin(websocket_url, schemes={"ws", "wss"})
        except ValueError as exc:
            raise ZarvisVoiceError("voice gateway returned an invalid WebSocket URL", code="voice_gateway_invalid_response") from exc
        if self.config.websocket_allowlist and websocket_origin not in self.config.websocket_allowlist:
            raise ZarvisVoiceError("voice gateway WebSocket origin is not allowlisted", status=502, code="voice_websocket_origin_denied")

        return {
            "ticket": ticket,
            "expires_at": expires_at,
            "websocket_url": websocket_url,
            "ticket_transport": "sec-websocket-protocol",
            "model": selected_model,
            "transport": "realtime-pcm16",
        }


@dataclass(frozen=True)
class ZarvisLiveConfig:
    enabled: bool
    api_key: str
    model: str
    voice: str
    thinking_level: str
    system_prompt: str
    token_ttl_minutes: int
    connect_window_minutes: int
    websocket_origin: str


def load_live_config() -> ZarvisLiveConfig:
    enabled = _bool_env("ZWORKFORCE_ZARVIS_LIVE_ENABLED")
    api_key = os.getenv("ZWORKFORCE_GEMINI_API_KEY", "").strip()
    if enabled and not api_key:
        raise ValueError("ZWORKFORCE_GEMINI_API_KEY is required when Z.A.R.V.I.S. Live is enabled")
    if enabled and len(api_key) < 20:
        raise ValueError("ZWORKFORCE_GEMINI_API_KEY must be at least 20 characters")
    
    model = os.getenv("ZWORKFORCE_ZARVIS_LIVE_MODEL", "gemini-3.1-flash-live-preview").strip()
    voice = os.getenv("ZWORKFORCE_ZARVIS_LIVE_VOICE", "Charon").strip()
    if len(voice) > 64:
        raise ValueError("ZWORKFORCE_ZARVIS_LIVE_VOICE must be <= 64 characters")
    
    thinking_level = os.getenv("ZWORKFORCE_ZARVIS_LIVE_THINKING", "minimal").strip()
    if thinking_level not in {"minimal", "low", "medium", "high"}:
        raise ValueError("ZWORKFORCE_ZARVIS_LIVE_THINKING must be one of: minimal, low, medium, high")
    
    system_prompt = os.getenv("ZWORKFORCE_ZARVIS_LIVE_SYSTEM_PROMPT", "You are Z.A.R.V.I.S., a direct and highly capable AI workforce assistant. Reply concisely in the user's language. Never claim that spoken text approves a mutating action.").strip()
    if len(system_prompt) > 8000:
        raise ValueError("ZWORKFORCE_ZARVIS_LIVE_SYSTEM_PROMPT must be <= 8000 characters")
    
    try:
        token_ttl_minutes = int(os.getenv("ZWORKFORCE_ZARVIS_LIVE_TOKEN_TTL_MINUTES", "30").strip())
    except ValueError:
        raise ValueError("ZWORKFORCE_ZARVIS_LIVE_TOKEN_TTL_MINUTES must be an integer")
    if not 5 <= token_ttl_minutes <= 120:
        raise ValueError("ZWORKFORCE_ZARVIS_LIVE_TOKEN_TTL_MINUTES must be between 5 and 120")
    
    try:
        connect_window_minutes = int(os.getenv("ZWORKFORCE_ZARVIS_LIVE_CONNECT_WINDOW_MINUTES", "1").strip())
    except ValueError:
        raise ValueError("ZWORKFORCE_ZARVIS_LIVE_CONNECT_WINDOW_MINUTES must be an integer")
    if not 1 <= connect_window_minutes <= 5:
        raise ValueError("ZWORKFORCE_ZARVIS_LIVE_CONNECT_WINDOW_MINUTES must be between 1 and 5")
    
    websocket_origin = "wss://generativelanguage.googleapis.com"
    
    return ZarvisLiveConfig(
        enabled=enabled,
        api_key=api_key,
        model=model,
        voice=voice,
        thinking_level=thinking_level,
        system_prompt=system_prompt,
        token_ttl_minutes=token_ttl_minutes,
        connect_window_minutes=connect_window_minutes,
        websocket_origin=websocket_origin,
    )


class ZarvisLiveVoiceService:
    def __init__(self, config: ZarvisLiveConfig | None = None, *, opener: Any = None) -> None:
        self.config = config or load_live_config()
        self._opener = opener or urllib.request.urlopen

    @property
    def csp_connect_sources(self) -> tuple[str, ...]:
        if not self.config.enabled:
            return ()
        return (self.config.websocket_origin,)

    def snapshot(self) -> dict[str, Any]:
        return {
            "live_enabled": self.config.enabled,
            "live_model": self.config.model if self.config.enabled else None,
            "live_voice": self.config.voice if self.config.enabled else None,
            "live_transport": "gemini-live" if self.config.enabled else None,
            "live_websocket_origin": self.config.websocket_origin if self.config.enabled else None,
        }

    def issue_live_token(self, *, tenant_id: str, subject_id: str, request_id: str) -> dict[str, Any]:
        """Generate a Gemini ephemeral token for browser Live API sessions.
        
        Uses Google's auth_tokens.create() API endpoint to issue a single-use
        ephemeral token. The master API key never leaves the server.
        """
        if not self.config.enabled:
            raise ZarvisVoiceError("Z.A.R.V.I.S. Live voice is disabled", status=503, code="live_voice_disabled")
        if not self.config.api_key:
            raise ZarvisVoiceError("Z.A.R.V.I.S. Live voice is not configured", status=503, code="live_voice_not_configured")

        now = datetime.datetime.now(tz=datetime.timezone.utc)
        expire_time = now + datetime.timedelta(minutes=self.config.token_ttl_minutes)
        connect_window = now + datetime.timedelta(minutes=self.config.connect_window_minutes)

        token_request_body = json.dumps({
            "config": {
                "uses": 1,
                "expire_time": expire_time.isoformat(),
                "new_session_expire_time": connect_window.isoformat(),
            }
        }, separators=(",", ":")).encode("utf-8")

        api_url = f"https://generativelanguage.googleapis.com/v1alpha/auth_tokens?key={self.config.api_key}"
        request = urllib.request.Request(
            api_url,
            data=token_request_body,
            headers={
                "Content-Type": "application/json",
                "Accept": "application/json",
                "X-Request-Id": request_id,
            },
            method="POST",
        )

        try:
            with self._opener(request, timeout=5.0) as response:
                raw = response.read(16 * 1024 + 1)
                if len(raw) > 16 * 1024:
                    raise ZarvisVoiceError("Gemini token response is too large", code="live_token_invalid_response")
        except urllib.error.HTTPError as exc:
            status = 503 if exc.code in {429, 503} else 502
            raise ZarvisVoiceError("Gemini token API rejected the request", status=status, code="live_token_rejected") from exc
        except (urllib.error.URLError, TimeoutError, socket.timeout, OSError) as exc:
            raise ZarvisVoiceError("Gemini token API is unavailable", status=503, code="live_token_unavailable") from exc

        try:
            payload = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ZarvisVoiceError("Gemini token API returned invalid JSON", code="live_token_invalid_response") from exc

        if not isinstance(payload, dict):
            raise ZarvisVoiceError("Gemini token API returned an invalid response", code="live_token_invalid_response")

        token_name = payload.get("name")
        if not isinstance(token_name, str) or not token_name.startswith("auth_tokens/"):
            raise ZarvisVoiceError("Gemini token API returned an invalid token", code="live_token_invalid_response")

        if self.config.api_key and self.config.api_key in json.dumps(payload):
            raise ZarvisVoiceError("Gemini token response echoed the API key", code="live_token_invalid_response")

        return {
            "token": token_name,
            "expires_at": expire_time.isoformat(),
            "model": self.config.model,
            "voice": self.config.voice,
            "thinking_level": self.config.thinking_level,
            "system_prompt": self.config.system_prompt,
            "websocket_origin": self.config.websocket_origin,
            "transport": "gemini-live",
        }


def build_zarvis_voice_services() -> tuple[ZarvisVoiceService, ZarvisLiveVoiceService]:
    return ZarvisVoiceService(), ZarvisLiveVoiceService()


def build_zarvis_voice_service() -> ZarvisVoiceService:
    return ZarvisVoiceService()
