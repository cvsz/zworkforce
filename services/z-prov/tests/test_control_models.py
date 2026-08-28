from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from zeaz_control.models import (
    ControlStore,
    DiscoveredModel,
    ModelLifecycle,
    ModelPage,
    ModelReconciler,
)

NOW = datetime(2026, 7, 26, tzinfo=UTC)


class ScriptedAdapter:
    provider = "openai"
    account = "project-a"
    region = "us"

    def __init__(self, pages: list[ModelPage]) -> None:
        self.pages = pages
        self.calls: list[tuple[str | None, int]] = []

    async def list_models(self, *, cursor, limit) -> ModelPage:
        self.calls.append((cursor, limit))
        return self.pages.pop(0)


def model(
    name: str,
    *,
    lifecycle: ModelLifecycle = ModelLifecycle.ACTIVE,
    observed_at: datetime = NOW,
) -> DiscoveredModel:
    return DiscoveredModel(
        provider="openai",
        account="project-a",
        region="us",
        model=name,
        lifecycle=lifecycle,
        capabilities={"tools": True, "context_window": 128_000},
        source="provider_models_api",
        observed_at=observed_at,
        extensions={"openai": {"owned_by": "system"}},
    )


def store(tmp_path: Path) -> ControlStore:
    state = tmp_path / "control-state"
    state.mkdir(mode=0o700)
    return ControlStore(state / "control.sqlite3")


@pytest.mark.asyncio
async def test_paginated_discovery_is_transactionally_reconciled(tmp_path: Path) -> None:
    control = store(tmp_path)
    adapter = ScriptedAdapter(
        [
            ModelPage(items=(model("gpt-a"),), next_cursor="cursor-1"),
            ModelPage(items=(model("gpt-b"),)),
        ]
    )
    result = await ModelReconciler(control, page_size=1).refresh(adapter, now=NOW)
    assert result.discovered == 2
    assert result.created == 2
    assert [item.model for item in control.models()] == ["gpt-a", "gpt-b"]
    assert adapter.calls == [(None, 1), ("cursor-1", 1)]
    audit = control.audit()
    assert len(audit) == 1
    assert audit[0].event_type == "control.models.reconciled"
    assert audit[0].details["created"] == 2


@pytest.mark.asyncio
async def test_unchanged_refresh_does_not_increment_revision(tmp_path: Path) -> None:
    control = store(tmp_path)
    reconciler = ModelReconciler(control)
    await reconciler.refresh(ScriptedAdapter([ModelPage(items=(model("gpt-a"),))]), now=NOW)
    result = await reconciler.refresh(
        ScriptedAdapter([ModelPage(items=(model("gpt-a"),))]),
        now=NOW + timedelta(minutes=1),
    )
    record = control.models()[0]
    assert result.unchanged == 1
    assert record.revision == 1
    assert record.reconciled_at == NOW + timedelta(minutes=1)


@pytest.mark.asyncio
async def test_missing_model_requires_repeated_observations_before_retirement(
    tmp_path: Path,
) -> None:
    control = store(tmp_path)
    reconciler = ModelReconciler(control, retire_after_missing=2)
    await reconciler.refresh(ScriptedAdapter([ModelPage(items=(model("gpt-a"),))]), now=NOW)
    first = await reconciler.refresh(
        ScriptedAdapter([ModelPage(items=())]),
        now=NOW + timedelta(minutes=1),
    )
    record = control.models()[0]
    assert first.missing == 1
    assert first.retired == 0
    assert record.lifecycle is ModelLifecycle.ACTIVE
    assert record.missing_observations == 1

    second = await reconciler.refresh(
        ScriptedAdapter([ModelPage(items=())]),
        now=NOW + timedelta(minutes=2),
    )
    record = control.models()[0]
    assert second.retired == 1
    assert record.lifecycle is ModelLifecycle.RETIRED
    assert record.missing_observations == 2


@pytest.mark.asyncio
async def test_reappearing_model_reactivates_and_increments_revision(tmp_path: Path) -> None:
    control = store(tmp_path)
    reconciler = ModelReconciler(control, retire_after_missing=1)
    await reconciler.refresh(ScriptedAdapter([ModelPage(items=(model("gpt-a"),))]), now=NOW)
    await reconciler.refresh(
        ScriptedAdapter([ModelPage(items=())]),
        now=NOW + timedelta(minutes=1),
    )
    result = await reconciler.refresh(
        ScriptedAdapter(
            [
                ModelPage(
                    items=(
                        model(
                            "gpt-a",
                            lifecycle=ModelLifecycle.ACTIVE,
                            observed_at=NOW + timedelta(minutes=2),
                        ),
                    )
                )
            ]
        ),
        now=NOW + timedelta(minutes=2),
    )
    assert result.updated == 1
    assert control.models()[0].lifecycle is ModelLifecycle.ACTIVE
    assert control.models()[0].revision == 3


@pytest.mark.asyncio
@pytest.mark.parametrize("failure", ("duplicate", "cursor", "pages", "items", "scope"))
async def test_malformed_or_excessive_discovery_never_partially_commits(
    tmp_path: Path,
    failure: str,
) -> None:
    control = store(tmp_path)
    if failure == "duplicate":
        pages = [ModelPage(items=(model("same"), model("same")))]
        reconciler = ModelReconciler(control)
    elif failure == "cursor":
        pages = [
            ModelPage(items=(model("a"),), next_cursor="repeat"),
            ModelPage(items=(model("b"),), next_cursor="repeat"),
        ]
        reconciler = ModelReconciler(control)
    elif failure == "pages":
        pages = [ModelPage(items=(), next_cursor=f"c-{index}") for index in range(2)]
        reconciler = ModelReconciler(control, max_pages=2)
    elif failure == "items":
        pages = [ModelPage(items=(model("a"), model("b")))]
        reconciler = ModelReconciler(control, page_size=1, max_models=1)
    else:
        wrong = model("a").model_copy(
            update={"provider": "anthropic", "extensions": {"anthropic": {}}}
        )
        pages = [ModelPage(items=(wrong,))]
        reconciler = ModelReconciler(control)
    with pytest.raises((RuntimeError, ValueError)):
        await reconciler.refresh(ScriptedAdapter(pages), now=NOW)
    assert control.models() == ()
    assert control.audit() == ()


def test_control_database_requires_private_real_paths(tmp_path: Path) -> None:
    public = tmp_path / "public"
    public.mkdir(mode=0o755)
    with pytest.raises(ValueError, match="private"):
        ControlStore(public / "control.sqlite3")
    private = tmp_path / "private"
    private.mkdir(mode=0o700)
    target = private / "target"
    target.write_bytes(b"")
    link = private / "link"
    link.symlink_to(target)
    with pytest.raises(ValueError, match="private regular"):
        ControlStore(link)
