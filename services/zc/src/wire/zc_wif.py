"""
zc_wif.py — Workload Identity Federation (WIF)
AI Model Coder CLI v1.23.0

Lets a workload authenticate to the zAICoder API with a short-lived OIDC
identity token from an identity provider it already trusts (AWS IAM,
Google Cloud, GitHub Actions, Kubernetes, Microsoft Entra ID, Okta,
SPIFFE, or any standards-compliant OIDC issuer) instead of a long-lived
static sk-ant-... API key. GA per platform.zc.com/docs/en/manage-zc/
workload-identity-federation (checked 2026-07-09).

Two independent surfaces:

  1. Token exchange (WIFCredentialExchanger) — what every federated
     *workload* actually calls at runtime: POST /v1/oauth/token with an
     RFC 7523 jwt-bearer grant, trading a JWT for a short-lived
     sk-ant-oat01-... access token. resolve_wif_env() mirrors the first-
     party SDKs' zero-argument-constructor behavior: it reads the same
     five environment variables the SDK does and activates only when
     all of the required ones are present, so a half-configured
     environment falls through to the normal static-API-key path
     instead of erroring.

  2. Setup (WIFAdminClient) — creating the service account, federation
     issuer, and federation rule that the exchange above depends on.
     These endpoints require an org:admin OAuth bearer token, NOT the
     Admin API key zc_admin_api.py's AdminApiClient uses — a
     genuinely different credential and header, kept deliberately
     separate here rather than bolted onto AdminApiClient.

Neither identity tokens nor the access tokens this module returns are
ever logged, printed in full, or included in any exception message —
they're treated with the same write-only discipline as vault credential
secrets in zc_agents_sdk.py.

CLI flags:
  --wif-exchange-token            Exchange the JWT found via env vars for
                                   a short-lived zAICoder API access token
  --wif-status                    Show which of the 5 WIF env vars are
                                   set/missing (never their values)
  --org-admin-token TOKEN         org:admin OAuth bearer token, for the
                                   --wif-create-*/--wif-list-* commands
                                   below (distinct from --admin-api-key)
  --wif-create-service-account NAME
  --wif-list-service-accounts
  --wif-create-issuer NAME        (requires --wif-issuer-url)
  --wif-issuer-url URL
  --wif-list-issuers
  --wif-create-rule NAME          (requires --wif-rule-issuer,
                                   --wif-rule-service-account,
                                   --wif-rule-subject-prefix)
  --wif-rule-issuer ID
  --wif-rule-service-account ID
  --wif-rule-subject-prefix PREFIX
  --wif-list-rules
"""

import json
import os
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Optional

from wire.exceptions import AICoderError, APIError, AuthenticationError, RateLimitError
from wire.resilience import CircuitBreaker, retry, urlopen_json

OAUTH_TOKEN_ENDPOINT = "https://api.anthropic.com/v1/oauth/token"
ADMIN_BASE = "https://api.anthropic.com/v1/organizations"
JWT_BEARER_GRANT = "urn:ietf:params:oauth:grant-type:jwt-bearer"

_breaker = CircuitBreaker(failure_threshold=5, reset_timeout=30)


class WIFExchangeError(Exception):
    """Raised when POST /v1/oauth/token returns a non-2xx response.
    Carries the HTTP status and response body (truncated, per
    resilience.raise_for_http_error's own convention) — mirrors the
    SDKs' own typed FederationExchangeError. Never includes the JWT
    assertion or any access token in its message."""

    def __init__(self, status: Optional[int], body: str):
        self.status = status
        self.body = body
        super().__init__(f"WIF token exchange failed: HTTP {status}")


