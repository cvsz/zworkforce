from contextlib import asynccontextmanager
import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

try:
    from app.config import settings
    from app.routes.api import router as api_router
    from app.services.browser_runtime import configure_browser_runtime
except ImportError:
    from server.app.config import settings
    from server.app.routes.api import router as api_router
    from server.app.services.browser_runtime import configure_browser_runtime


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.browser_runtime = await configure_browser_runtime()
    yield


app = FastAPI(
    title=settings.app_name,
    version=settings.version,
    description="Full-Stack AI Sidebar, ChatPDF, Summarizer & Multi-Model Gateway",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router)

web_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "web")
if os.path.exists(web_dir):
    app.mount("/web", StaticFiles(directory=web_dir, html=True), name="web")


@app.get("/health")
async def health():
    return {
        "status": "healthy",
        "service": "zider-bff",
        "version": settings.version,
        "browser_runtime": getattr(app.state, "browser_runtime", "uninitialized"),
    }
