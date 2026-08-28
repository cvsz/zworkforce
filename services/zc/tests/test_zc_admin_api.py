"""tests/test_zc_admin_api.py

Covers zc_admin_api.py: the Usage/Cost report query building and
default date range, the 401/403 admin-key-required error hint, API key
revoke (status -> inactive, no delete endpoint), and that
--admin-create-key is a pure explanation with no network call.
"""


from wire.zc_admin_api import (
    AdminApiClient,
    _default_date_range,
    cmd_admin_create_key,
    cmd_admin_list_keys,
    cmd_admin_revoke_key,
    cmd_cost_report,
    cmd_rate_limits,
    cmd_rate_limits_workspace,
    cmd_usage_report,
)

# ── AdminApiClient query building ────────────────────────────────────────


def test_get_usage_report_builds_expected_params(monkeypatch):
    client = AdminApiClient(admin_api_key="admin-k")
    captured = {}
    monkeypatch.setattr(client, "_get", lambda path, params=None: (
        captured.update(path=path, params=params) or {"data": []}
    ))

    client.get_usage_report("2026-06-01", "2026-07-01", group_by="api_key_id")

    assert captured["path"] == "/usage_report"
    assert captured["params"] == {
        "starting_at": "2026-06-01", "ending_at": "2026-07-01",
        "group_by": "api_key_id",
    }


def test_get_cost_report_builds_expected_params(monkeypatch):
    client = AdminApiClient(admin_api_key="admin-k")
    captured = {}
    monkeypatch.setattr(client, "_get", lambda path, params=None: (
        captured.update(path=path, params=params) or {"data": []}
    ))

    client.get_cost_report("2026-06-01", "2026-07-01")

    assert captured["path"] == "/cost_report"
    assert captured["params"]["group_by"] == "model"


def test_revoke_api_key_sets_status_inactive_not_delete(monkeypatch):
    client = AdminApiClient(admin_api_key="admin-k")
    captured = {}
    monkeypatch.setattr(client, "_post", lambda path, payload: (
        captured.update(path=path, payload=payload) or {"id": "key_1", "status": "inactive"}
    ))

    client.revoke_api_key("key_1")

    assert captured["path"] == "/api_keys/key_1"
    assert captured["payload"] == {"status": "inactive"}


def test_default_date_range_is_30_days():
    start, end = _default_date_range()
    from datetime import date
    d1 = date.fromisoformat(start)
    d2 = date.fromisoformat(end)
    assert (d2 - d1).days == 30


# ── cmd_* error handling / admin-key hint ────────────────────────────────


def test_cmd_usage_report_prints_admin_key_hint_on_403(monkeypatch, capsys):
    client = AdminApiClient(admin_api_key="regular-looking-key")
    monkeypatch.setattr(
        "wire.zc_admin_api.AdminApiClient",
        lambda admin_api_key: client,
    )
    monkeypatch.setattr(client, "get_usage_report",
                        lambda start, end, group_by="model": {"error": "forbidden", "status": 403})

    result = cmd_usage_report("regular-looking-key")

    assert result is None
    out = capsys.readouterr().out
    assert "Admin API key" in out


def test_cmd_cost_report_prints_rows(monkeypatch, capsys):
    client = AdminApiClient(admin_api_key="k")
    monkeypatch.setattr("wire.zc_admin_api.AdminApiClient", lambda admin_api_key: client)
    monkeypatch.setattr(client, "get_cost_report",
                        lambda start, end, group_by="model": {
                            "data": [{"model": "zc-xxx", "amount": "12.50", "currency": "usd"}]
                        })

    result = cmd_cost_report("k", start="2026-06-01", end="2026-07-01")

    assert result["data"][0]["amount"] == "12.50"
    out = capsys.readouterr().out
    assert "zc-xxx" in out
    assert "12.50" in out


def test_cmd_admin_list_keys_prints_each_key(monkeypatch, capsys):
    client = AdminApiClient(admin_api_key="k")
    monkeypatch.setattr("wire.zc_admin_api.AdminApiClient", lambda admin_api_key: client)
    monkeypatch.setattr(client, "list_api_keys", lambda limit=20: {
        "data": [{"id": "key_1", "name": "prod", "status": "active"}]
    })

    result = cmd_admin_list_keys("k")

    assert result["data"][0]["id"] == "key_1"
    out = capsys.readouterr().out
    assert "key_1" in out and "active" in out