class WIFCredentialExchanger:
    """Exchanges an IdP-issued JWT for a short-lived zAICoder API access
    token via POST /v1/oauth/token (RFC 7523 jwt-bearer grant)."""

    @retry(max_attempts=3, base_delay=1.0, max_delay=10.0, breaker=_breaker)
    def exchange(self, federation_rule_id: str, organization_id: str,
                service_account_id: str, identity_token: str,
                workspace_id: Optional[str] = None,
                token_lifetime_seconds: Optional[int] = None) -> dict:
        """Returns the OAuth 2.0 token response: access_token, expires_in,
        token_type, and scope. Never logs `identity_token` or the
        returned `access_token`, including on failure."""
        body: dict[str, Any] = {
            "grant_type": JWT_BEARER_GRANT,
            "assertion": identity_token,
            "federation_rule_id": federation_rule_id,
            "organization_id": organization_id,
            "service_account_id": service_account_id,
        }
        if workspace_id:
            body["workspace_id"] = workspace_id
        if token_lifetime_seconds is not None:
            body["token_lifetime_seconds"] = token_lifetime_seconds

        req = urllib.request.Request(
            OAUTH_TOKEN_ENDPOINT,
            data=json.dumps(body).encode(),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            # urlopen_json translates a raw HTTPError into the
            # AICoderError hierarchy (see resilience.raise_for_http_error)
            # before it ever reaches us, so we catch that hierarchy here,
            # not urllib.error.HTTPError directly.
            return urlopen_json(req, timeout=30)
        except AuthenticationError as e:
            raise WIFExchangeError(401, e.details.get("body", "")) from None
        except RateLimitError as e:
            raise WIFExchangeError(429, e.details.get("body", "")) from None
        except APIError as e:
            raise WIFExchangeError(e.status_code, e.details.get("body", "")) from None
        except AICoderError as e:
            raise WIFExchangeError(None, e.details.get("body", "")) from None


def resolve_wif_env(env: Optional[dict] = None) -> Optional[dict]:
    """Mirrors the first-party SDKs' zero-argument-constructor behavior:
    reads ANTHROPIC_FEDERATION_RULE_ID, ANTHROPIC_ORGANIZATION_ID,
    ANTHROPIC_SERVICE_ACCOUNT_ID (all required), ANTHROPIC_WORKSPACE_ID
    (optional — read alongside but does not gate activation), and one of
    ANTHROPIC_IDENTITY_TOKEN_FILE / ANTHROPIC_IDENTITY_TOKEN (at least
    one required; the file source takes precedence when both are set).

    Returns None — not a partial dict — unless all three required IDs
    and an identity token are present, so a half-configured environment
    falls through to the normal static-API-key path instead of a caller
    trying to use an incomplete config. `env` defaults to os.environ;
    pass an explicit dict in tests instead of monkeypatching the real
    environment."""
    env_vars = env if env is not None else dict(os.environ)
    rule_id = env_vars.get("ANTHROPIC_FEDERATION_RULE_ID")
    org_id = env_vars.get("ANTHROPIC_ORGANIZATION_ID")
    svc_account_id = env_vars.get("ANTHROPIC_SERVICE_ACCOUNT_ID")
    if not (rule_id and org_id and svc_account_id):
        return None

    identity_token = None
    token_file = env_vars.get("ANTHROPIC_IDENTITY_TOKEN_FILE")
    if token_file:
        try:
            identity_token = Path(token_file).read_text(encoding="utf-8").strip()
        except OSError:
            return None
    if identity_token is None:
        identity_token = env_vars.get("ANTHROPIC_IDENTITY_TOKEN")
    if not identity_token:
        return None

    return {
        "federation_rule_id": rule_id,
        "organization_id": org_id,
        "service_account_id": svc_account_id,
        "workspace_id": env_vars.get("ANTHROPIC_WORKSPACE_ID"),
        "identity_token": identity_token,
    }


class WIFAdminClient:
    """Setup-side client for service accounts, federation issuers, and
    federation rules. These endpoints require an org:admin OAuth bearer
    token, not the sk-ant-admin... Admin API key AdminApiClient uses —
    a genuinely different credential and header."""

    def __init__(self, org_admin_oauth_token: str):
        self.org_admin_oauth_token = org_admin_oauth_token

    def _headers(self) -> dict:
        return {
            "Content-Type": "application/json",
            "anthropic-version": "2023-06-01",
            "authorization": f"Bearer {self.org_admin_oauth_token}",
        }

    def _get(self, path: str) -> dict:
        req = urllib.request.Request(f"{ADMIN_BASE}{path}", headers=self._headers(), method="GET")
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.loads(r.read().decode())
        except urllib.error.HTTPError as e:
            return {"error": e.read().decode(), "status": e.code}
        except Exception as e:
            return {"error": str(e)}

    def _post(self, path: str, payload: dict) -> dict:
        req = urllib.request.Request(
            f"{ADMIN_BASE}{path}", data=json.dumps(payload).encode(),
            headers=self._headers(), method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.loads(r.read().decode())
        except urllib.error.HTTPError as e:
            return {"error": e.read().decode(), "status": e.code}
        except Exception as e:
            return {"error": str(e)}

    # ── Service accounts ─────────────────────────────────────────────
    def create_service_account(self, name: str) -> dict:
        return self._post("/service_accounts", {"name": name})

    def list_service_accounts(self) -> dict:
        return self._get("/service_accounts")

    # ── Federation issuers ───────────────────────────────────────────
    def create_federation_issuer(self, name: str, issuer_url: str,
                                 jwks: Optional[dict] = None) -> dict:
        payload = {"name": name, "issuer_url": issuer_url,
                  "jwks": jwks or {"type": "discovery"}}
        return self._post("/federation_issuers", payload)

    def list_federation_issuers(self) -> dict:
        return self._get("/federation_issuers")

    # ── Federation rules ─────────────────────────────────────────────
    def create_federation_rule(self, name: str, issuer_id: str,
                               service_account_id: str, match: dict,
                               oauth_scope: Optional[str] = None,
                               token_lifetime_seconds: Optional[int] = None) -> dict:
        payload: dict[str, Any] = {
            "name": name, "issuer_id": issuer_id,
            "service_account_id": service_account_id, "match": match,
        }
        if oauth_scope is not None:
            payload["oauth_scope"] = oauth_scope
        if token_lifetime_seconds is not None:
            payload["token_lifetime_seconds"] = token_lifetime_seconds
        return self._post("/federation_rules", payload)

    def list_federation_rules(self) -> dict:
        return self._get("/federation_rules")


# ── CLI entry points ────────────────────────────────────────────────────

WIF_ENV_VARS = (
    "ANTHROPIC_FEDERATION_RULE_ID", "ANTHROPIC_ORGANIZATION_ID",
    "ANTHROPIC_SERVICE_ACCOUNT_ID", "ANTHROPIC_WORKSPACE_ID",
    "ANTHROPIC_IDENTITY_TOKEN_FILE", "ANTHROPIC_IDENTITY_TOKEN",
)


def cmd_wif_status():
    """Prints which of the 5 WIF env vars are set/missing — never their
    values — so a user can debug "why didn't federation activate"
    without a secret ever hitting a terminal scrollback."""
    print("\n\033[94mWorkload Identity Federation — environment status\033[0m\n")
    for var in WIF_ENV_VARS:
        state = "\033[92mset\033[0m" if os.environ.get(var) else "\033[90mnot set\033[0m"
        print(f"  {var:<32} {state}")
    config = resolve_wif_env()
    print()
    if config:
        print("\033[92m✓ Federation would activate\033[0m (all required vars present)")
    else:
        print("\033[93mℹ Federation would NOT activate\033[0m — falls through to a "
             "static API key. Required: ANTHROPIC_FEDERATION_RULE_ID, "
             "ANTHROPIC_ORGANIZATION_ID, ANTHROPIC_SERVICE_ACCOUNT_ID, and one of "
             "ANTHROPIC_IDENTITY_TOKEN_FILE / ANTHROPIC_IDENTITY_TOKEN.")
    return config


def cmd_wif_exchange_token():
    config = resolve_wif_env()
    if not config:
        print("\033[91m✗ WIF is not fully configured in the environment.\033[0m "
             "Run --wif-status to see which variables are missing.")
        return None
    exchanger = WIFCredentialExchanger()
    try:
        token_response = exchanger.exchange(
            federation_rule_id=config["federation_rule_id"],
            organization_id=config["organization_id"],
            service_account_id=config["service_account_id"],
            identity_token=config["identity_token"],
            workspace_id=config["workspace_id"],
        )
    except WIFExchangeError as e:
        print(f"\033[91m✗ Token exchange failed: HTTP {e.status}\033[0m")
        return None
    access_token = token_response.get("access_token", "")
    preview = f"{access_token[:14]}...{access_token[-4:]}" if len(access_token) > 20 else "***"
    print(f"\033[92m✓ Exchanged for a zAICoder API access token\033[0m  "
         f"token={preview}  expires_in={token_response.get('expires_in')}s  "
         f"scope={token_response.get('scope')}")
    return token_response


def cmd_wif_create_service_account(name: str, org_admin_token: str) -> dict:
    client = WIFAdminClient(org_admin_token)
    data = client.create_service_account(name)
    if "error" in data:
        print(f"\033[91m✗ Failed to create service account: {data['error']}\033[0m")
        return data
    print(f"\033[92m✓ service account created\033[0m  id={data.get('id', '?')}  name={name}")
    return data


def cmd_wif_list_service_accounts(org_admin_token: str) -> dict:
    client = WIFAdminClient(org_admin_token)
    data = client.list_service_accounts()
    if "error" in data:
        print(f"\033[91m✗ Failed to list service accounts: {data['error']}\033[0m")
        return data
    for sa in data.get("data", []):
        print(f"  {sa.get('id', '?')}  {sa.get('name', '')}")
    return data


def cmd_wif_create_issuer(name: str, issuer_url: str, org_admin_token: str) -> dict:
    client = WIFAdminClient(org_admin_token)
    data = client.create_federation_issuer(name, issuer_url)
    if "error" in data:
        print(f"\033[91m✗ Failed to create federation issuer: {data['error']}\033[0m")
        return data
    print(f"\033[92m✓ federation issuer created\033[0m  id={data.get('id', '?')}  name={name}")
    return data


def cmd_wif_list_issuers(org_admin_token: str) -> dict:
    client = WIFAdminClient(org_admin_token)
    data = client.list_federation_issuers()
    if "error" in data:
        print(f"\033[91m✗ Failed to list federation issuers: {data['error']}\033[0m")
        return data
    for fi in data.get("data", []):
        print(f"  {fi.get('id', '?')}  {fi.get('name', '')}  {fi.get('issuer_url', '')}")
    return data


def cmd_wif_create_rule(name: str, issuer_id: str, service_account_id: str,
                        subject_prefix: str, org_admin_token: str) -> dict:
    client = WIFAdminClient(org_admin_token)
    match = {"subject_prefix": subject_prefix}
    data = client.create_federation_rule(name, issuer_id, service_account_id, match)
    if "error" in data:
        print(f"\033[91m✗ Failed to create federation rule: {data['error']}\033[0m")
        return data
    print(f"\033[92m✓ federation rule created\033[0m  id={data.get('id', '?')}  name={name}")
    return data


def cmd_wif_list_rules(org_admin_token: str) -> dict:
    client = WIFAdminClient(org_admin_token)
    data = client.list_federation_rules()
    if "error" in data:
        print(f"\033[91m✗ Failed to list federation rules: {data['error']}\033[0m")
        return data
    for fr in data.get("data", []):
        print(f"  {fr.get('id', '?')}  {fr.get('name', '')}")
    return data
