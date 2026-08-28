"""tests/test_zc_compliance_api.py

Covers zc_compliance_api.py: error parsing/retry classification,
exponential backoff on 429/retryable-5xx (never on 400/401/403/404/409),
cursor-safety in the iterate_* generators, the Content-Disposition
filename parser, and the dry-run-by-default guard on every destructive
cmd_* function.
"""
import json

import pytest

from wire.zc_compliance_api import (
    ComplianceApiClient,
    ComplianceApiError,
    _is_retryable,
    _parse_content_disposition_filename,
    cmd_compliance_chat_delete,
    cmd_compliance_file_delete,
    cmd_compliance_project_delete,
)

# ── error classification / retry contract ────────────────────────────────


def test_is_retryable_429_always():
    assert _is_retryable(429, {}) is True


@pytest.mark.parametrize("status", [502, 503, 504, 529])
def test_is_retryable_known_5xx_always(status):
    assert _is_retryable(status, {}) is True


def test_is_retryable_500_depends_on_should_retry_header():
    assert _is_retryable(500, {}) is True
    assert _is_retryable(500, {"x-should-retry": "true"}) is True
    assert _is_retryable(500, {"x-should-retry": "false"}) is False


@pytest.mark.parametrize("status", [400, 401, 403, 404, 409])
def test_never_retryable_client_errors(status):
    assert _is_retryable(status, {}) is False


def test_compliance_api_error_from_response_parses_envelope():
    body = json.dumps({"error": {"type": "not_found_error", "message": "Chat x not found."}}).encode()
    e = ComplianceApiError.from_response(404, body, {"request-id": "req_123"})
    assert e.status == 404
    assert e.error_type == "not_found_error"
    assert e.message == "Chat x not found."
    assert e.request_id == "req_123"
    assert e.retryable is False


def test_compliance_api_error_from_response_tolerates_bad_json():
    e = ComplianceApiError.from_response(500, b"not json", {})
    assert e.error_type == "unknown_error"
    assert e.retryable is True  # 500 with no x-should-retry header defaults retryable


# ── Content-Disposition filename parsing ─────────────────────────────────


def test_parse_content_disposition_extended_form():
    header = "attachment; filename*=utf-8''dashboard_mockup_v1.pdf"
    assert _parse_content_disposition_filename(header) == "dashboard_mockup_v1.pdf"


def test_parse_content_disposition_percent_encoded():
    header = "attachment; filename*=utf-8''report%20Q3%202026.csv"
    assert _parse_content_disposition_filename(header) == "report Q3 2026.csv"


def test_parse_content_disposition_missing_returns_none():
    assert _parse_content_disposition_filename("") is None
    assert _parse_content_disposition_filename("attachment") is None


# ── ComplianceApiClient: retry/backoff behavior ──────────────────────────


class _FakeHTTPError(Exception):
    """Stand-in we raise from a monkeypatched _request to simulate retry
    counting without touching urllib at all."""


def test_request_retries_429_then_succeeds(monkeypatch):
    """Drive retry logic through the real _request() by monkeypatching
    urllib.request.urlopen so we exercise the actual retry loop, not a
    reimplementation of it."""
    import wire.zc_compliance_api as mod

    calls = {"n": 0}
    sleeps = []

    class FakeResp:
        def __init__(self, body):
            self._body = body
            self.headers = {}
        def read(self):
            return self._body
        def __enter__(self):
            return self
        def __exit__(self, *a):
            return False

    def fake_urlopen(req, timeout=None):
        calls["n"] += 1
        if calls["n"] < 3:
            import urllib.error
            raise urllib.error.HTTPError(req.full_url, 429, "rate limited",
                                         {"request-id": "r1"}, None)
        return FakeResp(json.dumps({"data": [], "has_more": False}).encode())

    monkeypatch.setattr(mod.urllib.request, "urlopen", fake_urlopen)
    client = ComplianceApiClient(api_key="k", sleep_fn=lambda s: sleeps.append(s))

    result = client.list_activities(limit=10)

    assert calls["n"] == 3
    assert result == {"data": [], "has_more": False}
    assert sleeps == [1, 2]  # exponential: 2**0, 2**1


def test_request_does_not_retry_403(monkeypatch):
    import wire.zc_compliance_api as mod
    calls = {"n": 0}

    def fake_urlopen(req, timeout=None):
        calls["n"] += 1
        import urllib.error
        body = json.dumps({"error": {"type": "permission_error",
                                     "message": "Missing required scopes."}}).encode()
        raise urllib.error.HTTPError(req.full_url, 403, "forbidden", {}, None).__class__(
            req.full_url, 403, "forbidden", {}, None
        ) if False else _http_error(req.full_url, 403, body)

    def _http_error(url, code, body):
        import io
        import urllib.error
        e = urllib.error.HTTPError(url, code, "forbidden", {}, io.BytesIO(body))
        return e

    monkeypatch.setattr(mod.urllib.request, "urlopen", fake_urlopen)
    client = ComplianceApiClient(api_key="k", sleep_fn=lambda s: (_ for _ in ()).throw(
        AssertionError("must not sleep/retry on 403")))

    with pytest.raises(ComplianceApiError) as exc_info:
        client.list_organizations()

    assert calls["n"] == 1
    assert exc_info.value.status == 403
    assert exc_info.value.error_type == "permission_error"