def test_cmd_admin_revoke_key_success_message(monkeypatch, capsys):
    client = AdminApiClient(admin_api_key="k")
    monkeypatch.setattr("wire.zc_admin_api.AdminApiClient", lambda admin_api_key: client)
    monkeypatch.setattr(client, "revoke_api_key", lambda key_id: {"id": key_id, "status": "inactive"})

    result = cmd_admin_revoke_key("k", "key_1")

    assert result["status"] == "inactive"
    out = capsys.readouterr().out
    assert "key_1" in out


def test_cmd_admin_revoke_key_error(monkeypatch, capsys):
    client = AdminApiClient(admin_api_key="k")
    monkeypatch.setattr("wire.zc_admin_api.AdminApiClient", lambda admin_api_key: client)
    monkeypatch.setattr(client, "revoke_api_key", lambda key_id: {"error": "not found"})

    result = cmd_admin_revoke_key("k", "ghost")

    assert result is None
    out = capsys.readouterr().out
    assert "Failed to revoke" in out


# ── --admin-create-key: explanation only, no network ────────────────────


def test_cmd_admin_create_key_makes_no_network_call(monkeypatch, capsys):
    def boom(*a, **kw):
        raise AssertionError("cmd_admin_create_key must not touch the network")

    monkeypatch.setattr("wire.zc_admin_api.AdminApiClient", boom)

    result = cmd_admin_create_key("my-new-key")

    assert result is None
    out = capsys.readouterr().out
    assert "no documented create-key endpoint" in out
    assert "my-new-key" in out


# ── v1.23.0: Rate Limits API (read-only) ─────────────────────────────────


def test_get_org_rate_limits_omits_model_by_default(monkeypatch):
    client = AdminApiClient(admin_api_key="admin-k")
    captured = {}
    monkeypatch.setattr(client, "_get", lambda path, params=None: (
        captured.update(path=path, params=params) or {"data": []}
    ))

    client.get_org_rate_limits()

    assert captured["path"] == "/rate_limits"
    assert captured["params"] is None


def test_get_org_rate_limits_includes_model_when_given(monkeypatch):
    client = AdminApiClient(admin_api_key="admin-k")
    captured = {}
    monkeypatch.setattr(client, "_get", lambda path, params=None: (
        captured.update(path=path, params=params) or {"data": []}
    ))

    client.get_org_rate_limits(model="zc-opus-4-8")

    assert captured["params"] == {"model": "zc-opus-4-8"}


def test_get_workspace_rate_limits_builds_path(monkeypatch):
    client = AdminApiClient(admin_api_key="admin-k")
    captured = {}
    monkeypatch.setattr(client, "_get", lambda path, params=None: (
        captured.update(path=path) or {"data": []}
    ))

    client.get_workspace_rate_limits("wrkspc_1")

    assert captured["path"] == "/workspaces/wrkspc_1/rate_limits"


def test_cmd_rate_limits_prints_value_and_org_limit(monkeypatch, capsys):
    client_data = {"data": [{"model_group": "opus", "limits": [
        {"type": "requests_per_minute", "value": 4000},
    ]}]}
    monkeypatch.setattr(AdminApiClient, "get_org_rate_limits", lambda self, model=None: client_data)

    cmd_rate_limits("admin-k")

    out = capsys.readouterr().out
    assert "opus" in out
    assert "requests_per_minute" in out


def test_cmd_rate_limits_workspace_shows_value_and_org_limit(monkeypatch, capsys):
    client_data = {"data": [{"model_group": "opus", "limits": [
        {"type": "requests_per_minute", "value": 1000, "org_limit": 4000},
    ]}]}
    monkeypatch.setattr(AdminApiClient, "get_workspace_rate_limits",
                        lambda self, workspace_id: client_data)

    cmd_rate_limits_workspace("wrkspc_1", "admin-k")

    out = capsys.readouterr().out
    assert "1000" in out and "4000" in out


def test_cmd_rate_limits_workspace_no_overrides_message(monkeypatch, capsys):
    monkeypatch.setattr(AdminApiClient, "get_workspace_rate_limits",
                        lambda self, workspace_id: {"data": []})

    cmd_rate_limits_workspace("wrkspc_1", "admin-k")

    assert "no overrides" in capsys.readouterr().out


# ── v1.23.0: Spend Limits API (zAICoder Enterprise only) ───────────────────


def test_list_effective_spend_limits_builds_expected_params(monkeypatch):
    client = AdminApiClient(admin_api_key="admin-k")
    captured = {}
    monkeypatch.setattr(client, "_get", lambda path, params=None: (
        captured.update(path=path, params=params) or {"data": []}
    ))

    client.list_effective_spend_limits(limit=25)

    assert captured["path"] == "/spend_limits/effective"
    assert captured["params"]["limit"] == 25


