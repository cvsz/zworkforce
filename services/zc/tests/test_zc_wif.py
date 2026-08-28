"""tests/test_zc_wif.py

Covers zc_wif.py — Workload Identity Federation (v1.23.0).
See docs/35_upgrade_v1.23.0_audit_and_impl.md Finding 1.
"""
import json

import pytest

import wire.zc_wif as wif

# ── resolve_wif_env() ─────────────────────────────────────────────────

FULL_ENV = {
    "ANTHROPIC_FEDERATION_RULE_ID": "fdrl_1",
    "ANTHROPIC_ORGANIZATION_ID": "org_1",
    "ANTHROPIC_SERVICE_ACCOUNT_ID": "svac_1",
    "ANTHROPIC_IDENTITY_TOKEN": "eyFakeJwt",
}


def test_resolve_wif_env_empty_returns_none():
    assert wif.resolve_wif_env({}) is None


def test_resolve_wif_env_full_literal_token():
    cfg = wif.resolve_wif_env(FULL_ENV)
    assert cfg == {
        "federation_rule_id": "fdrl_1", "organization_id": "org_1",
        "service_account_id": "svac_1", "workspace_id": None,
        "identity_token": "eyFakeJwt",
    }


def test_resolve_wif_env_includes_workspace_id_when_set():
    env = dict(FULL_ENV, ANTHROPIC_WORKSPACE_ID="wrkspc_1")
    cfg = wif.resolve_wif_env(env)
    assert cfg["workspace_id"] == "wrkspc_1"


@pytest.mark.parametrize("missing", [
    "ANTHROPIC_FEDERATION_RULE_ID", "ANTHROPIC_ORGANIZATION_ID",
    "ANTHROPIC_SERVICE_ACCOUNT_ID",
])
def test_resolve_wif_env_missing_required_var_returns_none(missing):
    env = dict(FULL_ENV)
    del env[missing]
    assert wif.resolve_wif_env(env) is None


def test_resolve_wif_env_missing_both_token_sources_returns_none():
    env = {k: v for k, v in FULL_ENV.items() if k != "ANTHROPIC_IDENTITY_TOKEN"}
    assert wif.resolve_wif_env(env) is None


def test_resolve_wif_env_file_takes_precedence_over_literal(tmp_path):
    token_file = tmp_path / "token"
    token_file.write_text("file-token-value\n")
    env = dict(FULL_ENV)
    env["ANTHROPIC_IDENTITY_TOKEN_FILE"] = str(token_file)
    env["ANTHROPIC_IDENTITY_TOKEN"] = "literal-should-be-ignored"

    cfg = wif.resolve_wif_env(env)

    assert cfg["identity_token"] == "file-token-value"


def test_resolve_wif_env_unreadable_file_returns_none(tmp_path):
    env = dict(FULL_ENV)
    env["ANTHROPIC_IDENTITY_TOKEN_FILE"] = str(tmp_path / "does-not-exist")
    assert wif.resolve_wif_env(env) is None


# ── WIFCredentialExchanger.exchange() ────────────────────────────────


class _FakeResp:
    def __init__(self, body: bytes):
        self._body = body
        self.headers: dict[str, str] = {}

    def read(self):
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def test_exchange_sends_jwt_bearer_grant(monkeypatch):
    captured = {}

    def fake_urlopen(req, timeout=None):
        captured["body"] = json.loads(req.data.decode())
        return _FakeResp(json.dumps({
            "access_token": "sk-ant-oat01-abcdefghijklmno",
            "expires_in": 3600, "token_type": "bearer", "scope": "workspace:developer",
        }).encode())

    monkeypatch.setattr(wif.urllib.request, "urlopen", fake_urlopen)
    exchanger = wif.WIFCredentialExchanger()

    result = exchanger.exchange("fdrl_1", "org_1", "svac_1", "eyJhbGciOi.fake.jwt")

    assert captured["body"]["grant_type"] == wif.JWT_BEARER_GRANT
    assert captured["body"]["assertion"] == "eyJhbGciOi.fake.jwt"
    assert "workspace_id" not in captured["body"]
    assert result["access_token"].startswith("sk-ant-oat01-")


def test_exchange_includes_workspace_id_when_given(monkeypatch):
    captured = {}

    def fake_urlopen(req, timeout=None):
        captured["body"] = json.loads(req.data.decode())
        return _FakeResp(json.dumps({"access_token": "tok", "expires_in": 3600}).encode())

    monkeypatch.setattr(wif.urllib.request, "urlopen", fake_urlopen)
    wif.WIFCredentialExchanger().exchange("fdrl_1", "org_1", "svac_1", "tok",
                                          workspace_id="wrkspc_1")

    assert captured["body"]["workspace_id"] == "wrkspc_1"


def test_exchange_401_raises_wif_exchange_error_without_leaking_token(monkeypatch):
    import urllib.error

    class FakeHTTPError(urllib.error.HTTPError):
        def read(self):
            return b'{"error": "invalid_grant"}'

    def fake_urlopen(req, timeout=None):
        raise FakeHTTPError(wif.OAUTH_TOKEN_ENDPOINT, 401, "unauthorized", {}, None)

    monkeypatch.setattr(wif.urllib.request, "urlopen", fake_urlopen)
    secret_token = "super-secret-identity-token-value"

    with pytest.raises(wif.WIFExchangeError) as exc_info:
        wif.WIFCredentialExchanger().exchange("fdrl_1", "org_1", "svac_1", secret_token)

    assert exc_info.value.status == 401
    assert secret_token not in str(exc_info.value)


