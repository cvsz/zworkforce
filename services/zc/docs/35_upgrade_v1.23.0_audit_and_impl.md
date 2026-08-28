# v1.23.0 audit cycle — cross-product gap findings + implementation prompts

Unlike the last three cycles (v1.20.0–v1.22.0, all Managed Agents), this
cycle deliberately widened the net per the methodology's own instruction
to check the *whole* Features overview, not just the area of the last
few fixes — Managed Agents has been audited three cycles running and
was due for a break. Searched platform.zc.com/docs release notes
across Authentication, Admin API, and Rate Limits, plus cross-referenced
against `zc_admin_api.py` (the module most likely to already cover
adjacent Admin-API surface) before writing anything up as a gap.

## Finding 1 — Workload Identity Federation (WIF) (GA)

**What it is:** An authentication mechanism, now GA, that lets a
workload exchange a short-lived OIDC JWT from an identity provider it
already trusts (AWS IAM, Google Cloud, GitHub Actions, Kubernetes,
Entra ID, Okta, SPIFFE, or any standards-compliant OIDC issuer) for a
short-lived zAICoder API access token (`sk-ant-oat01-...`), instead of
using a long-lived static API key. Mechanically: `POST /v1/oauth/token`
with an RFC 7523 jwt-bearer grant; the response is a standard OAuth 2.0
token response. First-party SDKs auto-detect a full federation
configuration from five environment variables
(`ZC_FEDERATION_RULE_ID`, `ZC_ORGANIZATION_ID`,
`ZC_SERVICE_ACCOUNT_ID`, `ZC_WORKSPACE_ID`, and one of
`ZC_IDENTITY_TOKEN_FILE`/`ZC_IDENTITY_TOKEN`) and refresh
the token before it expires. Setup itself (service accounts, federation
issuers, federation rules) is a separate Admin-API-adjacent surface that
requires an `org:admin` OAuth bearer token rather than a regular Admin
API key.

**Why it's a gap:** grep for `workload identity|OIDC|oidc|federation` in
the tree: zero matches. Second, differently-worded grep for
`short-lived|token_exchange|id_token`: also zero matches. Every existing
wire module authenticates with a single, always-present, static
`api_key`/`admin_api_key` string — there is no code path anywhere that
exchanges a JWT for anything.

**Priority: 🔴 P0.** This is the flagship "keyless auth" story Anthropic
is pushing across the whole platform (SDKs, zAICoder, GitHub Actions)
— a CLI wrapper that only supports static keys is missing the auth
pattern ZaiCoder itself now recommends leading with.

## Finding 2 — Spend Limits API (zAICoder Enterprise)

