from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest
from pydantic import ValidationError
from zeaz_control.models import ControlStore
from zeaz_control.usage import (
    ControlUsageError,
    CostEvent,
    UsageCostService,
    UsageEvent,
)

NOW = datetime(2026, 7, 26, tzinfo=UTC)


def usage(**changes) -> UsageEvent:
    values = {
        "id": "usage-1",
        "provider": "openai",
        "account": "project-a",
        "model": "gpt-test",
        "input_tokens": 20,
        "output_tokens": 10,
        "source": "provider-response-usage",
        "observed_at": NOW,
    }
    values.update(changes)
    return UsageEvent(**values)


def cost(**changes) -> CostEvent:
    values = {
        "id": "cost-1",
        "usage_event_id": "usage-1",
        "provider": "openai",
        "account": "project-a",
        "model": "gpt-test",
        "amount": "0.000123",
        "currency": "USD",
        "pricing_source": "https://example.invalid/pricing/revision-7",
        "pricing_observed_on": date(2026, 7, 25),
        "observed_at": NOW,
    }
    values.update(changes)
    return CostEvent(**values)


def service(tmp_path: Path) -> tuple[UsageCostService, ControlStore]:
    state = tmp_path / "state"
    state.mkdir(mode=0o700)
    store = ControlStore(state / "control.sqlite3")
    return UsageCostService(store), store


def test_exact_cost_requires_source_date_and_rejects_float() -> None:
    assert cost().amount == Decimal("0.000123")
    for change in (
        {"amount": 0.1},
        {"pricing_source": ""},
        {"pricing_observed_on": None},
        {"currency": "usd"},
    ):
        with pytest.raises(ValidationError):
            cost(**change)


def test_usage_and_cost_are_idempotent_and_transactionally_audited(
    tmp_path: Path,
) -> None:
    ingestion, store = service(tmp_path)
    usage_event = usage()
    cost_event = cost()
    assert ingestion.ingest_usage(usage_event) == usage_event
    assert ingestion.ingest_usage(usage_event) == usage_event
    assert ingestion.ingest_cost(cost_event) == cost_event
    assert ingestion.ingest_cost(cost_event) == cost_event
    assert ingestion.usage() == (usage_event,)
    assert ingestion.costs() == (cost_event,)
    assert [item.event_type for item in store.audit()] == [
        "control.usage.ingested",
        "control.cost.ingested",
    ]
    assert store.audit()[1].details["pricing_observed_on"] == "2026-07-25"


def test_duplicate_ids_with_different_payload_fail(tmp_path: Path) -> None:
    ingestion, _ = service(tmp_path)
    ingestion.ingest_usage(usage())
    with pytest.raises(ControlUsageError, match="conflicts"):
        ingestion.ingest_usage(usage(output_tokens=11))
    ingestion.ingest_cost(cost())
    with pytest.raises(ControlUsageError, match="conflicts"):
        ingestion.ingest_cost(cost(amount="0.50"))


def test_cost_requires_existing_usage_with_matching_scope(tmp_path: Path) -> None:
    ingestion, _ = service(tmp_path)
    with pytest.raises(ControlUsageError, match="unknown usage"):
        ingestion.ingest_cost(cost())
    ingestion.ingest_usage(usage())
    with pytest.raises(ControlUsageError, match="scope"):
        ingestion.ingest_cost(cost(provider="anthropic"))


def test_bounds_and_timezone_are_strict() -> None:
    with pytest.raises(ValidationError):
        usage(input_tokens=-1)
    with pytest.raises(ValidationError):
        usage(observed_at=datetime(2026, 7, 26))
    with pytest.raises(ValidationError):
        cost(amount="1.1234567890123")


def test_extensions_are_isolated_to_provider_namespace() -> None:
    assert usage(extensions={"openai": {"service_tier": "flex"}}).extensions == {
        "openai": {"service_tier": "flex"}
    }
    with pytest.raises(ValidationError, match="provider namespace"):
        usage(extensions={"anthropic": {"service_tier": "priority"}})
    with pytest.raises(ValidationError):
        usage(extensions={"openai": {"Portable Field": "override"}})
