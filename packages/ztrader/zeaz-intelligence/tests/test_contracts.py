from __future__ import annotations

import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator, ValidationError

CONTRACT = (
    Path(__file__).resolve().parents[1]
    / "contracts"
    / "ztrader-advisory-intent.v1.schema.json"
)


def _schema() -> dict[str, object]:
    return json.loads(CONTRACT.read_text(encoding="utf-8"))


def _valid_payload() -> dict[str, object]:
    return {
        "version": "1.0",
        "tenant_id": "tenant-demo",
        "account_ref": "paper-account-1",
        "portfolio_ref": "portfolio-alpha",
        "signal_id": "signal-001",
        "trace_id": "trace-001",
        "symbol": "TOKEN",
        "chain": "base",
        "address": "0x1111111111111111111111111111111111111111",
        "scores": {"opportunity": 75, "risk": 30, "confidence": 80},
        "narrative": "EARLY",
        "whales": "ACCUMULATING",
        "rug_risk": "LOW",
        "action": "WATCH",
        "evidence_timestamp": "2026-09-12T11:00:00Z",
        "invalidations": ["risk score >= 55"],
        "proposed_trade": {
            "mode": "paper",
            "entry_low": 1.0,
            "entry_high": 1.1,
            "stop_loss": 0.9,
            "take_profit_levels": [1.3, 1.5],
            "max_position_usd": 100.0,
        },
        "evidence": {"source": "test-fixture"},
    }


def test_advisory_contract_is_valid_draft_2020_12_schema() -> None:
    Draft202012Validator.check_schema(_schema())


def test_advisory_contract_accepts_tenant_scoped_paper_intent() -> None:
    Draft202012Validator(_schema()).validate(_valid_payload())


@pytest.mark.parametrize(
    "field",
    ["tenant_id", "account_ref", "chain", "address"],
)
def test_advisory_contract_rejects_missing_identity(field: str) -> None:
    payload = _valid_payload()
    payload.pop(field)
    with pytest.raises(ValidationError):
        Draft202012Validator(_schema()).validate(payload)


def test_advisory_contract_rejects_live_execution_mode() -> None:
    payload = _valid_payload()
    payload["proposed_trade"]["mode"] = "live"  # type: ignore[index]
    with pytest.raises(ValidationError):
        Draft202012Validator(_schema()).validate(payload)


ADVISORY_V11 = (
    Path(__file__).resolve().parents[1]
    / "contracts"
    / "ztrader-advisory-intent.v1.1.schema.json"
)
ONCHAIN_V1 = (
    Path(__file__).resolve().parents[1]
    / "contracts"
    / "ztrader-onchain-evidence.v1.schema.json"
)
MODEL_GATEWAY_V1 = (
    Path(__file__).resolve().parents[1]
    / "contracts"
    / "ztrader-model-gateway.v1.schema.json"
)


@pytest.mark.parametrize("contract", [ADVISORY_V11, ONCHAIN_V1, MODEL_GATEWAY_V1])
def test_new_canonical_contracts_are_valid_draft_2020_12(contract: Path) -> None:
    schema = json.loads(contract.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)


def test_advisory_v11_requires_paper_limit_execution_fields() -> None:
    schema = json.loads(ADVISORY_V11.read_text(encoding="utf-8"))
    payload = _valid_payload()
    payload["version"] = "1.1"
    payload["proposed_trade"] = {
        **payload["proposed_trade"],  # type: ignore[arg-type]
        "side": "buy",
        "order_type": "limit",
        "max_position_usd": 100.0,
    }
    Draft202012Validator(schema).validate(payload)

    payload["proposed_trade"]["mode"] = "live"  # type: ignore[index]
    with pytest.raises(ValidationError):
        Draft202012Validator(schema).validate(payload)


def test_onchain_contract_accepts_explicit_unavailable_evidence() -> None:
    schema = json.loads(ONCHAIN_V1.read_text(encoding="utf-8"))
    payload = {
        "version": "1.0",
        "trace_id": "trace-001",
        "chain": "ethereum",
        "address": "0x1111111111111111111111111111111111111111",
        "observed_at": "2026-09-12T11:00:00Z",
        "freshness_seconds": 0,
        "quality": "UNAVAILABLE",
        "sources": [
            {
                "provider": "zwallet:collector-status",
                "reference": None,
                "observed_at": "2026-09-12T11:00:00Z",
            }
        ],
        "evidence": {},
    }
    Draft202012Validator(schema).validate(payload)


def test_model_gateway_contract_forbids_server_side_storage() -> None:
    schema = json.loads(MODEL_GATEWAY_V1.read_text(encoding="utf-8"))
    payload = {
        "version": "1.0",
        "trace_id": "trace-001",
        "task_class": "narrative_summary",
        "model": "provider/model",
        "input": "supplied evidence only",
        "store": False,
        "data_sensitivity": "PUBLIC",
    }
    Draft202012Validator(schema).validate(payload)
    payload["store"] = True
    with pytest.raises(ValidationError):
        Draft202012Validator(schema).validate(payload)
