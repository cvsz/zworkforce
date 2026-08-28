"""Contracts for CLI capabilities migrated to tenant-aware resource APIs."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, model_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ProjectCreate(StrictModel):
    name: str = Field(min_length=1, max_length=200)
    description: str = Field(default="", max_length=20_000)
    template: Literal["blank", "web_app", "api", "cli_tool", "data_pipeline", "ml_model"] = "blank"


class ProjectPatch(StrictModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=20_000)
    status: Literal["planning", "active", "paused", "done", "archived"] | None = None
    context: str | None = Field(default=None, max_length=200_000)


class TaskCreate(StrictModel):
    title: str = Field(min_length=1, max_length=300)
    description: str = Field(default="", max_length=20_000)
    agent: str = Field(default="", max_length=64)
    priority: Literal["low", "medium", "high", "critical"] = "medium"


class TaskPatch(StrictModel):
    title: str | None = Field(default=None, min_length=1, max_length=300)
    description: str | None = Field(default=None, max_length=20_000)
    agent: str | None = Field(default=None, max_length=64)
    priority: Literal["low", "medium", "high", "critical"] | None = None
    status: Literal["todo", "in_progress", "done", "blocked"] | None = None
    result: str | None = Field(default=None, max_length=200_000)


class ArtifactCreate(StrictModel):
    name: str = Field(min_length=1, max_length=200)
    artifact_type: Literal[
        "code", "document", "config", "test", "schema", "prompt", "data", "other"
    ] = "code"
    language: str = Field(default="", max_length=64)
    content: str | None = Field(default=None, max_length=1_000_000)
    prompt: str | None = Field(default=None, max_length=200_000)
    project_id: str | None = Field(default=None, max_length=64)
    tags: list[str] = Field(default_factory=list, max_length=50)
    model: str | None = Field(default=None, max_length=128)

    @model_validator(mode="after")
    def require_content_or_prompt(self) -> "ArtifactCreate":
        if not self.content and not self.prompt:
            raise ValueError("content or prompt is required")
        return self


class ProjectPlanCreate(StrictModel):
    model: str | None = Field(default=None, max_length=128)


class ProjectTaskRunCreate(StrictModel):
    model: str | None = Field(default=None, max_length=128)


class ArtifactIteration(StrictModel):
    feedback: str = Field(min_length=1, max_length=200_000)
    model: str | None = Field(default=None, max_length=128)


class ArtifactPatch(StrictModel):
    tags: list[str] | None = Field(default=None, max_length=50)
    project_id: str | None = Field(default=None, max_length=64)


class ResearchCreate(StrictModel):
    topic: str = Field(min_length=1, max_length=2_000)
    depth: int = Field(default=4, ge=1, le=10)
    source_urls: list[HttpUrl] = Field(default_factory=list, max_length=20)
    model: str | None = Field(default=None, max_length=128)


class FileQuestion(StrictModel):
    prompt: str = Field(min_length=1, max_length=200_000)
    model: str | None = Field(default=None, max_length=128)


class ManagedAgentRunCreate(StrictModel):
    task: str = Field(min_length=1, max_length=200_000)
    model: str | None = Field(default=None, max_length=128)
    agent: Literal[
        "code_generator",
        "code_reviewer",
        "testing_agent",
        "documentation_agent",
        "optimizer",
        "security_auditor",
        "full_stack",
    ] = "full_stack"
    memory_store_id: str | None = Field(default=None, max_length=64)
    vault_id: str | None = Field(default=None, max_length=64)
    system: str | None = Field(default=None, max_length=100_000)
    outcome_description: str | None = Field(default=None, max_length=20_000)
    outcome_rubric: str | None = Field(default=None, max_length=200_000)
    outcome_max_iterations: int = Field(default=1, ge=1, le=20)


class MemoryStoreCreate(StrictModel):
    name: str = Field(min_length=1, max_length=200)


class MemoryCreate(StrictModel):
    path: str = Field(min_length=1, max_length=500)
    content: str = Field(min_length=1, max_length=1_000_000)


class MemoryPatch(StrictModel):
    path: str | None = Field(default=None, min_length=1, max_length=500)
    content: str | None = Field(default=None, min_length=1, max_length=1_000_000)

    @model_validator(mode="after")
    def require_update(self) -> "MemoryPatch":
        if self.path is None and self.content is None:
            raise ValueError("path or content is required")
        return self


class DreamCreate(StrictModel):
    memory_store_id: str = Field(min_length=1, max_length=64)
    session_ids: list[str] = Field(default_factory=list, max_length=100)
    instructions: str | None = Field(default=None, max_length=100_000)
    model: str | None = Field(default=None, max_length=128)


class WebhookCreate(StrictModel):
    url: HttpUrl
    event_types: list[str] = Field(default_factory=list, max_length=50)

    @model_validator(mode="after")
    def require_https(self) -> "WebhookCreate":
        if self.url.scheme != "https":
            raise ValueError("webhook URL must use HTTPS")
        return self


class VaultCreate(StrictModel):
    display_name: str = Field(min_length=1, max_length=200)
    external_user_id: str | None = Field(default=None, max_length=200)


class VaultCredentialCreate(StrictModel):
    credential_type: Literal[
        "mcp_oauth", "static_bearer", "environment_variable"
    ]
    secret_value: str = Field(min_length=1, max_length=100_000)
    mcp_server_url: HttpUrl | None = None
    secret_name: str | None = Field(default=None, max_length=200)
    allowed_domains: list[str] = Field(default_factory=list, max_length=100)
    injection_location: Literal["headers", "body", "both"] | None = None


class ScheduleCreate(StrictModel):
    agent_id: str = Field(min_length=1, max_length=128)
    environment_id: str = Field(min_length=1, max_length=128)
    cron_expression: str = Field(min_length=5, max_length=200)
    timezone: str = Field(default="UTC", min_length=1, max_length=100)
    task: str = Field(default="", max_length=200_000)


class EnvironmentCreate(StrictModel):
    name: str = Field(min_length=1, max_length=200)


class MultiAgentReviewCreate(StrictModel):
    file_id: str = Field(min_length=1, max_length=64)
    specialists: list[
        Literal["security", "style", "test-coverage"]
    ] = Field(min_length=1, max_length=3)
    model: str | None = Field(default=None, max_length=128)


__all__ = [
    "ArtifactCreate",
    "ArtifactIteration",
    "ArtifactPatch",
    "FileQuestion",
    "DreamCreate",
    "EnvironmentCreate",
    "ManagedAgentRunCreate",
    "MemoryCreate",
    "MemoryPatch",
    "MemoryStoreCreate",
    "MultiAgentReviewCreate",
    "ProjectCreate",
    "ProjectPlanCreate",
    "ProjectPatch",
    "ProjectTaskRunCreate",
    "ResearchCreate",
    "TaskCreate",
    "TaskPatch",
    "ScheduleCreate",
    "VaultCreate",
    "VaultCredentialCreate",
    "WebhookCreate",
]
