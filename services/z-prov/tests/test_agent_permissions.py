from __future__ import annotations

from uuid import uuid4

import pytest
from pydantic import ValidationError
from zeaz_agent import (
    DecisionSource,
    PermissionOutcome,
    PermissionPolicy,
    PermissionRule,
    ToolCall,
    require_allowed,
)


def context() -> tuple:
    return uuid4(), uuid4()


@pytest.mark.parametrize(
    "outcome",
    [PermissionOutcome.ALLOW, PermissionOutcome.DENY, PermissionOutcome.ASK],
)
def test_policy_records_every_explicit_outcome(outcome: PermissionOutcome) -> None:
    session_id, correlation_id = context()
    rule = PermissionRule(
        id=f"{outcome.value}-read",
        effect=outcome,
        tool_pattern="filesystem.read",
        reason=f"{outcome.value} reads",
    )
    call = ToolCall(id="call_1", name="filesystem.read", arguments={"path": "README.md"})

    decision = PermissionPolicy((rule,)).decide(
        call,
        session_id=session_id,
        correlation_id=correlation_id,
    )

    assert decision.outcome is outcome
    assert decision.source is DecisionSource.POLICY
    assert decision.rule_id == rule.id
    assert decision.tool_call_id == call.id
    assert decision.arguments_sha256 not in str(call.arguments)


def test_default_is_ask_and_must_be_resolved_by_a_named_actor() -> None:
    session_id, correlation_id = context()
    call = ToolCall(id="call_1", name="filesystem.write")
    asked = PermissionPolicy().decide(
        call,
        session_id=session_id,
        correlation_id=correlation_id,
    )

    assert asked.outcome is PermissionOutcome.ASK
    assert asked.source is DecisionSource.DEFAULT

    allowed = PermissionPolicy.resolve_ask(
        asked,
        PermissionOutcome.ALLOW,
        decided_by="user:alice",
        reason="approved for this call",
    )

    assert allowed.outcome is PermissionOutcome.ALLOW
    assert allowed.source is DecisionSource.USER
    assert allowed.resolved_from == asked.id
    require_allowed(
        call,
        allowed,
        session_id=session_id,
        correlation_id=correlation_id,
    )


def test_only_ask_can_be_resolved_and_ask_cannot_be_final_resolution() -> None:
    session_id, correlation_id = context()
    call = ToolCall(id="call_1", name="safe.read")
    allowed = PermissionPolicy(
        (
            PermissionRule(
                id="allow-safe",
                effect="allow",
                tool_pattern="safe.*",
                reason="safe tools",
            ),
        )
    ).decide(call, session_id=session_id, correlation_id=correlation_id)

    with pytest.raises(ValueError, match="only ask"):
        PermissionPolicy.resolve_ask(
            allowed,
            PermissionOutcome.DENY,
            decided_by="user:alice",
            reason="changed mind",
        )

    asked = PermissionPolicy().decide(call, session_id=session_id, correlation_id=correlation_id)
    with pytest.raises(ValueError, match="allow or deny"):
        PermissionPolicy.resolve_ask(
            asked,
            PermissionOutcome.ASK,
            decided_by="user:alice",
            reason="ask again",
        )


def test_highest_priority_wins_and_deny_wins_equal_priority() -> None:
    call = ToolCall(id="call_1", name="filesystem.delete")
    session_id, correlation_id = context()
    rules = (
        PermissionRule(
            id="broad-deny",
            effect="deny",
            tool_pattern="filesystem.*",
            priority=10,
            reason="deny filesystem",
        ),
        PermissionRule(
            id="specific-allow",
            effect="allow",
            tool_pattern="filesystem.delete",
            priority=20,
            reason="higher priority exception",
        ),
    )
    decision = PermissionPolicy(rules).decide(
        call,
        session_id=session_id,
        correlation_id=correlation_id,
    )
    assert decision.outcome is PermissionOutcome.ALLOW

    equal_rules = (
        rules[1],
        rules[0].model_copy(update={"priority": 20}),
    )
    decision = PermissionPolicy(equal_rules).decide(
        call,
        session_id=session_id,
        correlation_id=correlation_id,
    )
    assert decision.outcome is PermissionOutcome.DENY
    assert decision.rule_id == "broad-deny"


def test_argument_attributes_narrow_a_rule() -> None:
    rule = PermissionRule(
        id="read-public",
        effect="allow",
        tool_pattern="filesystem.read",
        argument_equals={"scope": "public", "follow_links": False},
        reason="public reads without links",
    )
    policy = PermissionPolicy((rule,))
    session_id, correlation_id = context()

    allowed = policy.decide(
        ToolCall(
            id="call_1",
            name="filesystem.read",
            arguments={"scope": "public", "follow_links": False},
        ),
        session_id=session_id,
        correlation_id=correlation_id,
    )
    asked = policy.decide(
        ToolCall(
            id="call_2",
            name="filesystem.read",
            arguments={"scope": "private", "follow_links": False},
        ),
        session_id=session_id,
        correlation_id=correlation_id,
    )

    assert allowed.outcome is PermissionOutcome.ALLOW
    assert asked.outcome is PermissionOutcome.ASK


@pytest.mark.parametrize("mutation", ["arguments", "call", "session", "correlation"])
def test_allow_record_is_bound_to_exact_call_context(mutation: str) -> None:
    session_id, correlation_id = context()
    call = ToolCall(id="call_1", name="filesystem.read", arguments={"path": "README.md"})
    rule = PermissionRule(
        id="allow-read",
        effect="allow",
        tool_pattern="filesystem.read",
        reason="read only",
    )
    decision = PermissionPolicy((rule,)).decide(
        call,
        session_id=session_id,
        correlation_id=correlation_id,
    )
    actual_call = call
    actual_session = session_id
    actual_correlation = correlation_id
    if mutation == "arguments":
        actual_call = call.model_copy(update={"arguments": {"path": ".env"}})
    elif mutation == "call":
        actual_call = call.model_copy(update={"id": "call_2"})
    elif mutation == "session":
        actual_session = uuid4()
    else:
        actual_correlation = uuid4()

    with pytest.raises(PermissionError, match="does not match"):
        require_allowed(
            actual_call,
            decision,
            session_id=actual_session,
            correlation_id=actual_correlation,
        )


def test_deny_and_ask_records_never_authorize() -> None:
    call = ToolCall(id="call_1", name="shell.run")
    session_id, correlation_id = context()
    for outcome in (PermissionOutcome.DENY, PermissionOutcome.ASK):
        decision = PermissionPolicy(default=outcome).decide(
            call,
            session_id=session_id,
            correlation_id=correlation_id,
        )
        with pytest.raises(PermissionError, match="allow decision"):
            require_allowed(
                call,
                decision,
                session_id=session_id,
                correlation_id=correlation_id,
            )


def test_rule_and_decision_shapes_fail_closed() -> None:
    with pytest.raises(ValidationError):
        PermissionRule(
            id="bad",
            effect="allow",
            tool_pattern="../*",
            reason="invalid pattern",
        )
    with pytest.raises(ValueError, match="unique"):
        rule = PermissionRule(
            id="same",
            effect="deny",
            tool_pattern="*",
            reason="deny",
        )
        PermissionPolicy((rule, rule))
