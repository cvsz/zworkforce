from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest
from pydantic import SecretStr
from zeaz_enterprise.deletion import (
    AuthorizationGrant,
    DeletionControlError,
    DeletionTarget,
    PermanentDeletionCoordinator,
    ResolvedDeletionTarget,
)

NOW = datetime(2026, 7, 26, 12, 0, tzinfo=UTC)
PLAN_ID = UUID("12345678-1234-5678-1234-567812345678")


def target() -> DeletionTarget:
    return DeletionTarget(
        provider="anthropic",
        resource_type="organization",
        resource_id="org_1",
        organization_id="org_1",
    )


def resolved(*, changed: bool = False, organization_wide: bool = True):
    return ResolvedDeletionTarget(
        target=target(),
        organization_wide=organization_wide,
        display_name="Example Organization",
        state={"status": "changed" if changed else "active", "member_count": 12},
        dependent_resource_ids=("workspace_1", "workspace_2"),
    )


class Harness:
    changed = False
    resolutions = 0
    executions = 0
    grants: dict[str, AuthorizationGrant]

    def __init__(self) -> None:
        self.grants = {}

    async def resolve(self, _: DeletionTarget) -> ResolvedDeletionTarget:
        self.resolutions += 1
        return resolved(changed=self.changed)

    async def verify(self, token: SecretStr) -> AuthorizationGrant:
        return self.grants[token.get_secret_value()]

    async def execute(self, _: ResolvedDeletionTarget, key: str) -> str:
        self.executions += 1
        assert key == "delete-org-1"
        return "operation_1"


def coordinator(harness: Harness, clock=lambda: NOW) -> PermanentDeletionCoordinator:
    return PermanentDeletionCoordinator(
        resolver=harness.resolve,
        authorization_verifier=harness.verify,
        executor=harness.execute,
        clock=clock,
        plan_id_factory=lambda: PLAN_ID,
    )


def grant(preview, principal: str, **changes) -> AuthorizationGrant:
    values = {
        "principal_id": principal,
        "plan_id": preview.plan_id,
        "resolution_digest": preview.resolution_digest,
        "decision": "allow",
        "issued_at": NOW - timedelta(seconds=10),
        "expires_at": NOW + timedelta(minutes=5),
    }
    values.update(changes)
    return AuthorizationGrant(**values)


@pytest.mark.asyncio
async def test_preview_is_non_mutating_and_contains_resolved_digest_evidence() -> None:
    harness = Harness()
    preview = await coordinator(harness).preview(target())
    assert preview.dry_run is True
    assert preview.required_approvals == 2
    assert preview.resolved.dependent_resource_ids == ("workspace_1", "workspace_2")
    assert len(preview.resolution_digest) == 64
    assert harness.resolutions == 1
    assert harness.executions == 0


@pytest.mark.asyncio
async def test_org_wide_delete_requires_exact_confirmation_and_two_principals() -> None:
    harness = Harness()
    control = coordinator(harness)
    preview = await control.preview(target())
    harness.grants = {
        "token-a": grant(preview, "admin_1"),
        "token-b": grant(preview, "admin_2"),
    }
    receipt = await control.execute(
        preview,
        confirmation=preview.confirmation_text,
        authorization_tokens=(SecretStr("token-a"), SecretStr("token-b")),
        idempotency_key="delete-org-1",
    )
    assert receipt.authorizing_principal_ids == ("admin_1", "admin_2")
    assert receipt.resolution_digest == preview.resolution_digest
    assert receipt.provider_operation_id == "operation_1"
    assert harness.resolutions == 2
    assert harness.executions == 1
    assert "token-a" not in repr(receipt)


