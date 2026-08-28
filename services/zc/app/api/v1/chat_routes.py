"""Persistent chat session and streaming response routes."""

from __future__ import annotations

import json
from collections.abc import AsyncIterator

from fastapi import APIRouter, Depends, Query, Response
from fastapi.responses import StreamingResponse

from ...core.auth import Principal, require_roles
from ...models.ai import AIResponseRequest
from ...models.chat import ChatSessionCreate, ChatSessionPatch
from ...services.ai_service import AIServiceError, UnknownCapabilityError
from ...services.chat_sessions import ChatSessionService, get_chat_session_service

router = APIRouter(prefix="/v1/chat", tags=["chat"])
_read = require_roles("admin", "developer", "agent", "cli_service", "viewer")
_write = require_roles("admin", "developer", "agent", "cli_service")


def _sse(event: str, data: dict) -> bytes:
    payload = json.dumps(data, separators=(",", ":"), ensure_ascii=False)
    return f"event: {event}\ndata: {payload}\n\n".encode()


@router.post("/sessions", status_code=201)
async def create_session(
    request: ChatSessionCreate,
    response: Response,
    principal: Principal = Depends(_write),
    service: ChatSessionService = Depends(get_chat_session_service),
) -> dict:
    session = await service.create(principal.tenant_id, request)
    response.headers["Location"] = f"/v1/chat/sessions/{session.id}"
    return {"data": session.model_dump(mode="json")}


@router.get("/sessions")
async def list_sessions(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    principal: Principal = Depends(_read),
    service: ChatSessionService = Depends(get_chat_session_service),
) -> dict:
    sessions, total = await service.list(
        principal.tenant_id, limit=limit, offset=offset
    )
    return {
        "data": [session.model_dump(mode="json") for session in sessions],
        "meta": {"total": total, "limit": limit, "offset": offset},
    }


@router.get("/sessions/{session_id}")
async def get_session(
    session_id: str,
    principal: Principal = Depends(_read),
    service: ChatSessionService = Depends(get_chat_session_service),
) -> dict:
    session = await service.get(principal.tenant_id, session_id)
    return {"data": session.model_dump(mode="json")}


@router.patch("/sessions/{session_id}")
async def patch_session(
    session_id: str,
    request: ChatSessionPatch,
    principal: Principal = Depends(_write),
    service: ChatSessionService = Depends(get_chat_session_service),
) -> dict:
    session = await service.patch(principal.tenant_id, session_id, request)
    return {"data": session.model_dump(mode="json")}


@router.delete("/sessions/{session_id}", status_code=204)
async def delete_session(
    session_id: str,
    principal: Principal = Depends(_write),
    service: ChatSessionService = Depends(get_chat_session_service),
) -> Response:
    await service.delete(principal.tenant_id, session_id)
    return Response(status_code=204)


@router.post("/sessions/{session_id}/responses")
async def create_streaming_response(
    session_id: str,
    request: AIResponseRequest,
    principal: Principal = Depends(_write),
    service: ChatSessionService = Depends(get_chat_session_service),
) -> StreamingResponse:
    # Resolve ownership before response headers are sent so a missing or
    # cross-tenant session returns the normal sanitized 404 contract.
    await service.get(principal.tenant_id, session_id)

    async def events() -> AsyncIterator[bytes]:
        try:
            async for event in service.respond(
                principal.tenant_id, session_id, request
            ):
                yield _sse(event["type"], event)
        except UnknownCapabilityError as exc:
            yield _sse(
                "response.error",
                {
                    "type": "response.error",
                    "error": {
                        "code": "unknown_capability",
                        "message": str(exc),
                    },
                },
            )
        except AIServiceError:
            yield _sse(
                "response.error",
                {
                    "type": "response.error",
                    "error": {
                        "code": "provider_error",
                        "message": "The AI provider could not complete the request.",
                    },
                },
            )

    return StreamingResponse(
        events(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "X-Accel-Buffering": "no",
        },
    )


__all__ = ["router"]