def test_set_spend_limit_omits_suppress_notification_by_default(monkeypatch):
    client = AdminApiClient(admin_api_key="admin-k")
    captured = {}
    monkeypatch.setattr(client, "_post", lambda path, payload: (
        captured.update(path=path, payload=payload) or {}
    ))

    client.set_spend_limit("user_1", "5000")

    assert captured["payload"] == {"user_id": "user_1", "amount": "5000"}


def test_set_spend_limit_includes_suppress_notification_when_true(monkeypatch):
    client = AdminApiClient(admin_api_key="admin-k")
    captured = {}
    monkeypatch.setattr(client, "_post", lambda path, payload: (
        captured.update(payload=payload) or {}
    ))

    client.set_spend_limit("user_1", "5000", suppress_notification=True)

    assert captured["payload"]["suppress_notification"] is True


def test_delete_spend_limit_uses_delete_verb(monkeypatch):
    client = AdminApiClient(admin_api_key="admin-k")
    captured = {}
    monkeypatch.setattr(client, "_delete", lambda path: (
        captured.update(path=path) or {"deleted": True}
    ))

    result = client.delete_spend_limit("spl_1")

    assert captured["path"] == "/spend_limits/spl_1"
    assert result == {"deleted": True}


def test_list_spend_limit_increase_requests_filters_by_status(monkeypatch):
    client = AdminApiClient(admin_api_key="admin-k")
    captured = {}
    monkeypatch.setattr(client, "_get", lambda path, params=None: (
        captured.update(path=path, params=params) or {"data": []}
    ))

    client.list_spend_limit_increase_requests(status=["pending"])

    assert captured["params"]["status[]"] == ["pending"]


def test_list_spend_limit_increase_requests_omits_status_when_not_given(monkeypatch):
    client = AdminApiClient(admin_api_key="admin-k")
    captured = {}
    monkeypatch.setattr(client, "_get", lambda path, params=None: (
        captured.update(params=params) or {"data": []}
    ))

    client.list_spend_limit_increase_requests()

    assert "status[]" not in captured["params"]


def test_approve_spend_limit_increase_request_path_and_payload(monkeypatch):
    client = AdminApiClient(admin_api_key="admin-k")
    captured = {}
    monkeypatch.setattr(client, "_post", lambda path, payload: (
        captured.update(path=path, payload=payload) or {}
    ))

    client.approve_spend_limit_increase_request("req_1")

    assert captured["path"] == "/spend_limit_increase_requests/req_1/approve"
    assert captured["payload"] == {}


def test_deny_spend_limit_increase_request_with_suppress(monkeypatch):
    client = AdminApiClient(admin_api_key="admin-k")
    captured = {}
    monkeypatch.setattr(client, "_post", lambda path, payload: (
        captured.update(path=path, payload=payload) or {}
    ))

    client.deny_spend_limit_increase_request("req_1", suppress_notification=True)

    assert captured["path"] == "/spend_limit_increase_requests/req_1/deny"
    assert captured["payload"] == {"suppress_notification": True}


def test_cmd_spend_limits_list_prints_rows(monkeypatch, capsys):
    from wire.zc_admin_api import cmd_spend_limits_list
    monkeypatch.setattr(AdminApiClient, "list_effective_spend_limits", lambda self, limit=50, page=None: {
        "data": [{"user_id": "user_1", "amount": "5000", "source": "group",
                 "period_to_date_spend": "1200"}],
    })

    cmd_spend_limits_list("admin-k")

    out = capsys.readouterr().out
    assert "user_1" in out and "5000" in out


def test_cmd_spend_limits_list_enterprise_hint_on_403(monkeypatch, capsys):
    from wire.zc_admin_api import cmd_spend_limits_list
    monkeypatch.setattr(AdminApiClient, "list_effective_spend_limits",
                        lambda self, limit=50, page=None: {"error": "forbidden", "status": 403})

    cmd_spend_limits_list("admin-k")

    out = capsys.readouterr().out
    assert "Enterprise" in out


def test_cmd_spend_limit_set_success_message(monkeypatch, capsys):
    from wire.zc_admin_api import cmd_spend_limit_set
    monkeypatch.setattr(AdminApiClient, "set_spend_limit",
                        lambda self, user_id, amount, suppress_notification=False: {"id": "spl_1"})

    cmd_spend_limit_set("user_1", "5000", "admin-k")

    out = capsys.readouterr().out
    assert "user_1" in out and "5000" in out


