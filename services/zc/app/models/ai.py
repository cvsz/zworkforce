"""Validated contracts for the enterprise AI inference API."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ConversationMessage(BaseModel):
    """A single message accepted as conversation context."""

    model_config = ConfigDict(extra="forbid")

    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=200_000)


class AIResponseRequest(BaseModel):
    """A bounded server-side AI generation request."""

    model_config = ConfigDict(extra="forbid")

    prompt: str = Field(min_length=1, max_length=200_000)
    model: str | None = Field(default=None, min_length=1, max_length=128)
    system: str | None = Field(default=None, max_length=100_000)
    file_content: str | None = Field(default=None, max_length=1_000_000)
    history: list[ConversationMessage] = Field(default_factory=list, max_length=100)
    temperature: float = Field(default=0.3, ge=0.0, le=1.0)
    max_tokens: int = Field(default=4096, ge=1, le=65_536)
    personality: str | None = Field(default=None, max_length=64)
    agent: str | None = Field(default=None, max_length=64)
    skill: str | None = Field(default=None, max_length=128)
    service_tier: Literal["auto", "standard_only"] | None = None
    inference_geo: Literal["us", "global"] | None = None
    fast_mode: bool = False

    @field_validator("model")
    @classmethod
    def validate_model(cls, value: str | None) -> str | None:
        """Reject control characters before the model reaches an HTTP header or log."""
        if value is not None and any(ord(character) < 32 for character in value):
            raise ValueError("model must not contain control characters")
        return value


class AIUsage(BaseModel):
    """Token accounting when exposed by the provider adapter."""

    input_tokens: int | None = None
    output_tokens: int | None = None


class AIModel(BaseModel):
    """A model alias currently available through the inference gateway."""

    id: str
    object: Literal["model"] = "model"


class AIResponse(BaseModel):
    """Stable response resource returned by the enterprise API."""

    id: str
    object: Literal["ai.response"] = "ai.response"
    created_at: datetime
    model: str
    output_text: str
    usage: AIUsage = Field(default_factory=AIUsage)


class AICapabilities(BaseModel):
    """Discoverable options supported by the migrated CLI domain."""

    agents: list[str]
    personalities: list[str]
    skills: list[str]


__all__ = [
    "AICapabilities",
    "AIModel",
    "AIResponse",
    "AIResponseRequest",
    "AIUsage",
    "ConversationMessage",
]
