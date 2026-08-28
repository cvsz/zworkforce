"""
zc_admin_api.py — Admin API: Usage & Cost, API keys, Spend Limits, Rate Limits, zAICoder Analytics
AI Model Coder CLI v1.24.0

Thin Admin API wrappers, combined into one module since all require the
same auth (an Admin API key, prefix sk-ant-admin..., created in the
Console — this is a different key type than the regular API key used
everywhere else in this CLI, and these calls will 401 with a normal key).

  1. Usage and Cost API — org-level historical spend/usage reporting.
     `zc_cost_optimizer.py` only ever *estimates* cost locally from
     token counts it's told about after the fact; it never calls a real
     usage/cost endpoint. This module is that missing live-data path —
     see zc_cost_optimizer.py's docstring for the cross-link the other
     direction.

  2. API key management — list/update organization API keys. Anthropic
     does not document a create-key endpoint: keys are created through
     the Console UI, where the secret is displayed exactly once, and
     that's intentional (creating a raw secret programmatically would be
     an exfiltration/security risk). So this module implements list,
     get, and update (e.g. changing status to revoke a key) — not create.
     `--admin-create-key` is deliberately not implemented; see
     cmd_admin_create_key() below for why, rather than silently no-op-ing.

  3. Spend Limits API (v1.23.0) — per-member spend governance. zAICoder
     Enterprise only; a zAICoder Console/API-only org gets a 403 from
     these endpoints. Eight endpoints across two resources: spend limits
     (list effective limits org-wide, set/get/delete a per-user
     override) and spend limit increase requests (list the queue,
     approve/deny a pending request). Requires an Admin API key with the
     read:spend_limits / write:spend_limits scopes.

  4. Rate Limits API (v1.23.0) — read-only. Two endpoints: the org's
     configured limits (grouped by model family, batches, files, skills,
     web search), and a workspace's overrides (each paired with the
     inherited org_limit). This is a different concern from
     resilience.py's client-side 429 backoff: that module *reacts* to
     being rate-limited; this one *reads what the configured limits
     are* before you ever hit them.

CLI flags:
  --usage-report                 Print a usage report table (token counts)
  --usage-report-start DATE       Start date (YYYY-MM-DD), default: 30 days ago
  --usage-report-end DATE         End date (YYYY-MM-DD), default: today
  --usage-report-group-by FIELD   Group by field, e.g. model, api_key_id (default: model)
  --cost-report                   Print a cost report table (billed spend, not token counts)
  --cost-report-start DATE        Start date (YYYY-MM-DD), default: 30 days ago
  --cost-report-end DATE          End date (YYYY-MM-DD), default: today
  --cost-report-group-by FIELD    Group by field, e.g. model, api_key_id (default: model)
  --admin-list-keys               List organization API keys
  --admin-revoke-key ID           Revoke (set status=inactive) an API key by ID
  --admin-create-key NAME         Explains why this isn't supported (Console-only)
  --spend-limits-list             List every member's resolved effective spend limit
  --spend-limit-set USER_ID AMOUNT  Set a per-user spend limit override (decimal string, minor units)
  --spend-limit-get ID            Get one spend limit override by id
  --spend-limit-delete ID         Delete a per-user spend limit override
  --spend-limit-requests-list     List spend limit increase requests
  --spend-limit-status STATUS     Filter --spend-limit-requests-list by status (pending/approved/denied)
  --spend-limit-request-approve ID  Approve a pending increase request
  --spend-limit-request-deny ID   Deny a pending increase request
  --rate-limits                   Print the organization's configured rate limits
  --rate-limits-model MODEL       Filter --rate-limits to one model's group
  --rate-limits-workspace ID      Print one workspace's rate limit overrides (with inherited org_limit)
  --claude-code-usage-report      Print daily per-user zAICoder productivity metrics (v1.24.0)
  --claude-code-usage-report-start DATE  Date (YYYY-MM-DD) for --claude-code-usage-report, default: yesterday
"""

import json
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

