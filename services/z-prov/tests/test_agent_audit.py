from __future__ import annotations

import json
import os
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from uuid import uuid4

import pytest
from zeaz_agent import (
    AuditIntegrityError,
    JsonlAuditLog,
    PermissionOutcome,
    PermissionPolicy,
    Plan,
    PlannedAction,
    PlanStep,
    Session,
    ToolCall,
    approve_plan,
    record_permission_decision,
    record_plan_approval,
)


def append(log: JsonlAuditLog, index: int = 0):
    return log.append(
        session_id=uuid4(),
        correlation_id=uuid4(),
        event_type="tool.permission_decided",
        actor="policy",
        subject_id=f"call_{index}",
        details={"outcome": "allow", "index": index},
    )


def test_entries_are_correlated_sequenced_and_hash_chained(tmp_path: Path) -> None:
    log = JsonlAuditLog(tmp_path / "audit.jsonl")

    first = append(log, 1)
    second = append(log, 2)
    verified = log.verify()

    assert verified == (first, second)
    assert first.event.sequence == 0
    assert first.event.session_id
    assert first.event.correlation_id
    assert second.event.sequence == 1
    assert second.previous_sha256 == first.sha256
    assert (tmp_path / "audit.jsonl").stat().st_mode & 0o777 == 0o600


def test_sensitive_and_prompt_fields_are_redacted_before_persistence(tmp_path: Path) -> None:
    path = tmp_path / "audit.jsonl"
    log = JsonlAuditLog(path)
    secret = "do-not-persist-this-value"

    log.append(
        session_id=uuid4(),
        correlation_id=uuid4(),
        event_type="model.requested",
        actor="agent",
        details={
            "api_key": secret,
            "prompt": secret,
            "nested": {"authorization": secret},
            "input_tokens": 12,
        },
    )

    raw = path.read_text(encoding="utf-8")
    assert secret not in raw
    details = log.verify()[0].event.details
    assert details["api_key"] == "[REDACTED]"
    assert details["prompt"] == "[REDACTED]"
    assert details["nested"]["authorization"] == "[REDACTED]"
    assert details["input_tokens"] == 12


@pytest.mark.parametrize("tamper", ["edit", "reorder", "partial"])
def test_verification_detects_corruption(tmp_path: Path, tamper: str) -> None:
    path = tmp_path / "audit.jsonl"
    log = JsonlAuditLog(path)
    append(log, 1)
    append(log, 2)
    lines = path.read_bytes().splitlines(keepends=True)
    if tamper == "edit":
        value = json.loads(lines[0])
        value["event"]["details"]["outcome"] = "deny"
        lines[0] = json.dumps(value, separators=(",", ":"), sort_keys=True).encode() + b"\n"
    elif tamper == "reorder":
        lines.reverse()
    else:
        lines[-1] = lines[-1][:-2]
    path.write_bytes(b"".join(lines))

    with pytest.raises(AuditIntegrityError):
        log.verify()


def test_parallel_appenders_cannot_reuse_sequence_numbers(tmp_path: Path) -> None:
    log = JsonlAuditLog(tmp_path / "audit.jsonl", fsync=False)

    with ThreadPoolExecutor(max_workers=8) as pool:
        tuple(pool.map(lambda index: append(log, index), range(40)))

    entries = log.verify()
    assert [entry.event.sequence for entry in entries] == list(range(40))
    assert len({entry.sha256 for entry in entries}) == 40


def test_event_and_log_bounds_fail_before_append(tmp_path: Path) -> None:
    path = tmp_path / "audit.jsonl"
    log = JsonlAuditLog(path, max_event_bytes=1024, max_log_bytes=2048, fsync=False)

    with pytest.raises(ValueError, match="event exceeds"):
        log.append(
            session_id=uuid4(),
            correlation_id=uuid4(),
            event_type="tool.completed",
            actor="agent",
            details={"safe_metadata": "x" * 4096},
        )
    assert path.read_bytes() == b""

    while path.stat().st_size < 1024:
        append(log)
    with pytest.raises(ValueError, match="reached"):
        for index in range(100):
            append(log, index)


def test_symlink_and_insecure_existing_file_are_rejected(tmp_path: Path) -> None:
    target = tmp_path / "target"
    target.write_text("", encoding="utf-8")
    os.chmod(target, 0o600)
    link = tmp_path / "audit-link"
    link.symlink_to(target)
    with pytest.raises(AuditIntegrityError, match="safely"):
        append(JsonlAuditLog(link))

    insecure = tmp_path / "insecure"
    insecure.write_text("", encoding="utf-8")
    os.chmod(insecure, 0o644)
    with pytest.raises(AuditIntegrityError, match="owner-only"):
        append(JsonlAuditLog(insecure))


def test_nested_detail_limits_fail_closed(tmp_path: Path) -> None:
    value: dict = {"leaf": True}
    for _ in range(18):
        value = {"next": value}

    with pytest.raises(ValueError, match="nesting"):
        JsonlAuditLog(tmp_path / "audit.jsonl").append(
            session_id=uuid4(),
            correlation_id=uuid4(),
            event_type="session.updated",
            actor="agent",
            details=value,
        )


def test_permission_and_plan_records_emit_only_metadata(tmp_path: Path) -> None:
    log = JsonlAuditLog(tmp_path / "audit.jsonl")
    session_id = uuid4()
    correlation_id = uuid4()
    call = ToolCall(id="call_1", name="filesystem.write", arguments={"content": "private"})
    decision = PermissionPolicy(default=PermissionOutcome.ALLOW).decide(
        call,
        session_id=session_id,
        correlation_id=correlation_id,
    )
    record_permission_decision(log, decision)

    session = Session(id=session_id)
    plan = Plan(
        session_id=session.id,
        summary="Write the file.",
        steps=(
            PlanStep(
                id="step-1",
                description="Write it.",
                action=PlannedAction.from_call(call),
            ),
        ),
    )
    approval = approve_plan(plan, approved_by="user:alice", reason="approved")
    record_plan_approval(log, approval, correlation_id=correlation_id)

    entries = log.verify()
    assert [entry.event.event_type for entry in entries] == [
        "tool.permission_decided",
        "plan.approved",
    ]
    assert "private" not in (tmp_path / "audit.jsonl").read_text(encoding="utf-8")
