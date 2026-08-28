"""tests/test_logging_config.py"""
import logging

from wire.logging_config import JsonFormatter, correlation_id, new_correlation_id, redact


def test_redact_scrubs_api_key():
    text = "using key sk-ant-abcdef1234567890abcdefg for the call"
    assert "sk-ant" not in redact(text)
    assert "[REDACTED]" in redact(text)


def test_redact_leaves_normal_text_untouched():
    text = "the model returned a normal response"
    assert redact(text) == text


def test_new_correlation_id_is_unique():
    a = new_correlation_id()
    b = new_correlation_id()
    assert a != b
    assert correlation_id.get() == b


def test_json_formatter_includes_correlation_id():
    new_correlation_id()
    record = logging.LogRecord(
        name="wire.test", level=logging.INFO, pathname=__file__,
        lineno=1, msg="hello", args=(), exc_info=None,
    )
    out = JsonFormatter().format(record)
    assert '"correlation_id"' in out
    assert '"message": "hello"' in out
