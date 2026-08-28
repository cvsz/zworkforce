"""Tenant-isolated durable chat session orchestration."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from app.models.ai import AIResponseRequest, ConversationMessage
from app.models.chat import ChatSession, ChatSessionCreate, ChatSessionPatch

from .ai_service import AIService
from .chat_session_store import AtomicChatSessionStore

_DOMAIN = "chat-sessions"


def _id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex}"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _title_from_prompt(prompt: str) -> str:
    compact = " ".join(prompt.split())
    return compact[:77] + "..." if len(compact) > 80 else compact


class ChatSessionService:
    """Persist conversations locally and invoke the supported AI service."""

    def __init__(self, store: AtomicChatSessionStore, ai_service: AIService) -> None:
        self.store = store
        self.ai_service = ai_service
        self._locks: dict[tuple[str, str], asyncio.Lock] = {}
        self._locks_guard = asyncio.Lock()

    async def _lock(self, tenant_id: str, session_id: str) -> asyncio.Lock:
        key = (tenant_id, session_id)
        async with self._locks_guard:
            return self._locks.setdefault(key, asyncio.Lock())

    async def create(
        self, tenant_id: str, request: ChatSessionCreate
    ) -> ChatSession:
        item = await self.store.create(
            tenant_id,
            _DOMAIN,
            _id("chat"),
            {
                "object": "chat.session",
                "title": request.title,
                "messages": [],
            },
        )
        return ChatSession.model_validate(item)

    async def get(self, tenant_id: str, session_id: str) -> ChatSession:
        item = await self.store.get(tenant_id, _DOMAIN, session_id)
        return ChatSession.model_validate(item)

    async def list(
        self, tenant_id: str, *, limit: int, offset: int
    ) -> tuple[list[ChatSession], int]:
        items, total = await self.store.list(
            tenant_id, _DOMAIN, limit=limit, offset=offset
        )
        return [ChatSession.model_validate(item) for item in items], total

    async def patch(
        self,
        tenant_id: str,
        session_id: str,
        request: ChatSessionPatch,
    ) -> ChatSession:
        lock = await self._lock(tenant_id, session_id)
        async with lock:
            item = await self.store.get(tenant_id, _DOMAIN, session_id)
            item["title"] = request.title
            updated = await self.store.replace(
                tenant_id, _DOMAIN, session_id, item
            )
        return ChatSession.model_validate(updated)

    async def delete(self, tenant_id: str, session_id: str) -> None:
        lock = await self._lock(tenant_id, session_id)
        async with lock:
            await self.store.delete(tenant_id, _DOMAIN, session_id)
        async with self._locks_guard:
            self._locks.pop((tenant_id, session_id), None)

    async def respond(
        self,
        tenant_id: str,
        session_id: str,
        request: AIResponseRequest,
    ) -> AsyncIterator[dict[str, Any]]:
        """Persist one user/assistant exchange while yielding safe SSE events."""
        lock = await self._lock(tenant_id, session_id)
        async with lock:
            item = await self.store.get(tenant_id, _DOMAIN, session_id)
            history = [
                ConversationMessage(role=message["role"], content=message["content"])
                for message in item["messages"]
            ]
            user_message = {
                "id": _id("msg"),
                "role": "user",
                "content": request.prompt,
                "created_at": _now(),
                "model": request.model,
                "usage": {},
            }
            item["messages"].append(user_message)
            if not item["messages"][:-1] and item["title"] == "New chat":
                item["title"] = _title_from_prompt(request.prompt)
            await self.store.replace(tenant_id, _DOMAIN, session_id, item)

            effective_request = request.model_copy(update={"history": history})
            completed: dict[str, Any] | None = None
            async for event in self.ai_service.stream_response(effective_request):
                if event["type"] == "response.completed":
                    completed = event["response"]
                yield event

            if completed is None:
                return
            assistant_message = {
                "id": _id("msg"),
                "role": "assistant",
                "content": completed["output_text"],
                "created_at": completed["created_at"],
                "model": completed["model"],
                "usage": completed["usage"],
            }
            item = await self.store.get(tenant_id, _DOMAIN, session_id)
            item["messages"].append(assistant_message)
            await self.store.replace(tenant_id, _DOMAIN, session_id, item)


_service: ChatSessionService | None = None


def get_chat_session_service_instance() -> ChatSessionService:
    """Return the process-local chat session application service."""
    from .ai_service import get_ai_service_instance

    global _service
    if _service is None:
        from app.core.config import get_config

        config = get_config()
        _service = ChatSessionService(
            AtomicChatSessionStore(config.chat_session_dir),
            get_ai_service_instance(),
        )
    return _service


async def get_chat_session_service() -> ChatSessionService:
    """FastAPI dependency for the process-local chat session service."""
    return get_chat_session_service_instance()


__all__ = [
    "ChatSessionService",
    "get_chat_session_service",
    "get_chat_session_service_instance",
]
