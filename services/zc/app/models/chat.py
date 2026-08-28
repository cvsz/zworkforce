"""Validated contracts for persistent chat sessions."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from .ai import AIUsage


class ChatSessionCreate(BaseModel):
    """Create an empty tenant-scoped chat session."""

    model_config = ConfigDict(extra="forbid")

    title: str = Field(default="New chat", min_length=1, max_length=200)


class ChatSessionPatch(BaseModel):
    """Update user-editable chat session metadata."""

    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=1, max_length=200)


class ChatSessionMessage(BaseModel):
    """One durable message in a chat session."""

    id: str
    role: Literal["user", "assistant"]
    content: str
    created_at: datetime
    model: str | None = None
    usage: AIUsage = Field(default_factory=AIUsage)


class ChatSession(BaseModel):
    """A durable conversation owned by one tenant."""

    id: str
    object: Literal["chat.session"] = "chat.session"
    title: str
    messages: list[ChatSessionMessage] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime


__all__ = [
    "ChatSession",
    "ChatSessionCreate",
    "ChatSessionMessage",
    "ChatSessionPatch",
]