def test_request_gives_up_after_max_retries(monkeypatch):
    import wire.zc_compliance_api as mod
    calls = {"n": 0}

    def fake_urlopen(req, timeout=None):
        calls["n"] += 1
        import io
        import urllib.error
        body = json.dumps({"error": {"type": "rate_limit_error", "message": "slow down"}}).encode()
        raise urllib.error.HTTPError(req.full_url, 429, "rate limited", {}, io.BytesIO(body))

    monkeypatch.setattr(mod.urllib.request, "urlopen", fake_urlopen)
    client = ComplianceApiClient(api_key="k", max_retries=2, sleep_fn=lambda s: None)

    with pytest.raises(ComplianceApiError) as exc_info:
        client.list_activities()

    assert calls["n"] == 3  # initial attempt + 2 retries
    assert exc_info.value.status == 429


# ── list_chats validation ─────────────────────────────────────────────────


def test_list_chats_requires_user_ids():
    client = ComplianceApiClient(api_key="k")
    with pytest.raises(ValueError):
        client.list_chats(user_ids=[])


def test_list_chats_rejects_over_ten_user_ids():
    client = ComplianceApiClient(api_key="k")
    with pytest.raises(ValueError):
        client.list_chats(user_ids=[f"user_{i}" for i in range(11)])


# ── cursor safety in iterate_activities ───────────────────────────────────


def test_iterate_activities_pages_until_has_more_false(monkeypatch):
    client = ComplianceApiClient(api_key="k")
    pages = [
        {"data": [{"id": "a1"}, {"id": "a2"}], "has_more": True, "last_id": "a2"},
        {"data": [{"id": "a3"}], "has_more": False, "last_id": "a3"},
    ]
    calls = []

    def fake_list_activities(**kwargs):
        calls.append(kwargs.get("after_id"))
        return pages[len(calls) - 1]

    monkeypatch.setattr(client, "list_activities", fake_list_activities)

    items = list(client.iterate_activities())

    assert [i["id"] for i in items] == ["a1", "a2", "a3"]
    assert calls == [None, "a2"]  # cursor only advances after a page is consumed


def test_iterate_activities_stops_on_error_without_yielding_partial_next_page(monkeypatch):
    client = ComplianceApiClient(api_key="k")

    def fake_list_activities(**kwargs):
        if kwargs.get("after_id") is None:
            return {"data": [{"id": "a1"}], "has_more": True, "last_id": "a1"}
        raise ComplianceApiError(status=500, error_type="api_error", message="boom")

    monkeypatch.setattr(client, "list_activities", fake_list_activities)

    gen = client.iterate_activities()
    first = next(gen)
    assert first["id"] == "a1"
    with pytest.raises(ComplianceApiError):
        next(gen)


# ── destructive cmd_* functions: dry-run by default ──────────────────────


def test_cmd_chat_delete_dry_run_makes_no_client_call(monkeypatch, capsys):
    def boom(*a, **kw):
        raise AssertionError("must not construct a client without --compliance-yes")
    monkeypatch.setattr("wire.zc_compliance_api.ComplianceApiClient", boom)

    result = cmd_compliance_chat_delete("k", "zc_chat_1")

    assert result is None
    out = capsys.readouterr().out
    assert "DRY RUN" in out
    assert "zc_chat_1" in out


def test_cmd_file_delete_dry_run_makes_no_client_call(monkeypatch, capsys):
    def boom(*a, **kw):
        raise AssertionError("must not construct a client without --compliance-yes")
    monkeypatch.setattr("wire.zc_compliance_api.ComplianceApiClient", boom)

    result = cmd_compliance_file_delete("k", "zc_file_1")

    assert result is None
    assert "DRY RUN" in capsys.readouterr().out


def test_cmd_project_delete_dry_run_makes_no_client_call(monkeypatch, capsys):
    def boom(*a, **kw):
        raise AssertionError("must not construct a client without --compliance-yes")
    monkeypatch.setattr("wire.zc_compliance_api.ComplianceApiClient", boom)

    result = cmd_compliance_project_delete("k", "zc_proj_1")

    assert result is None
    assert "DRY RUN" in capsys.readouterr().out


def test_cmd_chat_delete_with_yes_calls_client(monkeypatch, capsys):
    class FakeClient:
        def __init__(self, api_key):
            pass
        def delete_chat(self, chat_id):
            return {"id": chat_id, "type": "zc_chat_deleted"}

    monkeypatch.setattr("wire.zc_compliance_api.ComplianceApiClient", FakeClient)

    result = cmd_compliance_chat_delete("k", "zc_chat_1", yes=True)

    assert result == {"id": "zc_chat_1", "type": "zc_chat_deleted"}
    assert "Deleted chat" in capsys.readouterr().out


def test_cmd_project_delete_with_yes_surfaces_409_hint(monkeypatch, capsys):
    class FakeClient:
        def __init__(self, api_key):
            pass
        def delete_project(self, project_id):
            raise ComplianceApiError(status=409, error_type="conflict_error",
                                     message="has chats attached")

    monkeypatch.setattr("wire.zc_compliance_api.ComplianceApiClient", FakeClient)

    result = cmd_compliance_project_delete("k", "zc_proj_1", yes=True)

    assert result is None
    out = capsys.readouterr().out
    assert "still has chats attached" in out