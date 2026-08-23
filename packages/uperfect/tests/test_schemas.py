from decimal import Decimal

from app.schemas import DomainError, decimal_json, decimal_value, parse_json_object


def test_decimal_helpers_preserve_currency_and_browser_shape():
    assert decimal_value("169") == Decimal("169.00")
    assert decimal_value("") is None
    assert decimal_json(Decimal("169.00")) == 169
    assert decimal_json(Decimal("169.50")) == 169.5


def test_domain_error_exposes_stable_metadata_and_invalid_json_is_empty():
    error = DomainError("bad", code="BAD_INPUT", http_status=422)

    assert error.code == "BAD_INPUT"
    assert error.http_status == 422
    assert parse_json_object("not-json") == {}
