from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import UUID

import pytest
from pydantic import ValidationError
from zeaz_sandbox.schemas import (
    EgressDestination,
    ExecutionReceipt,
    ExecutionState,
    JobRequest,
    JobSpec,
    NetworkMode,
    SandboxLimits,
    SandboxPolicy,
    WorkspaceAccess,
    approve_job,
    job_spec_digest,
    policy_digest,
)

SESSION_ID = UUID("00000000-0000-0000-0000-000000000001")
CORRELATION_ID = UUID("00000000-0000-0000-0000-000000000002")
PERMISSION_ID = UUID("00000000-0000-0000-0000-000000000003")
NOW = datetime(2026, 7, 26, tzinfo=UTC)
IMAGE = "registry.example/zeaz/worker@sha256:" + "a" * 64


def spec(**changes) -> JobSpec:
    values = {
        "session_id": SESSION_ID,
        "correlation_id": CORRELATION_ID,
        "image": IMAGE,
        "command": ("/usr/bin/python3", "-c", "print('safe')"),
        "workspace": Path("/workspace/job"),
    }
    values.update(changes)
    return JobSpec(**values)


def test_job_round_trip_uses_immutable_argv_and_digest_pinned_image() -> None:
    job = spec()
    approval = approve_job(
        job,
        approved_by="user:test",
        permission_decision_id=PERMISSION_ID,
        now=NOW,
    )
    request = JobRequest(spec=job, approval=approval)
    assert request == JobRequest.model_validate_json(request.model_dump_json())
    assert request.spec.command == ("/usr/bin/python3", "-c", "print('safe')")
    assert request.approval.spec_sha256 == job_spec_digest(job)
    request.require_current_approval(NOW + timedelta(seconds=1))
    with pytest.raises(ValidationError):
        request.spec.command = ("/bin/sh",)  # type: ignore[misc]


@pytest.mark.parametrize(
    "value",
    (
        "/bin/sh -c id",
        (),
        ("ok", "\x00bad"),
        ("x" * 16_385,),
    ),
)
def test_shell_strings_empty_and_invalid_argv_are_rejected(value) -> None:
    with pytest.raises(ValidationError):
        spec(command=value)


@pytest.mark.parametrize(
    "image",
    (
        "worker:latest",
        "worker@sha256:abc",
        "WORKER@sha256:" + "a" * 64,
        "worker@sha256:" + "g" * 64,
    ),
)
def test_image_must_be_exact_lowercase_sha256_reference(image: str) -> None:
    with pytest.raises(ValidationError):
        spec(image=image)


def test_approval_is_bound_to_every_execution_relevant_field() -> None:
    original = spec()
    approval = approve_job(
        original,
        approved_by="user:test",
        permission_decision_id=PERMISSION_ID,
        now=NOW,
    )
    for changed in (
        spec(command=("id",)),
        spec(workspace=Path("/different")),
        spec(policy=SandboxPolicy(workspace_access=WorkspaceAccess.READ_WRITE)),
        spec(image="worker@sha256:" + "b" * 64),
    ):
        with pytest.raises(ValidationError, match="exact job"):
            JobRequest(spec=changed, approval=approval)


def test_expired_or_not_yet_valid_approval_is_denied() -> None:
    job = spec()
    request = JobRequest(
        spec=job,
        approval=approve_job(
            job,
            approved_by="user:test",
            permission_decision_id=PERMISSION_ID,
            now=NOW,
            lifetime_seconds=60,
        ),
    )
    with pytest.raises(PermissionError):
        request.require_current_approval(NOW - timedelta(seconds=1))
    with pytest.raises(PermissionError):
        request.require_current_approval(NOW + timedelta(seconds=60))


def test_network_is_disabled_by_default_and_allow_list_is_exact() -> None:
    default = SandboxPolicy()
    assert default.network_mode is NetworkMode.DISABLED
    assert default.allowed_destinations == ()
    allowed = SandboxPolicy(
        network_mode=NetworkMode.ALLOW_LIST,
        allowed_destinations=(
            EgressDestination(host="API.Example.com.", ports=(443, 8443)),
        ),
    )
    assert allowed.allowed_destinations[0].host == "api.example.com"
    assert policy_digest(allowed) != policy_digest(default)
    with pytest.raises(ValidationError):
        SandboxPolicy(
            network_mode=NetworkMode.DISABLED,
            allowed_destinations=(EgressDestination(host="example.com", ports=(443,)),),
        )
    with pytest.raises(ValidationError):
        SandboxPolicy(network_mode=NetworkMode.ALLOW_LIST)


@pytest.mark.parametrize(
    "host",
    (
        "*",
        "*.example.com",
        "localhost",
        "127.0.0.1",
        "::1",
        "169.254.169.254",
        "metadata.google.internal",
        "224.0.0.1",
    ),
)
def test_metadata_loopback_and_wildcard_egress_is_forbidden(host: str) -> None:
    with pytest.raises(ValidationError):
        EgressDestination(host=host, ports=(80,))


def test_resource_limits_have_secure_bounds() -> None:
    for changes in (
        {"timeout_seconds": 0},
        {"cpu_cores": 0},
        {"memory_bytes": 1024},
        {"process_count": 0},
        {"file_bytes": 1024},
        {"temporary_bytes": 1024},
        {"output_bytes": 1},
    ):
        with pytest.raises(ValidationError):
            SandboxLimits(**changes)


def test_receipt_requires_coherent_terminal_state_and_policy_binding() -> None:
    job = spec()
    approval = approve_job(
        job,
        approved_by="user:test",
        permission_decision_id=PERMISSION_ID,
        now=NOW,
    )
    receipt = ExecutionReceipt(
        job_id=job.id,
        session_id=job.session_id,
        correlation_id=job.correlation_id,
        approval_id=approval.id,
        image_digest="sha256:" + "a" * 64,
        policy_sha256=policy_digest(job.policy),
        state=ExecutionState.COMPLETED,
        exit_code=0,
        started_at=NOW,
        finished_at=NOW + timedelta(seconds=1),
        stdout_bytes=5,
        stderr_bytes=0,
        cleanup_complete=True,
    )
    assert receipt.state is ExecutionState.COMPLETED
    with pytest.raises(ValidationError):
        ExecutionReceipt.model_validate(
            {**receipt.model_dump(), "state": ExecutionState.REJECTED}
        )
