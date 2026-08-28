"""Server-owned project templates."""

from __future__ import annotations

from typing import Any

PROJECT_TEMPLATES: dict[str, list[dict[str, Any]]] = {
    "blank": [],
    "web_app": [
        {
            "title": "Architecture Design",
            "description": "Define system architecture and technology choices.",
            "agent": "code_generator",
            "priority": "high",
        },
        {
            "title": "Backend API",
            "description": "Implement the authorized HTTP API.",
            "agent": "code_generator",
            "priority": "high",
        },
        {
            "title": "Frontend UI",
            "description": "Build the accessible user interface.",
            "agent": "code_generator",
            "priority": "medium",
        },
        {
            "title": "Tests",
            "description": "Add unit and integration coverage.",
            "agent": "testing_agent",
            "priority": "high",
        },
        {
            "title": "Security Audit",
            "description": "Review authentication, inputs, and data boundaries.",
            "agent": "security_auditor",
            "priority": "high",
        },
    ],
    "api": [
        {
            "title": "API Design",
            "description": "Define endpoints, schemas, and error contracts.",
            "agent": "code_generator",
            "priority": "high",
        },
        {
            "title": "Implementation",
            "description": "Implement the API behavior.",
            "agent": "code_generator",
            "priority": "high",
        },
        {
            "title": "Authentication",
            "description": "Add authentication and authorization.",
            "agent": "security_auditor",
            "priority": "high",
        },
        {
            "title": "Tests",
            "description": "Add unit and integration coverage.",
            "agent": "testing_agent",
            "priority": "high",
        },
    ],
    "cli_tool": [
        {
            "title": "CLI Design",
            "description": "Define commands, flags, and exit behavior.",
            "agent": "code_generator",
            "priority": "high",
        },
        {
            "title": "Core Logic",
            "description": "Implement command behavior.",
            "agent": "code_generator",
            "priority": "high",
        },
        {
            "title": "Tests",
            "description": "Cover commands and failure behavior.",
            "agent": "testing_agent",
            "priority": "high",
        },
    ],
    "data_pipeline": [
        {
            "title": "Schema Design",
            "description": "Define input and output schemas.",
            "agent": "code_generator",
            "priority": "high",
        },
        {
            "title": "Ingestion",
            "description": "Implement bounded data ingestion.",
            "agent": "code_generator",
            "priority": "high",
        },
        {
            "title": "Validation",
            "description": "Add data quality checks.",
            "agent": "testing_agent",
            "priority": "high",
        },
    ],
    "ml_model": [
        {
            "title": "Data Preparation",
            "description": "Implement data loading and preprocessing.",
            "agent": "code_generator",
            "priority": "high",
        },
        {
            "title": "Evaluation",
            "description": "Define metrics and validation.",
            "agent": "testing_agent",
            "priority": "high",
        },
        {
            "title": "Serving",
            "description": "Implement the bounded inference API.",
            "agent": "code_generator",
            "priority": "medium",
        },
    ],
}

__all__ = ["PROJECT_TEMPLATES"]
