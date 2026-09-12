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