@pytest.mark.asyncio
async def test_changed_target_blocks_execution_after_reresolution() -> None:
    harness = Harness()
    control = coordinator(harness)
    preview = await control.preview(target())
    harness.grants = {
        "a": grant(preview, "admin_1"),
        "b": grant(preview, "admin_2"),
    }
    harness.changed = True
    with pytest.raises(DeletionControlError, match="changed"):
        await control.execute(
            preview,
            confirmation=preview.confirmation_text,
            authorization_tokens=(SecretStr("a"), SecretStr("b")),
            idempotency_key="delete-org-1",
        )
    assert harness.executions == 0


@pytest.mark.asyncio
@pytest.mark.parametrize("failure", ("confirmation", "count", "same", "deny", "expired", "binding"))
async def test_authorization_failures_never_execute(failure: str) -> None:
    harness = Harness()
    control = coordinator(harness)
    preview = await control.preview(target())
    second_principal = "admin_1" if failure == "same" else "admin_2"
    changes = {}
    if failure == "deny":
        changes["decision"] = "deny"
    if failure == "expired":
        changes["expires_at"] = NOW
    if failure == "binding":
        changes["resolution_digest"] = "0" * 64
    harness.grants = {
        "a": grant(preview, "admin_1"),
        "b": grant(preview, second_principal, **changes),
    }
    tokens = (SecretStr("a"),) if failure == "count" else (
        SecretStr("a"),
        SecretStr("b"),
    )
    confirmation = "DELETE something else" if failure == "confirmation" else preview.confirmation_text
    with pytest.raises(DeletionControlError):
        await control.execute(
            preview,
            confirmation=confirmation,
            authorization_tokens=tokens,
            idempotency_key="delete-org-1",
        )
    assert harness.executions == 0


@pytest.mark.asyncio
async def test_expired_preview_and_invalid_idempotency_never_execute() -> None:
    harness = Harness()
    later = NOW + timedelta(hours=1)
    current = [NOW]
    control = coordinator(harness, clock=lambda: current[0])
    preview = await control.preview(target())
    harness.grants = {
        "a": grant(preview, "admin_1"),
        "b": grant(preview, "admin_2"),
    }
    current[0] = later
    with pytest.raises(DeletionControlError, match="expired"):
        await control.execute(
            preview,
            confirmation=preview.confirmation_text,
            authorization_tokens=(SecretStr("a"), SecretStr("b")),
            idempotency_key="delete-org-1",
        )
    current[0] = NOW
    with pytest.raises(ValueError, match="idempotency"):
        await control.execute(
            preview,
            confirmation=preview.confirmation_text,
            authorization_tokens=(SecretStr("a"), SecretStr("b")),
            idempotency_key="bad key",
        )
    assert harness.executions == 0


@pytest.mark.asyncio
async def test_non_org_target_still_requires_one_explicit_authorization() -> None:
    harness = Harness()

    async def resolve(_: DeletionTarget) -> ResolvedDeletionTarget:
        return resolved(organization_wide=False)

    control = PermanentDeletionCoordinator(
        resolver=resolve,
        authorization_verifier=harness.verify,
        executor=harness.execute,
        clock=lambda: NOW,
        plan_id_factory=lambda: PLAN_ID,
    )
    preview = await control.preview(target())
    assert preview.required_approvals == 1
    harness.grants = {"a": grant(preview, "admin_1")}
    await control.execute(
        preview,
        confirmation=preview.confirmation_text,
        authorization_tokens=(SecretStr("a"),),
        idempotency_key="delete-org-1",
    )
    assert harness.executions == 1


@pytest.mark.asyncio
async def test_callback_errors_are_sanitized() -> None:
    async def resolver(_: DeletionTarget) -> ResolvedDeletionTarget:
        raise RuntimeError("provider-secret-detail")

    async def unused(*_):
        raise AssertionError

    control = PermanentDeletionCoordinator(
        resolver=resolver,
        authorization_verifier=unused,
        executor=unused,
    )
    with pytest.raises(DeletionControlError, match="resolution") as raised:
        await control.preview(target())
    assert "provider-secret-detail" not in str(raised.value)
