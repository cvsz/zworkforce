"""FastAPI application factory for U.Perfect Social Commerce OS."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app.api import router
from app.config import Settings
from app.database import Database
from app.repositories import Repository
from app.schemas import DomainError
from app.services.catalog import CatalogService
from app.services.conversations import ConversationService
from app.services.integrations import IntegrationService
from app.services.notifications import NotificationService
from app.services.orders import OrderService
from app.services.settings import WorkspaceSettingsService


WEB_ROOT = Path(__file__).resolve().parent.parent / "web"
PROJECT_ROOT = WEB_ROOT.parent
ASSET_ROOT = PROJECT_ROOT / "assets"
INTEGRATION_GUIDE_ROOT = PROJECT_ROOT / "docs" / "integrations"


def create_app(settings: Settings | None = None) -> FastAPI:
    """Create a locally runnable API without exposing runtime secrets."""

    app = FastAPI(title="U.Perfect Social Commerce OS")
    app.state.settings = settings or Settings.from_environment()
    app.state.db = Database(app.state.settings.database_path)
    app.state.db.initialize()

    repository = Repository(app.state.db)
    catalog = CatalogService(repository)
    workspace_settings = WorkspaceSettingsService(repository)
    conversations = ConversationService(repository, catalog, settings_provider=workspace_settings.get)
    notifications = NotificationService(repository)
    orders = OrderService(
        repository,
        catalog,
        notifications,
        line_destination=app.state.settings.line_admin_destination,
    )
    integrations = IntegrationService(repository, app.state.settings, conversations)
    app.state.services = SimpleNamespace(
        repository=repository,
        catalog=catalog,
        conversations=conversations,
        orders=orders,
        integrations=integrations,
        notifications=notifications,
        workspace_settings=workspace_settings,
    )
    app.include_router(router)
    app.mount("/assets", StaticFiles(directory=ASSET_ROOT), name="assets")
    app.mount("/guides", StaticFiles(directory=INTEGRATION_GUIDE_ROOT), name="integration-guides")

    @app.exception_handler(DomainError)
    async def domain_error(_: Request, error: DomainError) -> JSONResponse:
        return JSONResponse(
            status_code=error.http_status,
            content={"error": {"code": error.code, "message": error.public_message}},
        )

    @app.exception_handler(RequestValidationError)
    async def validation_error(_: Request, error: RequestValidationError) -> JSONResponse:
        return JSONResponse(
            status_code=422,
            content={"error": {"code": "VALIDATION_ERROR", "message": "ข้อมูลที่ส่งมาไม่ถูกต้อง"}},
        )

    @app.get("/", include_in_schema=False)
    def dashboard_shell():
        return FileResponse(WEB_ROOT / "index.html", media_type="text/html")

    @app.get("/styles.css", include_in_schema=False)
    def styles():
        return FileResponse(WEB_ROOT / "styles.css", media_type="text/css")

    @app.get("/app.js", include_in_schema=False)
    def javascript():
        return FileResponse(WEB_ROOT / "app.js", media_type="text/javascript")

    @app.get("/manifest.webmanifest", include_in_schema=False)
    def manifest():
        return FileResponse(WEB_ROOT / "manifest.webmanifest", media_type="application/manifest+json")

    @app.get("/favicon.svg", include_in_schema=False)
    def favicon():
        return FileResponse(WEB_ROOT / "favicon.svg", media_type="image/svg+xml")

    @app.get("/service-worker.js", include_in_schema=False)
    def service_worker():
        return FileResponse(WEB_ROOT / "service-worker.js", media_type="application/javascript")

    return app


app = create_app()