ADMIN_BASE = "https://api.anthropic.com/v1/organizations"


class AdminApiError(Exception):
    pass


class AdminApiClient:
    """Thin client for the Admin API, following the same _post()/_get()
    pattern used throughout this project's zc_*.py modules.

    admin_api_key must be an Admin API key (sk-ant-admin...), not a
    regular API key — regular keys don't have access to this endpoint
    family and will get a 401/403.
    """

    def __init__(self, admin_api_key: str):
        self.admin_api_key = admin_api_key

    def _headers(self) -> dict:
        return {
            "Content-Type": "application/json",
            "x-api-key": self.admin_api_key,
            "anthropic-version": "2023-06-01",
        }

    def _get(self, path: str, params: Optional[dict] = None) -> dict:
        url = f"{ADMIN_BASE}{path}"
        if params:
            url += "?" + urllib.parse.urlencode(
                {k: v for k, v in params.items() if v is not None}, doseq=True,
            )
        req = urllib.request.Request(url, headers=self._headers(), method="GET")
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
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
            with urllib.request.urlopen(req, timeout=60) as r:
                return json.loads(r.read().decode())
        except urllib.error.HTTPError as e:
            return {"error": e.read().decode(), "status": e.code}
        except Exception as e:
            return {"error": str(e)}

    def _delete(self, path: str) -> dict:
        req = urllib.request.Request(f"{ADMIN_BASE}{path}", headers=self._headers(), method="DELETE")
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                body = r.read().decode()
                return json.loads(body) if body else {"deleted": True}
        except urllib.error.HTTPError as e:
            return {"error": e.read().decode(), "status": e.code}
        except Exception as e:
            return {"error": str(e)}

    # ── Usage and Cost API ──────────────────────────────────────────────

    def get_usage_report(self, start: str, end: str, group_by: str = "model") -> dict:
        """Wraps the usage_report endpoint. start/end are YYYY-MM-DD."""
        return self._get("/usage_report", params={
            "starting_at": start, "ending_at": end, "group_by": group_by,
        })

    def get_cost_report(self, start: str, end: str, group_by: str = "model") -> dict:
        """Wraps the cost_report endpoint — actual billed spend, distinct
        from the token-count usage_report above."""
        return self._get("/cost_report", params={
            "starting_at": start, "ending_at": end, "group_by": group_by,
        })

    # ── CMEK external_keys (v1.25.0 — see note below) ─────────────────────
    #
    # ⚠️ Confirmation needed: the docs confirm "external_keys API
    # endpoints" exist and are Admin-API-scoped on zAICoder Platform
    # (explicitly called out as *unavailable* on zAICoder Platform on AWS),
    # but this session could not find or safely fetch the endpoint's
    # exact path, request body, or response schema. The path segment
    # below (/organizations/external_keys) is a best-effort guess by
    # analogy with every other resource in this file living under
    # /organizations/..., NOT a confirmed one. Verify against the live
    # API reference before using this against a production organization
    # — CMEK misconfiguration risk is asymmetric (see the "Revoking or
    # disabling the key makes all CMEK-protected data in that workspace
    # permanently inaccessible, with no backout path" warning in the
    # product docs), so treat these methods as a starting point to
    # correct, not a verified client.
    def create_external_key(self, workspace_id: str, provider: str, key_arn_or_id: str) -> dict:
        """Register a customer-managed encryption key (CMEK) for a
        workspace. `provider` is one of "aws_kms", "gcp_kms", or
        "azure_key_vault" per the product docs (Google Cloud KMS and
        Azure Key Vault are not available on zAICoder Platform on AWS —
        AWS KMS only there). Attaching a key to a workspace is
        irreversible: it cannot later be detached or swapped, and the
        workspace's data-retention setting locks in place."""
        return self._post("/external_keys", {
            "workspace_id": workspace_id, "provider": provider,
            "key_arn_or_id": key_arn_or_id,
        })

    def validate_external_key(self, key_id: str) -> dict:
        """Validate a registered key's permissions/purpose/algorithm
        before attaching it — mirrors the Console's "validate" step."""
        return self._post(f"/external_keys/{key_id}/validate", {})

    def attach_external_key(self, key_id: str, workspace_id: str) -> dict:
        """Attach a validated key to a workspace. Irreversible per the
        product docs: once attached, a key cannot be detached or
        swapped, and returning to zero data retention requires creating
        a new workspace and moving traffic to it."""
        return self._post(f"/external_keys/{key_id}/attach", {"workspace_id": workspace_id})

    def list_external_keys(self, workspace_id: Optional[str] = None) -> dict:
        """List registered CMEK keys, optionally filtered to one
        workspace."""
        params = {"workspace_id": workspace_id} if workspace_id else None
        return self._get("/external_keys", params=params)

    # ── zAICoder Analytics API (v1.24.0) ──────────────────────────────

    def get_zc_code_usage_report(self, starting_at: str, limit: int = 20,
                                     page: Optional[str] = None) -> dict:
        """GET /organizations/usage_report/zc_code — one record per
        user per day: session counts, lines of code added/removed,
        commits/PRs created through zAICoder, per-editing-tool
        accept/reject counts, and a per-model token/cost breakdown. Same
        Admin API key as the org-wide Usage & Cost API above, but this is
        zAICoder-Code-specific and free to call regardless of plan.
        starting_at is required (YYYY-MM-DD); page is the cursor from a
        previous response's next_page for pagination."""
        return self._get("/usage_report/zc_code", params={
            "starting_at": starting_at, "limit": limit, "page": page,
        })

    # ── API key management ──────────────────────────────────────────────

    def list_api_keys(self, limit: int = 20) -> dict:
        return self._get("/api_keys", params={"limit": limit})

    def get_api_key(self, key_id: str) -> dict:
        return self._get(f"/api_keys/{key_id}")

    def update_api_key(self, key_id: str, status: Optional[str] = None,
                       name: Optional[str] = None) -> dict:
        """status: 'active' or 'inactive'. There is no documented delete
        endpoint either — revocation is done via status, not deletion."""
        payload = {}
        if status:
            payload["status"] = status
        if name:
            payload["name"] = name
        return self._post(f"/api_keys/{key_id}", payload)

    def revoke_api_key(self, key_id: str) -> dict:
        return self.update_api_key(key_id, status="inactive")

    # ── Spend Limits API (v1.23.0, zAICoder Enterprise only) ───────────────

    def list_effective_spend_limits(self, limit: int = 50, page: Optional[str] = None) -> dict:
        """Every current member with their resolved effective spend limit,
        where it's inherited from (source), and their period-to-date
        spend. GET /spend_limits/effective."""
        return self._get("/spend_limits/effective", params={"limit": limit, "page": page})

    def set_spend_limit(self, user_id: str, amount: str,
                        suppress_notification: bool = False) -> dict:
        """Set a per-user spend limit override. `amount` is a decimal
        string in minor units (cents), per the API's convention.
        `suppress_notification` is only sent when True (omitted
        otherwise) — by default Anthropic emails the member."""
        payload: dict[str, Any] = {"user_id": user_id, "amount": amount}
        if suppress_notification:
            payload["suppress_notification"] = True
        return self._post("/spend_limits", payload)

    def get_spend_limit(self, spend_limit_id: str) -> dict:
        return self._get(f"/spend_limits/{spend_limit_id}")

    def delete_spend_limit(self, spend_limit_id: str) -> dict:
        """Deletes a per-user override. Seat-tier, group, and
        organization-level rows cannot be deleted through this
        endpoint — only per-user overrides."""
        return self._delete(f"/spend_limits/{spend_limit_id}")

    def list_spend_limit_increase_requests(self, status: Optional[list] = None,
                                           actor_ids: Optional[list] = None,
                                           limit: int = 50,
                                           page: Optional[str] = None) -> dict:
        """List spend limit increase requests, most recent first. `status`
        filters by one or more of pending/approved/denied; `actor_ids`
        filters to specific requesters."""
        params: dict[str, Any] = {"limit": limit, "page": page}
        if status:
            params["status[]"] = status
        if actor_ids:
            params["actor_ids[]"] = actor_ids
        return self._get("/spend_limit_increase_requests", params=params)

    def get_spend_limit_increase_request(self, request_id: str) -> dict:
        return self._get(f"/spend_limit_increase_requests/{request_id}")

    def approve_spend_limit_increase_request(self, request_id: str,
                                             suppress_notification: bool = False) -> dict:
        """Approving writes the same per-user spend limit row that
        set_spend_limit() writes — this resolves the pending request AND
        sets the override in one call."""
        payload = {}
        if suppress_notification:
            payload["suppress_notification"] = True
        return self._post(f"/spend_limit_increase_requests/{request_id}/approve", payload)

    def deny_spend_limit_increase_request(self, request_id: str,
                                          suppress_notification: bool = False) -> dict:
        payload = {}
        if suppress_notification:
            payload["suppress_notification"] = True
        return self._post(f"/spend_limit_increase_requests/{request_id}/deny", payload)

    # ── Rate Limits API (v1.23.0, read-only) ─────────────────────────────

    def get_org_rate_limits(self, model: Optional[str] = None) -> dict:
        """The organization's configured rate limits, grouped by model
        family/batches/files/skills/web-search. `model`, when given,
        filters to the single group that model string belongs to (404 if
        it doesn't match any group) — omitted by default, returning every
        group."""
        params = {"model": model} if model else None
        return self._get("/rate_limits", params=params)

    def get_workspace_rate_limits(self, workspace_id: str) -> dict:
        """A single workspace's rate limit *overrides* only — anything
        missing is inherited from the organization, not unlimited. Each
        present limiter is paired with the organization's value
        (org_limit) for the same limiter."""
        return self._get(f"/workspaces/{workspace_id}/rate_limits")