def test_cmd_spend_limit_delete_success_message(monkeypatch, capsys):
    from wire.zc_admin_api import cmd_spend_limit_delete
    monkeypatch.setattr(AdminApiClient, "delete_spend_limit",
                        lambda self, spend_limit_id: {"deleted": True})

    cmd_spend_limit_delete("spl_1", "admin-k")

    assert "spl_1" in capsys.readouterr().out


def test_cmd_spend_limit_requests_list_passes_single_status_filter(monkeypatch, capsys):
    from wire.zc_admin_api import cmd_spend_limit_requests_list
    captured = {}
    monkeypatch.setattr(AdminApiClient, "list_spend_limit_increase_requests",
                        lambda self, status=None, actor_ids=None, limit=50, page=None: (
                            captured.update(status=status) or {"data": []}
                        ))

    cmd_spend_limit_requests_list("admin-k", status="pending")

    assert captured["status"] == ["pending"]


def test_cmd_spend_limit_request_approve_and_deny(monkeypatch, capsys):
    from wire.zc_admin_api import cmd_spend_limit_request_approve, cmd_spend_limit_request_deny
    monkeypatch.setattr(AdminApiClient, "approve_spend_limit_increase_request",
                        lambda self, request_id, suppress_notification=False: {"id": request_id})
    monkeypatch.setattr(AdminApiClient, "deny_spend_limit_increase_request",
                        lambda self, request_id, suppress_notification=False: {"id": request_id})

    cmd_spend_limit_request_approve("req_1", "admin-k")
    cmd_spend_limit_request_deny("req_2", "admin-k")

    out = capsys.readouterr().out
    assert "req_1" in out and "approved" in out
    assert "req_2" in out and "denied" in out


# ── v1.24.0: zAICoder Analytics API ────────────────────────────────────


def test_get_zc_code_usage_report_builds_expected_params(monkeypatch):
    client = AdminApiClient(admin_api_key="admin-k")
    captured = {}
    monkeypatch.setattr(client, "_get", lambda path, params=None: (
        captured.update(path=path, params=params) or {"data": []}
    ))

    client.get_zc_code_usage_report("2026-07-08", limit=15)

    assert captured["path"] == "/usage_report/zc_code"
    assert captured["params"] == {"starting_at": "2026-07-08", "limit": 15, "page": None}


def test_get_zc_code_usage_report_passes_page_cursor(monkeypatch):
    client = AdminApiClient(admin_api_key="admin-k")
    captured = {}
    monkeypatch.setattr(client, "_get", lambda path, params=None: (
        captured.update(path=path, params=params) or {"data": []}
    ))

    client.get_zc_code_usage_report("2026-07-08", page="page_abc123")

    assert captured["params"]["page"] == "page_abc123"


def test_cmd_zc_code_usage_report_prints_wrong_key_hint(monkeypatch, capsys):
    AdminApiClient(admin_api_key="admin-k")
    monkeypatch.setattr(AdminApiClient, "get_zc_code_usage_report",
                        lambda self, *a, **k: {"error": "forbidden", "status": 403})
    from wire.zc_admin_api import cmd_zc_code_usage_report

    result = cmd_zc_code_usage_report("regular-key", "2026-07-08")

    assert result is None
    out = capsys.readouterr().out
    assert "Admin API key" in out


def test_cmd_zc_code_usage_report_handles_missing_optional_fields(monkeypatch, capsys):
    monkeypatch.setattr(AdminApiClient, "get_zc_code_usage_report",
                        lambda self, *a, **k: {"data": [
                            {"date": "2026-07-08T00:00:00Z", "api_actor": {"api_key_name": "ci-key"}},
                        ]})
    from wire.zc_admin_api import cmd_zc_code_usage_report

    result = cmd_zc_code_usage_report("admin-k", "2026-07-08")

    assert result is not None
    out = capsys.readouterr().out
    assert "ci-key" in out


def test_cmd_zc_code_usage_report_prints_named_user_and_metrics(monkeypatch, capsys):
    monkeypatch.setattr(AdminApiClient, "get_zc_code_usage_report",
                        lambda self, *a, **k: {"data": [{
                            "date": "2026-07-08T00:00:00Z",
                            "user_actor": {"email_address": "[email protected]"},
                            "core_metrics": {
                                "num_sessions": 5,
                                "lines_of_code": {"added": 100, "removed": 20},
                                "commits_by_zc_code": 3,
                                "pull_requests_by_zc_code": 1,
                            },
                            "model_breakdown": [
                                {"model": "zc-opus-4-8",
                                 "estimated_cost": {"currency": "USD", "amount": 1025}},
                            ],
                        }]})
    from wire.zc_admin_api import cmd_zc_code_usage_report

    cmd_zc_code_usage_report("admin-k", "2026-07-08")

    out = capsys.readouterr().out
    assert "[em***ed]" in out
    assert "sessions=5" in out
    assert "cost=1025" in out


