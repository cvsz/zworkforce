"""Enterprise API routes for capabilities migrated from the legacy AI CLI."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from ...core.auth import Principal, require_roles
from ...models.ai import AICapabilities, AIModel, AIResponse, AIResponseRequest
from ...services.ai_service import (
    AIService,
    AIServiceError,
    UnknownCapabilityError,
    get_ai_service,
)

router = APIRouter(prefix="/v1/ai", tags=["AI"])
_ai_roles = require_roles("admin", "developer", "agent", "cli_service")


@router.get("/capabilities", response_model=dict[str, AICapabilities])
async def get_capabilities(
    _principal: Principal = Depends(_ai_roles),
    service: AIService = Depends(get_ai_service),
) -> dict[str, AICapabilities]:
    """Discover agents, personalities, and skills supported by the server."""
    return {"data": service.capabilities()}


@router.post("/responses", response_model=dict[str, AIResponse], status_code=201)
async def create_response(
    request: AIResponseRequest,
    _principal: Principal = Depends(_ai_roles),
    service: AIService = Depends(get_ai_service),
) -> dict[str, AIResponse] | JSONResponse:
    """Create a synchronous AI response using server-owned provider credentials."""
    try:
        response = await service.create_response(request)
    except UnknownCapabilityError as exc:
        return JSONResponse(
            status_code=422,
            content={
                "error": {
                    "code": "unknown_capability",
                    "message": str(exc),
                }
            },
        )
    except AIServiceError:
        return JSONResponse(
            status_code=502,
            content={
                "error": {
                    "code": "provider_error",
                    "message": "The AI provider could not complete the request.",
                }
            },
        )
    return {"data": response}


@router.get("/models", response_model=dict[str, list[AIModel]])
async def list_models(
    _principal: Principal = Depends(_ai_roles),
    service: AIService = Depends(get_ai_service),
) -> dict[str, list[AIModel]]:
    """List sanitized model aliases visible through the inference gateway."""
    return {"data": await service.list_models()}


__all__ = ["router"]