def _default_date_range() -> tuple:
    end = datetime.now(timezone.utc).date()
    start = end - timedelta(days=30)
    return start.isoformat(), end.isoformat()


def cmd_usage_report(admin_api_key: str, start: Optional[str] = None,
                     end: Optional[str] = None, group_by: str = "model"):
    default_start, default_end = _default_date_range()
    start = start or default_start
    end = end or default_end
    client = AdminApiClient(admin_api_key)
    data = client.get_usage_report(start, end, group_by=group_by)
    if "error" in data:
        print(f"\033[91m✗ Usage report failed: {data['error']}\033[0m")
        if data.get("status") in (401, 403):
            print("\033[93m  This endpoint requires an Admin API key (sk-ant-admin...), "
                 "not a regular API key.\033[0m")
        return None

    print(f"\n\033[94mUsage report — {start} to {end} (grouped by {group_by})\033[0m\n")
    rows = data.get("data", data.get("results", []))
    if not rows:
        print("  (no usage data returned for this range)")
    for row in rows:
        label = row.get(group_by, row.get("model", "?"))
        input_tok = row.get("input_tokens", row.get("uncached_input_tokens", "?"))
        output_tok = row.get("output_tokens", "?")
        print(f"  {label:<28} in={input_tok:<12} out={output_tok}")
    print()
    return data


