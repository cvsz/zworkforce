"""Workspace preference service with no credential storage."""

from __future__ import annotations

from typing import Any

from app.repositories import Repository
from app.settings import default_workspace_settings


class WorkspaceSettingsService:
    def __init__(self, repository: Repository) -> None:
        self.repository = repository

    def get(self) -> dict[str, Any]:
        values, updated_at = self.repository.load_workspace_settings()
        result = default_workspace_settings()
        result.update(values)
        result["updated_at"] = updated_at
        return result

    def update(self, values: dict[str, Any]) -> dict[str, Any]:
        allowed = set(default_workspace_settings()) - {"facebook_page_url"}
        unknown = sorted(set(values) - allowed)
        if unknown:
            raise ValueError(f"Unsupported workspace setting: {unknown[0]}")
        self.repository.save_workspace_settings(values)
        return self.get()
