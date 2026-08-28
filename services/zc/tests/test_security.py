"""tests/test_security.py"""
import pytest

from wire.exceptions import SecurityError, ValidationError
from wire.security import (
    assert_no_secret,
    contains_secret,
    env_flag,
    safe_resolve,
    validate_name,
    validate_url,
)


def test_safe_resolve_allows_path_inside_base(tmp_path):
    result = safe_resolve("sub/file.txt", tmp_path)
    assert str(result).startswith(str(tmp_path))


def test_safe_resolve_blocks_traversal(tmp_path):
    with pytest.raises(SecurityError):
        safe_resolve("../../etc/passwd", tmp_path)


def test_safe_resolve_blocks_absolute_escape(tmp_path):
    with pytest.raises(SecurityError):
        safe_resolve("/etc/passwd", tmp_path)


@pytest.mark.parametrize("name", ["my-project", "Project 1", "notes.md", "a_b.c"])
def test_validate_name_accepts_safe_names(name):
    assert validate_name(name) == name


@pytest.mark.parametrize("name", ["../etc", "a/b", "a\\b", "", "x" * 300])
def test_validate_name_rejects_unsafe_names(name):
    with pytest.raises(ValidationError):
        validate_name(name)


def test_validate_url_allows_https():
    validate_url("https://api.anthropic.com/v1/messages")  # no raise


@pytest.mark.parametrize("url", [
    "http://example.com",
    "file:///etc/passwd",
    "javascript:alert(1)",
    "ftp://example.com/file",
])
def test_validate_url_rejects_unsafe_schemes(url):
    with pytest.raises(SecurityError):
        validate_url(url)


def test_contains_secret_detects_api_key():
    assert contains_secret("here is sk-ant-abcdef1234567890 for you") is True


def test_contains_secret_false_for_clean_text():
    assert contains_secret("just a normal sentence") is False


def test_assert_no_secret_raises_on_key():
    with pytest.raises(SecurityError):
        assert_no_secret("key: sk-ant-abcdef1234567890abcdef")


def test_env_flag_parses_truthy_values(monkeypatch):
    for val in ("1", "true", "True", "yes", "on"):
        monkeypatch.setenv("wire_TEST_FLAG", val)
        assert env_flag("wire_TEST_FLAG") is True


def test_env_flag_defaults_when_unset(monkeypatch):
    monkeypatch.delenv("wire_TEST_FLAG", raising=False)
    assert env_flag("wire_TEST_FLAG", default=True) is True
    assert env_flag("wire_TEST_FLAG", default=False) is False