def cmd_cost_report(admin_api_key: str, start: Optional[str] = None,
                    end: Optional[str] = None, group_by: str = "model"):
    """--cost-report: actual billed spend (cost_report), distinct from
    the token-count-based --usage-report above. Mirrors cmd_usage_report
    one-for-one; get_cost_report() already existed on AdminApiClient but
    had no CLI flag wired to it until now."""
    default_start, default_end = _default_date_range()
    start = start or default_start
    end = end or default_end
    client = AdminApiClient(admin_api_key)
    data = client.get_cost_report(start, end, group_by=group_by)
    if "error" in data:
        print(f"\033[91m✗ Cost report failed: {data['error']}\033[0m")
        if data.get("status") in (401, 403):
            print("\033[93m  This endpoint requires an Admin API key (sk-ant-admin...), "
                 "not a regular API key.\033[0m")
        return None

    print(f"\n\033[94mCost report — {start} to {end} (grouped by {group_by})\033[0m\n")
    rows = data.get("data", data.get("results", []))
    if not rows:
        print("  (no cost data returned for this range)")
    for row in rows:
        label = row.get(group_by, row.get("model", "?"))
        amount = row.get("amount", row.get("cost", "?"))
        currency = row.get("currency", "usd")
        print(f"  {label:<28} {amount} {currency}")
    print()
    return data