**What it is:** Eight Admin-API endpoints across two resources for
per-member spend governance, Enterprise-only: `GET
/v1/organizations/spend_limits/effective` (every member's resolved
limit + where it's inherited from + period-to-date spend), `POST`/`GET`/
`DELETE /v1/organizations/spend_limits[/{id}]` (set/read/remove a
per-user override), and `GET
/v1/organizations/spend_limit_increase_requests[/{id}]` plus
`.../{id}/approve` and `.../{id}/deny` (work the queue of member-
submitted requests for a higher limit). Requires an Admin API key with
`read:spend_limits`/`write:spend_limits` scopes.

**Why it's a gap:** first grep for `spend_limit` in the tree: zero
matches. `zc_admin_api.py` already implements the sibling Usage and
Cost API and API-key management, but has no code path for this
resource family at all.

**Priority: 🟠 P1.**

## Finding 3 — Rate Limits API

**What it is:** Two read-only Admin-API endpoints: `GET
/v1/organizations/rate_limits` (optionally filtered by `model=`) returns
the org's configured limits grouped by model family/batches/files/
skills/web-search, and `GET
/v1/organizations/workspaces/{workspace_id}/rate_limits` returns only
that workspace's *overrides*, each paired with the inherited
`org_limit` for comparison. Both take the same Admin API key as the
Usage and Cost API.

**Why it's a gap:** first grep for `rate_limit\b|rate-limits` outside of
retry/backoff logic in the tree: zero matches for this specific API
surface (this codebase's `resilience.py` handles *client-side* 429
backoff, which is a different, already-solved problem — this finding is
about reading ZaiCoder's *configured* limits, not reacting to them).

**Priority: 🟡 P2.** Small, read-only, no side effects — a natural
companion to `zc_admin_api.py`'s existing usage/cost reporting for
building gateways/dashboards, per the docs' own stated use cases.

## Non-gaps checked this cycle

**zAICoder Managed Agents vault credential background refresh for
`mcp_oauth` credentials** — a release-note line item alongside these
three. Not a gap: this is server-side behavior (ZaiCoder now refreshes
a stored OAuth credential's access token automatically instead of it
going stale), not a new request shape or parameter wire's
`add_credential()` needs to send. Nothing to build.

**zAICoder Managed Agents on zAICoder Platform on AWS** (webhooks, multi-
agent, self-hosted sandboxes) — not a gap: this is the same API surface
`zc_agents_sdk.py` already covers, becoming available on a different
deployment target (AWS-native endpoints vs. the direct zAICoder API).
Deployment location isn't a code-level gap unless wire starts
supporting multiple base URLs/auth schemes per cloud, which is a bigger,
separate architectural question outside a single audit finding.

---

## Implementation prompts

### Prompt 1 — Workload Identity Federation (P0)

> Create `zc_wif.py`. Two client classes:
>
> ```python
> class WIFCredentialExchanger:
>     """Exchanges an IdP-issued JWT for a short-lived zAICoder API access
>     token via POST /v1/oauth/token (RFC 7523 jwt-bearer grant)."""
>
>     def exchange(self, federation_rule_id: str, organization_id: str,
>                  service_account_id: str, identity_token: str,
>                  workspace_id: Optional[str] = None,
>                  token_lifetime_seconds: Optional[int] = None) -> dict:
>         # POST https://api.zc.com/v1/oauth/token with
>         # grant_type=urn:ietf:params:oauth:grant-type:jwt-bearer,
>         # assertion=identity_token, plus the rule/org/service-account/
>         # workspace identifiers. Returns the OAuth 2.0 token response
>         # (access_token, expires_in, token_type, scope). Wrap non-2xx
>         # responses in a typed WIFExchangeError carrying the HTTP
>         # status, response body, and request_id, mirroring the SDK's
>         # own FederationExchangeError.
>
> def resolve_wif_env() -> Optional[dict]:
>     # Reads ZC_FEDERATION_RULE_ID, ZC_ORGANIZATION_ID,
>     # ZC_SERVICE_ACCOUNT_ID, ZC_WORKSPACE_ID (optional),
>     # and one of ZC_IDENTITY_TOKEN_FILE / ZC_IDENTITY_TOKEN.
>     # Returns None (not a partial dict) unless rule_id, organization_id,
>     # service_account_id, and an identity token are ALL present — the
>     # direct env-var federation path "activates only when all are set,"
>     # per the docs; a half-configured environment must fall through to
>     # the normal API-key path rather than erroring.
> ```
>
> `WIFCredentialExchanger.exchange()` never logs `identity_token` or the
> returned `access_token` in any exception message (same write-only
> discipline as vault credentials in `zc_agents_sdk.py`).
>
> CLI: `--wif-exchange-token` (calls `resolve_wif_env()`, exchanges, and
> prints the resulting access token's expiry and scope — never the
> token value itself in full; show a truncated `sk-ant-oat01-...abcd`
> preview) and `--wif-status` (prints which of the five env vars are
> set/missing, without printing any of their values, so a user can debug
> "why didn't federation activate" without a secret ever hitting a
> terminal scrollback).
>
> Second class, `WIFAdminClient`, for the setup side (service accounts,
> federation issuers, federation rules) — these require an `org:admin`
> OAuth bearer token, not the Admin API key `zc_admin_api.py` uses:
> ```python
> class WIFAdminClient:
>     def __init__(self, org_admin_oauth_token: str): ...
>     def create_service_account(self, name: str) -> dict          # POST /v1/organizations/service_accounts
>     def list_service_accounts(self) -> dict                       # GET  /v1/organizations/service_accounts
>     def create_federation_issuer(self, name: str, issuer_url: str,
>                                  jwks: Optional[dict] = None) -> dict  # POST /v1/organizations/federation_issuers
>     def list_federation_issuers(self) -> dict                     # GET  /v1/organizations/federation_issuers
>     def create_federation_rule(self, name: str, issuer_id: str,
>                                service_account_id: str, match: dict,
>                                oauth_scope: Optional[str] = None,
>                                token_lifetime_seconds: Optional[int] = None) -> dict
>                                                                    # POST /v1/organizations/federation_rules
>     def list_federation_rules(self) -> dict                       # GET  /v1/organizations/federation_rules
> ```
> Send `Authorization: Bearer {org_admin_oauth_token}`, not
> `x-api-key` — a different header than every other Admin-API-adjacent
> call in this codebase, so this must not reuse `AdminApiClient`'s
> `_headers()` unchanged.
>
> CLI: `--wif-create-service-account NAME`, `--wif-list-service-accounts`,
> `--wif-create-issuer NAME --wif-issuer-url URL`, `--wif-list-issuers`,
> `--wif-create-rule NAME --wif-rule-issuer ID --wif-rule-service-account
> ID --wif-rule-subject-prefix PREFIX`, `--wif-list-rules` — all requiring
> a new `--org-admin-token` flag (or `ZC_ORG_ADMIN_TOKEN` env var),
> kept separate from `--admin-api-key` throughout.
>
> Tests: `resolve_wif_env()` returns `None` when any required var is
> missing (parametrize over each of the four required vars individually
> absent) and a full dict when all are set, preferring
> `ZC_IDENTITY_TOKEN_FILE` (reading the file) when both token
> sources are set; `exchange()` posts the correct jwt-bearer grant body
> and never leaks the assertion or access token in a raised exception's
> message; `WIFAdminClient` sends `Authorization: Bearer` (not
> `x-api-key`) on every call.

### Prompt 2 — Spend Limits API (P1)

> Add to `zc_admin_api.py`'s `AdminApiClient`:
> ```python
> def _delete(self, path: str) -> dict: ...  # new helper, mirrors _get/_post

> def list_effective_spend_limits(self, limit: int = 50, page: Optional[str] = None) -> dict
> def set_spend_limit(self, user_id: str, amount: str, suppress_notification: bool = False) -> dict
> def get_spend_limit(self, spend_limit_id: str) -> dict
> def delete_spend_limit(self, spend_limit_id: str) -> dict
> def list_spend_limit_increase_requests(self, status: Optional[list] = None,
>                                        actor_ids: Optional[list] = None,
>                                        limit: int = 50, page: Optional[str] = None) -> dict
> def get_spend_limit_increase_request(self, request_id: str) -> dict
> def approve_spend_limit_increase_request(self, request_id: str, suppress_notification: bool = False) -> dict
> def deny_spend_limit_increase_request(self, request_id: str, suppress_notification: bool = False) -> dict
> ```
> Note in the module docstring that this resource family is
> Enterprise-only (a zAICoder Console/API-only org gets a 403) — surface
> that in the `cmd_*` error path the same way the existing functions
> already surface the "wrong key type" 401/403 hint.
>
> CLI: `--spend-limits-list`, `--spend-limit-set USER_ID AMOUNT`,
> `--spend-limit-get ID`, `--spend-limit-delete ID`,
> `--spend-limit-requests-list [--spend-limit-status pending]`,
> `--spend-limit-request-approve ID`, `--spend-limit-request-deny ID`.
>
> Tests: each method's request shape (path, query params, DELETE verb);
> `set_spend_limit`'s `suppress_notification` flag is only sent when
> `True` (omitted by default, matching every other optional-flag
> convention already established in this file).

### Prompt 3 — Rate Limits API (P2)

> Add to `AdminApiClient`:
> ```python
> def get_org_rate_limits(self, model: Optional[str] = None) -> dict   # GET /rate_limits
> def get_workspace_rate_limits(self, workspace_id: str) -> dict        # GET /workspaces/{id}/rate_limits
> ```
> `model` is only included as a query param when given (omitted by
> default — the endpoint returns all groups). CLI: `--rate-limits
> [--rate-limits-model MODEL]`, `--rate-limits-workspace WORKSPACE_ID`.
> The workspace command's output should show each overridden limiter's
> workspace value next to its inherited `org_limit`, per the documented
> response shape, so a reader doesn't have to cross-reference the org
> call by hand.
>
> Tests: `model` param presence/absence in the org call; workspace call
> path construction; `cmd_rate_limits` prints both value and org_limit
> per limiter.

---

## Suggested sequencing

1. Prompt 1 (WIF) — highest priority, and a new standalone module, so no
   ordering conflict with the other two.
2. Prompt 2 (Spend Limits) — extends `zc_admin_api.py`.
3. Prompt 3 (Rate Limits) — smallest, extends the same file as Prompt 2;
   do after so both land in one coherent diff to that module.
