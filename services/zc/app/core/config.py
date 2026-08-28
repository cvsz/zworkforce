"""
app/core/config.py - Enterprise configuration management

Centralized configuration with environment variable support,
secrets management, and runtime feature flags.
"""
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


@dataclass
class Config:
    """Enterprise-grade configuration with 2026 standards."""
    
    # Application
    app_name: str = "wire-enterprise"
    version: str = "2.0.0"
    debug: bool = False
    environment: str = "production"  # development, staging, production
    
    # API Settings
    api_host: str = "0.0.0.0"
    api_port: int = 8420
    api_workers: int = 4
    api_timeout: int = 30
    
    # Protocol Buffers
    protobuf_enabled: bool = True
    max_message_size: int = 100 * 1024 * 1024  # 100MB
    
    # Redis/Valkey Cache
    redis_url: str = "redis://localhost:6379"
    redis_pool_size: int = 10
    redis_ttl_default: int = 3600
    redis_enabled: bool = True
    
    # Database (optional for enterprise features)
    database_url: Optional[str] = None
    db_pool_size: int = 20
    db_max_overflow: int = 10
    
    # File Upload
    upload_chunk_size: int = 4 * 1024 * 1024  # 4MB
    upload_max_size: int = 50 * 1024 * 1024 * 1024  # 50GB
    upload_temp_dir: Path = field(default_factory=lambda: Path("/tmp/uploads"))
    storage_backend: str = "s3"  # local, s3, minio
    storage_s3_bucket: str = "wire-uploads"
    storage_s3_endpoint: Optional[str] = None  # None for AWS, URL for MinIO
    storage_s3_access_key: Optional[str] = None
    storage_s3_secret_key: Optional[str] = None
    storage_s3_region: str = "us-east-1"
    
    # NATS Message Queue
    nats_url: str = "nats://localhost:4222"
    nats_cluster: list[str] = field(default_factory=list)
    nats_enabled: bool = True
    
    # Security
    jwt_secret: Optional[str] = None
    service_token: Optional[str] = None
    jwt_algorithm: str = "HS256"
    jwt_expiry_seconds: int = 3600
    mtls_enabled: bool = False
    mtls_ca_cert: Optional[Path] = None
    encryption_key: Optional[str] = None
    
    # Rate Limiting
    rate_limit_enabled: bool = True
    rate_limit_requests: int = 1000
    rate_limit_window: int = 60  # seconds
    
    # Observability
    otel_enabled: bool = True
    otel_exporter_endpoint: str = "http://otel-collector:4317"
    otel_service_name: str = "wire-api"
    otel_tracing_sample_rate: float = 0.1
    prometheus_metrics_enabled: bool = True
    prometheus_port: int = 9090
    
    # Control Panel
    control_panel_enabled: bool = True
    control_panel_admin_users: list[str] = field(default_factory=list)
    feature_flags: dict[str, bool] = field(default_factory=dict)
    
    # HTTP/3 (QUIC)
    http3_enabled: bool = False
    http3_port: int = 8443
    quic_certificate: Optional[Path] = None
    quic_private_key: Optional[Path] = None
    
    # Kubernetes/Cilium
    kubernetes_enabled: bool = False
    cilium_ebpf_enabled: bool = False
    
    @classmethod
    def from_env(cls) -> "Config":
        """Load configuration from environment variables."""
        return cls(
            app_name=os.getenv("APP_NAME", "wire-enterprise"),
            version=os.getenv("APP_VERSION", "2.0.0"),
            debug=os.getenv("DEBUG", "false").lower() == "true",
            environment=os.getenv("ENVIRONMENT", "production"),
            
            api_host=os.getenv("API_HOST", "0.0.0.0"),
            api_port=int(os.getenv("API_PORT", "8420")),
            api_workers=int(os.getenv("API_WORKERS", "4")),
            api_timeout=int(os.getenv("API_TIMEOUT", "30")),
            
            protobuf_enabled=os.getenv("PROTOBUF_ENABLED", "true").lower() == "true",
            max_message_size=int(os.getenv("MAX_MESSAGE_SIZE", "104857600")),
            
            redis_url=os.getenv("REDIS_URL", "redis://localhost:6379"),
            redis_pool_size=int(os.getenv("REDIS_POOL_SIZE", "10")),
            redis_ttl_default=int(os.getenv("REDIS_TTL_DEFAULT", "3600")),
            redis_enabled=os.getenv("REDIS_ENABLED", "true").lower() == "true",
            
            database_url=os.getenv("DATABASE_URL"),
            db_pool_size=int(os.getenv("DB_POOL_SIZE", "20")),
            db_max_overflow=int(os.getenv("DB_MAX_OVERFLOW", "10")),
            
            upload_chunk_size=int(os.getenv("UPLOAD_CHUNK_SIZE", "4194304")),
            upload_max_size=int(os.getenv("UPLOAD_MAX_SIZE", "53687091200")),
            upload_temp_dir=Path(os.getenv("UPLOAD_TEMP_DIR", "/tmp/uploads")),
            storage_backend=os.getenv("STORAGE_BACKEND", "s3"),
            storage_s3_bucket=os.getenv("STORAGE_S3_BUCKET", "wire-uploads"),
            storage_s3_endpoint=os.getenv("STORAGE_S3_ENDPOINT"),
            storage_s3_access_key=os.getenv("STORAGE_S3_ACCESS_KEY"),
            storage_s3_secret_key=os.getenv("STORAGE_S3_SECRET_KEY"),
            storage_s3_region=os.getenv("STORAGE_S3_REGION", "us-east-1"),
            
            nats_url=os.getenv("NATS_URL", "nats://localhost:4222"),
            nats_cluster=os.getenv("NATS_CLUSTER", "").split(",") if os.getenv("NATS_CLUSTER") else [],
            nats_enabled=os.getenv("NATS_ENABLED", "true").lower() == "true",
            
            jwt_secret=os.getenv("JWT_SECRET"),
            service_token=os.getenv("ZC_API_TOKEN"),
            jwt_algorithm=os.getenv("JWT_ALGORITHM", "HS256"),
            jwt_expiry_seconds=int(os.getenv("JWT_EXPIRY_SECONDS", "3600")),
            mtls_enabled=os.getenv("MTLS_ENABLED", "false").lower() == "true",
            mtls_ca_cert=Path(str(os.getenv("MTLS_CA_CERT"))) if os.getenv("MTLS_CA_CERT") else None,
            encryption_key=os.getenv("ENCRYPTION_KEY"),
            
            rate_limit_enabled=os.getenv("RATE_LIMIT_ENABLED", "true").lower() == "true",
            rate_limit_requests=int(os.getenv("RATE_LIMIT_REQUESTS", "1000")),
            rate_limit_window=int(os.getenv("RATE_LIMIT_WINDOW", "60")),
            
            otel_enabled=os.getenv("OTEL_ENABLED", "true").lower() == "true",
            otel_exporter_endpoint=os.getenv("OTEL_EXPORTER_ENDPOINT", "http://otel-collector:4317"),
            otel_service_name=os.getenv("OTEL_SERVICE_NAME", "wire-api"),
            otel_tracing_sample_rate=float(os.getenv("OTEL_TRACING_SAMPLE_RATE", "0.1")),
            prometheus_metrics_enabled=os.getenv("PROMETHEUS_METRICS_ENABLED", "true").lower() == "true",
            prometheus_port=int(os.getenv("PROMETHEUS_PORT", "9090")),
            
            control_panel_enabled=os.getenv("CONTROL_PANEL_ENABLED", "true").lower() == "true",
            control_panel_admin_users=os.getenv("CONTROL_PANEL_ADMIN_USERS", "").split(",") if os.getenv("CONTROL_PANEL_ADMIN_USERS") else [],
            
            http3_enabled=os.getenv("HTTP3_ENABLED", "false").lower() == "true",
            http3_port=int(os.getenv("HTTP3_PORT", "8443")),
            quic_certificate=Path(str(os.getenv("QUIC_CERTIFICATE"))) if os.getenv("QUIC_CERTIFICATE") else None,
            quic_private_key=Path(str(os.getenv("QUIC_PRIVATE_KEY"))) if os.getenv("QUIC_PRIVATE_KEY") else None,
            
            kubernetes_enabled=os.getenv("KUBERNETES_ENABLED", "false").lower() == "true",
            cilium_ebpf_enabled=os.getenv("CILIUM_EBPF_ENABLED", "false").lower() == "true",
        )
    
    def ensure_dirs(self) -> None:
        """Ensure all required directories exist."""
        self.upload_temp_dir.mkdir(parents=True, exist_ok=True)


# Global config instance
_config: Optional[Config] = None


def get_config() -> Config:
    """Get or create the global configuration instance."""
    global _config
    if _config is None:
        _config = Config.from_env()
        _config.ensure_dirs()
    return _config


def reload_config() -> Config:
    """Reload configuration from environment (useful for testing)."""
    global _config
    _config = Config.from_env()
    _config.ensure_dirs()
    return _config
