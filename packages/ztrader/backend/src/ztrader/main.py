# apps/ztrader/backend/src/ztrader/main.py

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from ztrader.abt.services.audit_middleware import AuditMiddleware
from ztrader.api.v1 import admin, health, platform, trading, webhooks
from ztrader.tradingagents_integration.api import router as ta_router

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("ztrader.main")

app = FastAPI(
    title="ztrader API Gateway",
    description="Safety-first, multi-language cryptocurrency algorithmic trading API",
    version="1.0.0"
)

from prometheus_fastapi_instrumentator import Instrumentator

app.add_middleware(AuditMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3016",
        "http://127.0.0.1:3016",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "https://ztrader.zeaz.dev"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

Instrumentator().instrument(app).expose(app, include_in_schema=False, should_gzip=True)

app.include_router(health.router)
app.include_router(trading.router)
app.include_router(webhooks.router)
app.include_router(admin.router)
app.include_router(platform.router)
app.include_router(ta_router)