def cmd_cmek_list(admin_api_key: str, workspace_id: Optional[str] = None):
    """--cmek-list: list registered CMEK external keys.

    ⚠️ See the "CMEK external_keys" section of AdminApiClient — the
    exact endpoint shape used here is a best-effort guess pending
    confirmation against the live API reference, not a verified client.
    """
    client = AdminApiClient(admin_api_key)
    data = client.list_external_keys(workspace_id=workspace_id)
    if "error" in data:
        print(f"\033[91m✗ Failed to list CMEK keys: {data['error']}\033[0m")
        if data.get("status") in (401, 403):
            print("\033[93m  This endpoint requires an Admin API key (sk-ant-admin...), "
                 "not a regular API key.\033[0m")
        return None

    print("\n\033[94mCMEK external keys\033[0m  "
          "\033[93m(unverified endpoint shape — see docs/37_upgrade_v1.25.0_audit_and_impl.md)\033[0m\n")
    for k in data.get("data", []):
        print(f"  {k.get('id', '?')}  workspace={k.get('workspace_id', '?')}  "
              f"provider={k.get('provider', '?')}  status={k.get('status', '?')}")
    print()
    return data



def cmd_zc_code_usage_report(admin_api_key: str, starting_at: str, limit: int = 20):
    """--claude-code-usage-report: daily, per-user zAICoder productivity
    metrics (sessions, lines of code, commits/PRs, per-model cost) — a
    dedicated report distinct from the org-wide --usage-report/--cost-report
    above, though it shares the same Admin API key and client class."""
    client = AdminApiClient(admin_api_key)
    data = client.get_zc_code_usage_report(starting_at, limit=limit)
    if "error" in data:
        print(f"\033[91m✗ zAICoder usage report failed: {data['error']}\033[0m")
        if data.get("status") in (401, 403):
            print("\033[93m  This endpoint requires an Admin API key (sk-ant-admin...), "
                 "not a regular API key.\033[0m")
        return None

    print(f"\n\033[94mzAICoder usage report — {starting_at}\033[0m\n")
    rows = data.get("data", [])
    if not rows:
        print("  (no zAICoder activity for this date)")
    for row in rows:
        user_actor = row.get("user_actor") or {}
        api_actor = row.get("api_actor") or {}
        actor_label = "user" if user_actor else "api_key" if api_actor else "actor"
        core = row.get("core_metrics", {})
        def numeric_metric(value: Any, fallback: Any = "?") -> Any:
            return value if isinstance(value, (int, float)) and not isinstance(value, bool) else fallback

        num_sessions = numeric_metric(core.get("num_sessions"))
        loc = core.get("lines_of_code", {})
        added = numeric_metric(loc.get("added"))
        removed = numeric_metric(loc.get("removed"))
        commits = numeric_metric(core.get("commits_by_zc_code"))
        prs = numeric_metric(core.get("pull_requests_by_zc_code"))
        cost_total = sum(
            numeric_metric(mb.get("estimated_cost", {}).get("amount"), 0)
            for mb in row.get("model_breakdown", []) or []
        )
        # API-derived metrics are numeric allow-listed and actor labels contain no identity data.
        print(f"  {actor_label:<32} sessions={num_sessions:<4} "
              f"+{added}/-{removed}  commits={commits}  prs={prs}  "
              f"cost={cost_total}")
    print()
    return data


