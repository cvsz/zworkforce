from enum import Enum
from pydantic import BaseModel, Field
from typing import List, Optional

class Role(str, Enum):
    ADMIN = "admin"
    DEVELOPER = "developer"
    VIEWER = "viewer"
    AGENT = "agent"

class ResourceType(str, Enum):
    FILE = "file"
    API_KEY = "api_key"
    METRICS = "metrics"
    SYSTEM_CONFIG = "system_config"

class Policy(BaseModel):
    role: Role
    resources: List[ResourceType]
    actions: List[str] = Field(default_factory=lambda: ["read"])

# Default OPA-like policy mock
DEFAULT_POLICIES = [
    Policy(role=Role.ADMIN, resources=[r for r in ResourceType], actions=["read", "write", "delete", "admin"]),
    Policy(role=Role.DEVELOPER, resources=[ResourceType.FILE, ResourceType.METRICS], actions=["read", "write"]),
    Policy(role=Role.VIEWER, resources=[ResourceType.METRICS], actions=["read"]),
    Policy(role=Role.AGENT, resources=[ResourceType.FILE], actions=["read", "write"]),
]

def check_permission(user_role: Role, resource: ResourceType, action: str) -> bool:
    for policy in DEFAULT_POLICIES:
        if policy.role == user_role and resource in policy.resources:
            if action in policy.actions or "admin" in policy.actions:
                return True
    return False
