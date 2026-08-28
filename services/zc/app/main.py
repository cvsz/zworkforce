"""
app/main.py - Enterprise FastAPI Application

Main entry point for the enterprise-grade wire API server.
Features:
- OpenTelemetry instrumentation
- Prometheus metrics endpoint
- Graceful shutdown handling
- CORS configuration
- Request/response logging
"""
import time
import hmac
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse

from .api.v1.routes import router as wire_router
from .core.cache import init_cache, shutdown_cache
from .core.config import get_config
from .core.http_client import init_http_client, shutdown_http_client
from .services.upload_manager import init_upload_manager
from typing import Optional


# Track request timing for metrics
@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator:
    """Application lifespan manager for startup/shutdown."""
    config = get_config()
    
    # Startup
    print(f"🚀 Starting wire-enterprise v{config.version}")
    print(f"   Environment: {config.environment}")
    print(f"   Redis: {'enabled' if config.redis_enabled else 'disabled'}")
    print(f"   Protobuf: {'enabled' if config.protobuf_enabled else 'disabled'}")
    
    try:
        await init_cache()
        print("✓ Cache initialized")
    except Exception as e:
        print(f"⚠ Cache initialization failed: {e}")
    
    try:
        await init_http_client()
        print("✓ HTTP client initialized")
    except Exception as e:
        print(f"⚠ HTTP client initialization failed: {e}")
    
    try:
        await init_upload_manager()
        print("✓ Upload manager initialized")
    except Exception as e:
        print(f"⚠ Upload manager initialization failed: {e}")
    
    if config.protobuf_enabled:
        try:
            from .grpc.wire_servicer import create_grpc_server
            from .services.upload_manager import get_upload_manager
            
            grpc_server = await create_grpc_server(
                host=config.api_host if hasattr(config, 'api_host') else "0.0.0.0",
                port=(config.api_port + 1) if hasattr(config, 'api_port') else 50051,
                upload_manager=get_upload_manager(),
                delta_service=None  # will use default in create_grpc_server
            )
            await grpc_server.start()
            print("✓ gRPC server started")
            app.state.grpc_server = grpc_server
        except Exception as e:
            print(f"⚠ gRPC server initialization failed: {e}")
    
    yield
    
    # Shutdown
    print("\n🛑 Shutting down wire-enterprise...")
    
    await shutdown_cache()
    print("✓ Cache shutdown complete")
    
    await shutdown_http_client()
    print("✓ HTTP client shutdown complete")
    
    if hasattr(app.state, 'grpc_server'):
        await app.state.grpc_server.stop(grace=5.0)
        print("✓ gRPC server shutdown complete")


# Create FastAPI application
config = get_config()

app = FastAPI(
    title=config.app_name,
    version=config.version,
    description="Enterprise-grade wire CLI-to-API backend with optimized file uploads",
    docs_url="/docs" if config.debug else None,
    redoc_url="/redoc" if config.debug else None,
    openapi_url="/openapi.json" if config.debug else None,
    lifespan=lifespan,
)

# Add middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if config.debug else ["http://localhost:*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(GZipMiddleware, minimum_size=1000)


@app.middleware("http")
async def add_timing_header(request: Request, call_next) -> Response:
    """Add X-Process-Time header to all responses."""
    start_time = time.perf_counter()
    response = await call_next(request)
    process_time = (time.perf_counter() - start_time) * 1000
    response.headers["X-Process-Time"] = f"{process_time:.2f}ms"
    return response


@app.middleware("http")
async def require_service_auth(request: Request, call_next) -> Response:
    """Protect wire operations while keeping orchestration probes public."""
    config = get_config()
    protected = request.url.path.startswith("/v1/wire/") and not request.url.path.startswith("/v1/wire/health/")
    if protected and config.service_token:
        authorization = request.headers.get("authorization", "")
        supplied = authorization[7:].strip() if authorization.lower().startswith("bearer ") else ""
        if not supplied or not hmac.compare_digest(supplied, config.service_token):
            return JSONResponse(status_code=401, content={"detail": "Authentication required"})
    return await call_next(request)


# Include routers
app.include_router(wire_router)


@app.get("/")
async def root() -> dict:
    """Root endpoint with API information."""
    return {
        "name": config.app_name,
        "version": config.version,
        "description": "Enterprise-grade wire CLI-to-API backend",
        "docs": "/docs" if config.debug else "Disabled in production",
        "health": "/v1/wire/health/live",
        "metrics": "/v1/wire/metrics/performance",
    }


@app.get("/ready")
async def readiness() -> dict:
    """Simple readiness check."""
    return {"status": "ready"}


def run_server(host: Optional[str] = None, port: Optional[int] = None, workers: Optional[int] = None):
    """Run the FastAPI server with uvicorn."""
    cfg = get_config()
    
    uvicorn.run(
        "app.main:app",
        host=host or cfg.api_host,
        port=port or cfg.api_port,
        workers=workers or cfg.api_workers,
        log_level="info" if cfg.debug else "warning",
        access_log=cfg.debug,
        loop="uvloop",  # High-performance event loop
        http="httptools",  # Fast HTTP parser
    )


if __name__ == "__main__":
    run_server()