# ── WIFAdminClient ────────────────────────────────────────────────────


def _install_fake_admin_urlopen(monkeypatch, captured: dict, response_body: dict):
    def fake_urlopen(req, timeout=None):
        captured["headers"] = dict(req.headers)
        captured["url"] = req.full_url
        captured["method"] = req.get_method()
        if req.data:
            captured["body"] = json.loads(req.data.decode())
        return _FakeResp(json.dumps(response_body).encode())
    monkeypatch.setattr(wif.urllib.request, "urlopen", fake_urlopen)


def test_wif_admin_client_uses_bearer_not_api_key(monkeypatch):
    captured = {}
    _install_fake_admin_urlopen(monkeypatch, captured, {"id": "svac_123", "name": "test"})
    client = wif.WIFAdminClient("org-admin-oauth-token-xyz")

    result = client.create_service_account("test")

    assert result["id"] == "svac_123"
    assert captured["headers"].get("Authorization") == "Bearer org-admin-oauth-token-xyz"
    assert "X-api-key" not in captured["headers"]


def test_wif_admin_client_list_service_accounts_uses_get(monkeypatch):
    captured = {}
    _install_fake_admin_urlopen(monkeypatch, captured, {"data": []})
    client = wif.WIFAdminClient("token")

    client.list_service_accounts()

    assert captured["method"] == "GET"
    assert captured["url"] == "https://api.anthropic.com/v1/organizations/service_accounts"


def test_wif_admin_client_create_federation_issuer_defaults_jwks_discovery(monkeypatch):
    captured = {}
    _install_fake_admin_urlopen(monkeypatch, captured, {"id": "fdis_1"})
    client = wif.WIFAdminClient("token")

    client.create_federation_issuer("gha", "https://token.actions.githubusercontent.com")

    assert captured["body"]["jwks"] == {"type": "discovery"}


def test_wif_admin_client_create_federation_rule_omits_optional_fields(monkeypatch):
    captured = {}
    _install_fake_admin_urlopen(monkeypatch, captured, {"id": "fdrl_1"})
    client = wif.WIFAdminClient("token")

    client.create_federation_rule("rule1", "fdis_1", "svac_1", {"subject_prefix": "repo:x"})

    assert captured["body"]["match"] == {"subject_prefix": "repo:x"}
    assert "oauth_scope" not in captured["body"]
    assert "token_lifetime_seconds" not in captured["body"]


def test_wif_admin_client_create_federation_rule_includes_optional_fields_when_given(monkeypatch):
    captured = {}
    _install_fake_admin_urlopen(monkeypatch, captured, {"id": "fdrl_1"})
    client = wif.WIFAdminClient("token")

    client.create_federation_rule("rule1", "fdis_1", "svac_1", {"subject_prefix": "repo:x"},
                                  oauth_scope="workspace:developer", token_lifetime_seconds=600)

    assert captured["body"]["oauth_scope"] == "workspace:developer"
    assert captured["body"]["token_lifetime_seconds"] == 600


# ── CLI entry points ──────────────────────────────────────────────────


def test_cmd_wif_status_never_prints_env_values(monkeypatch, capsys):
    monkeypatch.setenv("ANTHROPIC_FEDERATION_RULE_ID", "fdrl_super_secret_id")
    monkeypatch.setenv("ANTHROPIC_IDENTITY_TOKEN", "super-secret-jwt-value")
    monkeypatch.delenv("ANTHROPIC_ORGANIZATION_ID", raising=False)
    monkeypatch.delenv("ANTHROPIC_SERVICE_ACCOUNT_ID", raising=False)
    monkeypatch.delenv("ANTHROPIC_WORKSPACE_ID", raising=False)
    monkeypatch.delenv("ANTHROPIC_IDENTITY_TOKEN_FILE", raising=False)

    wif.cmd_wif_status()

    out = capsys.readouterr().out
    assert "fdrl_super_secret_id" not in out
    assert "super-secret-jwt-value" not in out
    assert "not set" in out


def test_cmd_wif_exchange_token_fails_gracefully_when_unconfigured(monkeypatch, capsys):
    for var in wif.WIF_ENV_VARS:
        monkeypatch.delenv(var, raising=False)

    result = wif.cmd_wif_exchange_token()

    assert result is None
    assert "not fully configured" in capsys.readouterr().out


def test_cmd_wif_exchange_token_never_prints_full_access_token(monkeypatch, capsys):
    for k, v in FULL_ENV.items():
        monkeypatch.setenv(k, v)
    monkeypatch.delenv("ANTHROPIC_WORKSPACE_ID", raising=False)
    monkeypatch.delenv("ANTHROPIC_IDENTITY_TOKEN_FILE", raising=False)

    long_token = "sk-ant-oat01-" + "x" * 40

    def fake_exchange(self, **kwargs):
        return {"access_token": long_token, "expires_in": 3600,
               "token_type": "bearer", "scope": "workspace:developer"}

    monkeypatch.setattr(wif.WIFCredentialExchanger, "exchange", fake_exchange)

    result = wif.cmd_wif_exchange_token()

    out = capsys.readouterr().out
    assert result["access_token"] == long_token
    assert long_token not in out  # only a truncated preview should ever be printed
