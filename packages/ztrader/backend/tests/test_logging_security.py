"""Regression tests for secure logging and error responses."""

from ztrader.core.logging_utils import sanitize_log_value


def test_sanitize_log_value_escapes_control_characters_and_bounds_length():
    value = "BTCUSDT\r\nforged-entry" + ("x" * 300)

    sanitized = sanitize_log_value(value)

    assert "\r" not in sanitized
    assert "\n" not in sanitized
    assert "\\r\\n" in sanitized
    assert len(sanitized) == 256