def cmd_admin_list_keys(admin_api_key: str, limit: int = 20):
    client = AdminApiClient(admin_api_key)
    data = client.list_api_keys(limit=limit)
    if "error" in data:
        print(f"\033[91m✗ Failed to list API keys: {data['error']}\033[0m")
        if data.get("status") in (401, 403):
            print("\033[93m  This endpoint requires an Admin API key (sk-ant-admin...), "
                 "not a regular API key.\033[0m")
        return None

    print("\n\033[94mOrganization API keys\033[0m\n")
    for key in data.get("data", []):
        # expires_at (v1.24.0): the API surfaces this field now that the
        # Console lets a key be created with an expiration. Print a clear
        # placeholder instead of the literal string "None" when absent —
        # there's still no create-key API endpoint (expiration is set at
        # creation in the Console UI only), this is a read-only addition.
        expires_at = key.get("expires_at") or "never"
        print(f"  {key.get('id', '?')}  {key.get('name', '')}  "
              f"status={key.get('status', '?')}  expires={expires_at}")
    print()
    return data


def cmd_admin_revoke_key(admin_api_key: str, key_id: str):
    client = AdminApiClient(admin_api_key)
    data = client.revoke_api_key(key_id)
    if "error" in data:
        print(f"\033[91m✗ Failed to revoke key {key_id}: {data['error']}\033[0m")
        return None
    print(f"\033[92m✓ Key {key_id} set to inactive\033[0m")
    return data


def cmd_admin_create_key(name: str):
    """--admin-create-key deliberately does not call an API — there is no
    documented create-key endpoint. Anthropic API keys are generated
    through the Console UI, where the secret is displayed exactly once;
    creating them programmatically isn't supported, almost certainly so a
    raw secret is never returned to a script that could log or leak it.
    This prints that explanation instead of silently failing or faking
    a response."""
    print(f"\033[93mℹ Can't create API key {name!r} via the Admin API — there is no "
         "documented create-key endpoint.\033[0m")
    print("  API keys are generated through the Console UI (a secret is shown once, "
         "on purpose). Use --admin-list-keys / --admin-revoke-key for the parts of "
         "key management that are actually supported programmatically.")
    return None


def _wrong_key_hint(data: dict, extra: str = ""):
    if data.get("status") in (401, 403):
        print(f"\033[93m  This endpoint requires an Admin API key (sk-ant-admin...), "
             f"not a regular API key.{' ' + extra if extra else ''}\033[0m")


# ── Spend Limits API (v1.23.0, zAICoder Enterprise only) ──────────────────

def cmd_spend_limits_list(admin_api_key: str, limit: int = 50):
    client = AdminApiClient(admin_api_key)
    data = client.list_effective_spend_limits(limit=limit)
    if "error" in data:
        print(f"\033[91m✗ Failed to list spend limits: {data['error']}\033[0m")
        _wrong_key_hint(data, "This API also requires a zAICoder Enterprise organization.")
        return None

    print("\n\033[94mEffective spend limits\033[0m\n")
    for row in data.get("data", []):
        user = row.get("user_id", "?")
        amount = row.get("amount", "?")
        source = row.get("source", "?")
        spent = row.get("period_to_date_spend", "?")
        print(f"  {user:<28} limit={amount:<12} source={source:<12} spent={spent}")
    print()
    return data


def cmd_spend_limit_set(user_id: str, amount: str, admin_api_key: str,
                        suppress_notification: bool = False):
    client = AdminApiClient(admin_api_key)
    data = client.set_spend_limit(user_id, amount, suppress_notification=suppress_notification)
    if "error" in data:
        print(f"\033[91m✗ Failed to set spend limit: {data['error']}\033[0m")
        _wrong_key_hint(data)
        return None
    print(f"\033[92m✓ spend limit set\033[0m  user_id={user_id}  amount={amount}")
    return data


def cmd_spend_limit_get(spend_limit_id: str, admin_api_key: str):
    client = AdminApiClient(admin_api_key)
    data = client.get_spend_limit(spend_limit_id)
    if "error" in data:
        print(f"\033[91m✗ Failed to get spend limit {spend_limit_id}: {data['error']}\033[0m")
        return None
    print(f"  {data}")
    return data


