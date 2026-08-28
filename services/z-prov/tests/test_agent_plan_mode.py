from __future__ import annotations

from uuid import uuid4

import pytest
from pydantic import ValidationError
from zeaz_agent import (
    PermissionOutcome,
    PermissionPolicy,
    Plan,
    PlannedAction,
    PlanStep,
    Session,
    SessionStatus,
    ToolCall,
    ToolDefinition,
    approve_plan,
    require_execution_allowed,
    require_plan_allows,
    set_plan_mode,
)


def planned(call: ToolCall, session: Session) -> Plan:
    return Plan(
        session_id=session.id,
        summary="Apply the requested workspace change.",
        steps=(
            PlanStep(
                id="step-1",
                description="Write the requested file.",
                action=PlannedAction.from_call(call),
            ),
        ),
    )


def allowed(call: ToolCall, session: Session, correlation_id):
    return PermissionPolicy(default=PermissionOutcome.ALLOW).decide(
        call,
        session_id=session.id,
        correlation_id=correlation_id,
    )


def test_plan_mode_state_change_is_immutable_and_revisioned() -> None:
    session = Session()

    plan_session = set_plan_mode(session, enabled=True)

    assert session.execution_mode.value == "normal"
    assert plan_session.execution_mode.value == "plan"
    assert plan_session.revision == session.revision + 1
    assert set_plan_mode(plan_session, enabled=True) is plan_session


def test_plan_mode_allows_declared_read_only_tool_without_plan() -> None:
    session = set_plan_mode(Session(), enabled=True)
    call = ToolCall(id="call_1", name="filesystem.read", arguments={"path": "README.md"})

    require_plan_allows(
        session,
        call,
        (ToolDefinition(name="filesystem.read", mutating=False),),
    )


@pytest.mark.parametrize("definitions", [(), (ToolDefinition(name="filesystem.write"),)])
def test_unknown_and_mutating_tools_fail_closed_without_approval(definitions: tuple) -> None:
    session = set_plan_mode(Session(), enabled=True)
    call = ToolCall(id="call_1", name="filesystem.write", arguments={"path": "README.md"})

    with pytest.raises(PermissionError, match="blocks mutation"):
        require_plan_allows(session, call, definitions)


def test_approved_exact_action_can_pass_both_independent_gates() -> None:
    session = set_plan_mode(Session(), enabled=True)
    correlation_id = uuid4()
    call = ToolCall(
        id="call_1",
        name="filesystem.write",
        arguments={"path": "notes.txt", "content": "safe"},
    )
    plan = planned(call, session)
    approval = approve_plan(plan, approved_by="user:alice", reason="approved")
    decision = allowed(call, session, correlation_id)

    require_execution_allowed(
        session,
        call,
        decision,
        (ToolDefinition(name="filesystem.write", mutating=True),),
        correlation_id=correlation_id,
        plan=plan,
        approval=approval,
    )


@pytest.mark.parametrize("tamper", ["arguments", "plan", "session", "call"])
def test_plan_approval_cannot_be_replayed_after_tampering(tamper: str) -> None:
    session = set_plan_mode(Session(), enabled=True)
    call = ToolCall(id="call_1", name="filesystem.write", arguments={"path": "notes.txt"})
    plan = planned(call, session)
    approval = approve_plan(plan, approved_by="user:alice", reason="approved")
    actual_session = session
    actual_call = call
    actual_plan = plan
    if tamper == "arguments":
        actual_call = call.model_copy(update={"arguments": {"path": ".env"}})
    elif tamper == "plan":
        actual_plan = plan.model_copy(update={"summary": "A different plan"})
    elif tamper == "session":
        actual_session = set_plan_mode(Session(), enabled=True)
    else:
        actual_call = call.model_copy(update={"id": "call_2"})

    with pytest.raises(PermissionError):
        require_plan_allows(
            actual_session,
            actual_call,
            (ToolDefinition(name="filesystem.write"),),
            plan=actual_plan,
            approval=approval,
        )


def test_plan_approval_does_not_substitute_for_tool_permission() -> None:
    session = set_plan_mode(Session(), enabled=True)
    correlation_id = uuid4()
    call = ToolCall(id="call_1", name="filesystem.write")
    plan = planned(call, session)
    approval = approve_plan(plan, approved_by="user:alice", reason="approve plan")
    denied = PermissionPolicy(default=PermissionOutcome.DENY).decide(
        call,
        session_id=session.id,
        correlation_id=correlation_id,
    )

    with pytest.raises(PermissionError, match="allow decision"):
        require_execution_allowed(
            session,
            call,
            denied,
            (ToolDefinition(name="filesystem.write"),),
            correlation_id=correlation_id,
            plan=plan,
            approval=approval,
        )


def test_permission_allow_does_not_substitute_for_plan_approval() -> None:
    session = set_plan_mode(Session(), enabled=True)
    correlation_id = uuid4()
    call = ToolCall(id="call_1", name="filesystem.write")
    decision = allowed(call, session, correlation_id)

    with pytest.raises(PermissionError, match="blocks mutation"):
        require_execution_allowed(
            session,
            call,
            decision,
            (ToolDefinition(name="filesystem.write"),),
            correlation_id=correlation_id,
        )


def test_duplicate_definitions_and_invalid_plans_are_rejected() -> None:
    session = set_plan_mode(Session(), enabled=True)
    call = ToolCall(id="call_1", name="filesystem.write")
    duplicate = (
        ToolDefinition(name="filesystem.write", mutating=False),
        ToolDefinition(name="filesystem.write", mutating=True),
    )
    with pytest.raises(ValueError, match="unique"):
        require_plan_allows(session, call, duplicate)

    step = PlanStep(id="same", description="one")
    with pytest.raises(ValidationError, match="unique"):
        Plan(session_id=session.id, summary="bad", steps=(step, step))


def test_inactive_session_cannot_enter_plan_mode() -> None:
    with pytest.raises(ValueError, match="active"):
        set_plan_mode(Session(status=SessionStatus.COMPLETED), enabled=True)
