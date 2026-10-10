"""Fail-closed computer-use dispatch gates; read-only observation only.

This thin adapter reuses the existing session authority and browser runner.
It does not provide mutation execution, privileged desktop access, or grant
authority. A trusted network sandbox remains an external deployment gate.
"""
from __future__ import annotations

from datetime import datetime
from typing import Callable

from zworkforce.sagi_computer_session import (
    ApprovalAuthority, SessionAuthority, verify_computer_use,
)
from zworkforce.sagi_computer_use import ComputerAction, ComputerUseIntent
from zworkforce.sagi_browser_runtime import BrowserPolicy, run_browser_action


def observe_approved_page(
    *,
    intent: ComputerUseIntent,
    policy: BrowserPolicy,
    url: str,
    sessions: SessionAuthority,
    approvals: ApprovalAuthority,
    now: datetime,
    emergency_stop: Callable[[], bool],
) -> bytes:
    """Authorize session and observe; deny mutation and stale/unbound target.

    Do not bind this to public API until genuine isolated egress is enforced.
    """
    if not isinstance(intent, ComputerUseIntent):
        raise PermissionError("invalid intent")
    if intent.action is not ComputerAction.OBSERVE or intent.target != url:
        raise PermissionError("only exact read-only observation target permitted")
    verify_computer_use(
        intent=intent, sessions=sessions, approvals=approvals,
        now=now, emergency_stop=emergency_stop,
    )
    # Revalidate immediately before launch, including emergency stop. This
    # does not replace a live sandbox kill switch for in-flight navigation.
    def authorized(request: ComputerUseIntent) -> bool:
        if request != intent:
            return False
        return verify_computer_use(
            intent=request, sessions=sessions, approvals=approvals,
            now=now, emergency_stop=emergency_stop,
        )
    return run_browser_action(
        intent=intent, policy=policy, url=url, authorized=authorized,
    )
