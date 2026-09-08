"""Centralized runtime configuration for the zcoder API service."""

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

APP_NAME = "zcoder"
APP_VERSION = "1.33.0"
DEFAULT_API_PORT = 8000


def _env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


@dataclass
class Config:
    """Application configuration loaded from environment variables."""

    app_name: str = APP_NAME
    version: str = APP_VERSION
    debug: bool = False
    environment: str = "production"

    api_host: str = "127.0.0.1"
    api_port: int = DEFAULT_API_PORT
    api_workers: int = 1
    api_timeout: int = 30
    strict_readiness: bool = False

    ai_provider: str = "anthropic"
    litellm_config_path: Path = field(
        default_factory=lambda: Path("./litellm-config.yaml")
    )
    litellm_model: str = "zc-default"
    litellm_timeout_seconds: int = 120

    protobuf_enabled: bool = True
    max_message_size: int = 100 * 1024 * 1024

    redis_url: str = "redis://localhost:6379"
    redis_pool_size: int = 10
    redis_ttl_default: int = 3600
    redis_enabled: bool = False

    database_url: Optional[str] = None
    db_pool_size: int = 20
    db_max_overflow: int = 10

    upload_chunk_size: int = 4 * 1024 * 1024
    upload_max_size: int = 50 * 1024 * 1024 * 1024
    upload_temp_dir: Path = field(default_factory=lambda: Path("./data/uploads"))
    chat_session_dir: Path = field(
        default_factory=lambda: Path("./data/chat/sessions")
    )
    storage_backend: str = "local"
    storage_s3_bucket: str = "wire-uploads"
    storage_s3_endpoint: Optional[str] = None
    storage_s3_access_key: Optional[str] = None
    storage_s3_secret_key: Optional[str] = None
    storage_s3_region: str = "us-east-1"

    nats_url: str = "nats://localhost:4222"
    nats_cluster: list[str] = field(default_factory=list)
    nats_enabled: bool = False

    jwt_secret: Optional[str] = None
    jwt_algorithm: str = "HS256"
    jwt_expiry_seconds: int = 3600
    auth_required: bool = True
    mtls_enabled: bool = False
    mtls_ca_cert: Optional[Path] = None
    encryption_key: Optional[str] = None
    cors_origins: list[str] = field(default_factory=list)

    rate_limit_enabled: bool = False
    rate_limit_requests: int = 1000
    rate_limit_window: int = 60

    otel_enabled: bool = False
    otel_exporter_endpoint: str = "http://otel-collector:4317"
    otel_service_name: str = "zcoder-api"
    otel_tracing_sample_rate: float = 0.1
    prometheus_metrics_enabled: bool = False
    prometheus_port: int = 9090

    control_panel_enabled: bool = True
    frontend_enabled: bool = True
    control_panel_admin_users: list[str] = field(default_factory=list)
    feature_flags: dict[str, bool] = field(default_factory=dict)

    http3_enabled: bool = False
    http3_port: int = 8443
    quic_certificate: Optional[Path] = None
    quic_private_key: Optional[Path] = None

    kubernetes_enabled: bool = False
    cilium_ebpf_enabled: bool = False

    @classmethod
    def from_env(cls) -> "Config":
        """Load configuration from environment variables."""
        return cls(
            app_name=os.getenv("APP_NAME", APP_NAME),
            version=os.getenv("APP_VERSION", APP_VERSION),
            debug=_env_bool("DEBUG", False),
            environment=os.getenv("ENVIRONMENT", "production"),
            api_host=os.getenv("API_HOST", "127.0.0.1"),
            api_port=int(os.getenv("API_PORT", str(DEFAULT_API_PORT))),
            api_workers=int(os.getenv("API_WORKERS", "1")),
            api_timeout=int(os.getenv("API_TIMEOUT", "30")),
            strict_readiness=_env_bool("STRICT_READINESS", False),
            ai_provider=os.getenv("AI_PROVIDER", "anthropic").strip().lower(),
            litellm_config_path=Path(
                os.getenv("LITELLM_CONFIG_PATH", "./litellm-config.yaml")
            ),
            litellm_model=os.getenv("LITELLM_MODEL", "zc-default"),
            litellm_timeout_seconds=int(os.getenv("LITELLM_TIMEOUT_SECONDS", "120")),
            protobuf_enabled=_env_bool("PROTOBUF_ENABLED", True),
            max_message_size=int(os.getenv("MAX_MESSAGE_SIZE", "104857600")),
            redis_url=os.getenv("REDIS_URL", "redis://localhost:6379"),
            redis_pool_size=int(os.getenv("REDIS_POOL_SIZE", "10")),
            redis_ttl_default=int(os.getenv("REDIS_TTL_DEFAULT", "3600")),
            redis_enabled=_env_bool("REDIS_ENABLED", False),
            database_url=os.getenv("DATABASE_URL"),
            db_pool_size=int(os.getenv("DB_POOL_SIZE", "20")),
            db_max_overflow=int(os.getenv("DB_MAX_OVERFLOW", "10")),
            upload_chunk_size=int(os.getenv("UPLOAD_CHUNK_SIZE", "4194304")),
            upload_max_size=int(os.getenv("UPLOAD_MAX_SIZE", "53687091200")),
            upload_temp_dir=Path(os.getenv("UPLOAD_TEMP_DIR", "./data/uploads")),
            chat_session_dir=Path(
                os.getenv("CHAT_SESSION_DIR", "./data/chat/sessions")
            ),
            storage_backend=os.getenv("STORAGE_BACKEND", "local"),
            storage_s3_bucket=os.getenv("STORAGE_S3_BUCKET", "wire-uploads"),
            storage_s3_endpoint=os.getenv("STORAGE_S3_ENDPOINT"),
            storage_s3_access_key=os.getenv("STORAGE_S3_ACCESS_KEY"),
            storage_s3_secret_key=os.getenv("STORAGE_S3_SECRET_KEY"),
            storage_s3_region=os.getenv("STORAGE_S3_REGION", "us-east-1"),
            nats_url=os.getenv("NATS_URL", "nats://localhost:4222"),
            nats_cluster=(
                os.getenv("NATS_CLUSTER", "").split(",")
                if os.getenv("NATS_CLUSTER")
                else []
            ),
            nats_enabled=_env_bool("NATS_ENABLED", False),
            jwt_secret=os.getenv("JWT_SECRET"),
            jwt_algorithm=os.getenv("JWT_ALGORITHM", "HS256"),
            jwt_expiry_seconds=int(os.getenv("JWT_EXPIRY_SECONDS", "3600")),
            auth_required=_env_bool("AUTH_REQUIRED", True),
            mtls_enabled=_env_bool("MTLS_ENABLED", False),
            mtls_ca_cert=(
                Path(os.environ["MTLS_CA_CERT"]) if os.getenv("MTLS_CA_CERT") else None
            ),
            encryption_key=os.getenv("ENCRYPTION_KEY"),
            cors_origins=[
                origin.strip()
                for origin in os.getenv("CORS_ORIGINS", "").split(",")
                if origin.strip()
            ],
            rate_limit_enabled=_env_bool("RATE_LIMIT_ENABLED", False),
            rate_limit_requests=int(os.getenv("RATE_LIMIT_REQUESTS", "1000")),
            rate_limit_window=int(os.getenv("RATE_LIMIT_WINDOW", "60")),
            otel_enabled=_env_bool("OTEL_ENABLED", False),
            otel_exporter_endpoint=os.getenv(
                "OTEL_EXPORTER_ENDPOINT", "http://otel-collector:4317"
            ),
            otel_service_name=os.getenv("OTEL_SERVICE_NAME", "zcoder-api"),
            otel_tracing_sample_rate=float(
                os.getenv("OTEL_TRACING_SAMPLE_RATE", "0.1")
            ),
            prometheus_metrics_enabled=_env_bool(
                "PROMETHEUS_METRICS_ENABLED", False
            ),
            prometheus_port=int(os.getenv("PROMETHEUS_PORT", "9090")),
            control_panel_enabled=_env_bool("CONTROL_PANEL_ENABLED", True),
            frontend_enabled=_env_bool("FRONTEND_ENABLED", True),
            control_panel_admin_users=(
                os.getenv("CONTROL_PANEL_ADMIN_USERS", "").split(",")
                if os.getenv("CONTROL_PANEL_ADMIN_USERS")
                else []
            ),
            http3_enabled=_env_bool("HTTP3_ENABLED", False),
            http3_port=int(os.getenv("HTTP3_PORT", "8443")),
            quic_certificate=(
                Path(os.environ["QUIC_CERTIFICATE"])
                if os.getenv("QUIC_CERTIFICATE")
                else None
            ),
            quic_private_key=(
                Path(os.environ["QUIC_PRIVATE_KEY"])
                if os.getenv("QUIC_PRIVATE_KEY")
                else None
            ),
            kubernetes_enabled=_env_bool("KUBERNETES_ENABLED", False),
            cilium_ebpf_enabled=_env_bool("CILIUM_EBPF_ENABLED", False),
        )

    def ensure_dirs(self) -> None:
        self.upload_temp_dir.mkdir(parents=True, exist_ok=True)
        self.chat_session_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
        os.chmod(self.chat_session_dir, 0o700)

    def validate(self) -> None:
        """Fail closed when production security invariants are not configured."""
        if self.environment == "production" and self.auth_required and not self.jwt_secret:
            raise RuntimeError("JWT_SECRET is required when production authentication is enabled")
        if self.ai_provider not in {"anthropic", "litellm"}:
            raise RuntimeError("AI_PROVIDER must be 'anthropic' or 'litellm'")
        if self.litellm_timeout_seconds <= 0:
            raise RuntimeError("LITELLM_TIMEOUT_SECONDS must be positive")
        if self.ai_provider == "litellm":
            if not self.litellm_model:
                raise RuntimeError("LITELLM_MODEL must not be empty")
            if not self.litellm_config_path.is_file():
                raise RuntimeError(
                    f"LiteLLM config not found: {self.litellm_config_path}"
                )
        if self.upload_chunk_size <= 0 or self.upload_chunk_size > self.max_message_size:
            raise RuntimeError("UPLOAD_CHUNK_SIZE must be within MAX_MESSAGE_SIZE")
        if self.upload_max_size < self.upload_chunk_size:
            raise RuntimeError("UPLOAD_MAX_SIZE must be at least UPLOAD_CHUNK_SIZE")
        if self.rate_limit_enabled and not self.redis_enabled and self.api_workers != 1:
            raise RuntimeError(
                "API_WORKERS must be 1 when rate limiting uses in-memory state"
            )


_config: Optional[Config] = None


def get_config() -> Config:
    global _config
    if _config is None:
        _config = Config.from_env()
        _config.ensure_dirs()
    return _config


def reload_config() -> Config:
    global _config
    _config = Config.from_env()
    _config.ensure_dirs()
    return _config
