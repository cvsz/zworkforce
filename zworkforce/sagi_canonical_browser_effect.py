"""SAGI adapter to existing tenant-scoped, transactional browser_effects3 ledger.

The canonical zWorkforce database owns approval checks, atomic claims and
effect lifecycle. This adapter deliberately does not grant approvals or execute
a browser action. A claimed effect cannot be transparently retried.
"""
from __future__ import annotations

from typing import Any, Protocol

from zworkforce.sagi_computer_use import ComputerAction, ComputerUseIntent


class BrowserEffectAuthority(Protocol):
    def begin_browser_effect(
        self, tenant_id: str, *, idempotency_key: str,
        action_sha256: str, approval_task_id: str
    ) -> dict[str, Any]: ...
    def claim_browser_effect(
        self, tenant_id: str, effect_id: str
    ) -> tuple[dict[str, Any], bool]: ...
    def finish_browser_effect(
        self, tenant_id: str, effect_id: str, *, status: str,
        result_sha256: str = "", error_code: str = ""
    ) -> dict[str, Any]: ...


class CanonicalComputerEffect:
    """Single-use mutation intent linked to canonical approval task."""

    def __init__(self, authority: BrowserEffectAuthority):
        self.authority = authority

    def claim(
        self, *, intent: ComputerUseIntent, approval_task_id: str
    ) -> dict[str, Any]:
        if not isinstance(intent, ComputerUseIntent):
            raise PermissionError("valid computer intent required")
        if intent.action is ComputerAction.OBSERVE or not intent.requires_approval:
            raise PermissionError("mutating intent and canonical task approval required")
        if not isinstance(approval_task_id, str) or not approval_task_id.strip():
            raise PermissionError("canonical approval task required")
        # The database checks task tenant, independent approvals, cancellations
        # and the one-effect-per-approved-task unique constraint.
        effect = self.authority.begin_browser_effect(
            intent.tenant_id,
            idempotency_key=intent.request_digest,
            action_sha256=intent.request_digest,
            approval_task_id=approval_task_id,
        )
        claimed, execute = self.authority.claim_browser_effect(
            intent.tenant_id, effect["id"]
        )
        if not execute:
            raise PermissionError("browser effect already claimed or rejected")
        if claimed.get("status") != "executing" or claimed.get("action_sha256") != intent.request_digest:
            raise PermissionError("canonical ledger returned mismatched effect")
        return claimed

    def finish(
        self, *, intent: ComputerUseIntent, effect_id: str,
        status: str, result_sha256: str = "", error_code: str = ""
    ) -> dict[str, Any]:
        if status not in {"succeeded", "failed", "unknown", "canceled"}:
            raise ValueError("invalid completion status")
        return self.authority.finish_browser_effect(
            intent.tenant_id, effect_id, status=status,
            result_sha256=result_sha256, error_code=error_code,
        )