def cmd_spend_limit_delete(spend_limit_id: str, admin_api_key: str):
    client = AdminApiClient(admin_api_key)
    data = client.delete_spend_limit(spend_limit_id)
    if "error" in data:
        print(f"\033[91m✗ Failed to delete spend limit {spend_limit_id}: {data['error']}\033[0m")
        return None
    print(f"\033[92m✓ spend limit {spend_limit_id} deleted\033[0m")
    return data


def cmd_spend_limit_requests_list(admin_api_key: str, status: Optional[str] = None):
    client = AdminApiClient(admin_api_key)
    status_filter = [status] if status else None
    data = client.list_spend_limit_increase_requests(status=status_filter)
    if "error" in data:
        print(f"\033[91m✗ Failed to list spend limit increase requests: {data['error']}\033[0m")
        _wrong_key_hint(data, "This API also requires a zAICoder Enterprise organization.")
        return None

    print("\n\033[94mSpend limit increase requests\033[0m\n")
    for row in data.get("data", []):
        print(f"  {row.get('id', '?')}  user={row.get('actor', {}).get('user_id', '?')}  "
             f"status={row.get('status', '?')}  requested={row.get('requested_amount', '?')}")
    print()
    return data


def cmd_spend_limit_request_approve(request_id: str, admin_api_key: str):
    client = AdminApiClient(admin_api_key)
    data = client.approve_spend_limit_increase_request(request_id)
    if "error" in data:
        print(f"\033[91m✗ Failed to approve request {request_id}: {data['error']}\033[0m")
        return None
    print(f"\033[92m✓ request {request_id} approved\033[0m")
    return data


def cmd_spend_limit_request_deny(request_id: str, admin_api_key: str):
    client = AdminApiClient(admin_api_key)
    data = client.deny_spend_limit_increase_request(request_id)
    if "error" in data:
        print(f"\033[91m✗ Failed to deny request {request_id}: {data['error']}\033[0m")
        return None
    print(f"\033[92m✓ request {request_id} denied\033[0m")
    return data


# ── Rate Limits API (v1.23.0, read-only) ─────────────────────────────────

def cmd_rate_limits(admin_api_key: str, model: Optional[str] = None):
    client = AdminApiClient(admin_api_key)
    data = client.get_org_rate_limits(model=model)
    if "error" in data:
        print(f"\033[91m✗ Failed to get rate limits: {data['error']}\033[0m")
        _wrong_key_hint(data)
        return None

    print("\n\033[94mOrganization rate limits\033[0m" +
         (f" (model={model})" if model else "") + "\n")
    for group in data.get("data", data.get("rate_limits", [])):
        label = group.get("model_group", group.get("name", "?"))
        print(f"  {label}")
        for limiter in group.get("limits", []):
            print(f"    {limiter.get('type', '?'):<24} {limiter.get('value', '?')}")
    print()
    return data


def cmd_rate_limits_workspace(workspace_id: str, admin_api_key: str):
    client = AdminApiClient(admin_api_key)
    data = client.get_workspace_rate_limits(workspace_id)
    if "error" in data:
        print(f"\033[91m✗ Failed to get rate limits for workspace {workspace_id}: "
             f"{data['error']}\033[0m")
        _wrong_key_hint(data)
        return None

    print(f"\n\033[94mWorkspace rate limit overrides — {workspace_id}\033[0m\n")
    groups = data.get("data", data.get("rate_limits", []))
    if not groups:
        print("  (no overrides — this workspace inherits every organization limit)")
    for group in groups:
        label = group.get("model_group", group.get("name", "?"))
        print(f"  {label}")
        for limiter in group.get("limits", []):
            print(f"    {limiter.get('type', '?'):<24} "
                 f"value={limiter.get('value', '?'):<12} org_limit={limiter.get('org_limit', '?')}")
    print()
    return data