# ── v1.24.0: API key expires_at surfaced ──────────────────────────────────


def test_cmd_admin_list_keys_prints_expires_at(monkeypatch, capsys):
    monkeypatch.setattr(AdminApiClient, "list_api_keys",
                        lambda self, limit=20: {"data": [
                            {"id": "key_1", "name": "prod", "status": "active",
                             "expires_at": "2026-12-01T00:00:00Z"},
                        ]})

    cmd_admin_list_keys("admin-k")

    out = capsys.readouterr().out
    assert "2026-12-01T00:00:00Z" in out


def test_cmd_admin_list_keys_prints_placeholder_when_expires_at_absent(monkeypatch, capsys):
    monkeypatch.setattr(AdminApiClient, "list_api_keys",
                        lambda self, limit=20: {"data": [
                            {"id": "key_2", "name": "dev", "status": "active"},
                        ]})

    cmd_admin_list_keys("admin-k")

    out = capsys.readouterr().out
    assert "expires=never" in out
    assert "expires=None" not in out


# ── v1.25.0: CMEK external_keys (best-effort, flagged for verification) ──


def test_create_external_key_builds_expected_payload(monkeypatch):
    client = AdminApiClient(admin_api_key="admin-k")
    captured = {}
    monkeypatch.setattr(client, "_post", lambda path, payload: (
        captured.update(path=path, payload=payload) or {"id": "key_1"}
    ))

    client.create_external_key("wrkspc_1", "aws_kms", "arn:aws:kms:us-east-1:123:key/abc")

    assert captured["path"] == "/external_keys"
    assert captured["payload"] == {
        "workspace_id": "wrkspc_1", "provider": "aws_kms",
        "key_arn_or_id": "arn:aws:kms:us-east-1:123:key/abc",
    }


def test_validate_external_key_posts_to_validate_path(monkeypatch):
    client = AdminApiClient(admin_api_key="admin-k")
    captured = {}
    monkeypatch.setattr(client, "_post", lambda path, payload: (
        captured.update(path=path, payload=payload) or {"valid": True}
    ))

    client.validate_external_key("key_1")

    assert captured["path"] == "/external_keys/key_1/validate"


def test_attach_external_key_posts_workspace_id(monkeypatch):
    client = AdminApiClient(admin_api_key="admin-k")
    captured = {}
    monkeypatch.setattr(client, "_post", lambda path, payload: (
        captured.update(path=path, payload=payload) or {"attached": True}
    ))

    client.attach_external_key("key_1", "wrkspc_1")

    assert captured["path"] == "/external_keys/key_1/attach"
    assert captured["payload"] == {"workspace_id": "wrkspc_1"}


def test_list_external_keys_without_workspace_filter(monkeypatch):
    client = AdminApiClient(admin_api_key="admin-k")
    captured = {}
    monkeypatch.setattr(client, "_get", lambda path, params=None: (
        captured.update(path=path, params=params) or {"data": []}
    ))

    client.list_external_keys()

    assert captured["path"] == "/external_keys"
    assert captured["params"] is None


def test_list_external_keys_with_workspace_filter(monkeypatch):
    client = AdminApiClient(admin_api_key="admin-k")
    captured = {}
    monkeypatch.setattr(client, "_get", lambda path, params=None: (
        captured.update(path=path, params=params) or {"data": []}
    ))

    client.list_external_keys(workspace_id="wrkspc_1")

    assert captured["params"] == {"workspace_id": "wrkspc_1"}


def test_cmd_cmek_list_prints_wrong_key_hint(monkeypatch, capsys):
    from wire.zc_admin_api import cmd_cmek_list
    monkeypatch.setattr(AdminApiClient, "list_external_keys",
                        lambda self, workspace_id=None: {"error": "forbidden", "status": 403})

    result = cmd_cmek_list("regular-key")

    assert result is None
    assert "Admin API key" in capsys.readouterr().out


def test_cmd_cmek_list_prints_keys(monkeypatch, capsys):
    from wire.zc_admin_api import cmd_cmek_list
    monkeypatch.setattr(AdminApiClient, "list_external_keys",
                        lambda self, workspace_id=None: {"data": [
                            {"id": "key_1", "workspace_id": "wrkspc_1",
                             "provider": "aws_kms", "status": "active"},
                        ]})

    result = cmd_cmek_list("admin-k")

    out = capsys.readouterr().out
    assert "key_1" in out
    assert "aws_kms" in out
    assert result is not None
