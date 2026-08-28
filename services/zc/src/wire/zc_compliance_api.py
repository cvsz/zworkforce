"""
zc_compliance_api.py — Compliance API (Activity Feed, content, directory)
AI Model Coder CLI v1.16.0

Confirmed against platform.zc.com/docs/en/manage-zc/compliance-api*
(checked 2026-07-04). This closes the gap `ROADMAP.md` had flagged as "no
matches anywhere in the tree, probably stays undocumented" — that call was
made before Anthropic shipped this API; it's real now, so this is the
concrete-request trigger the roadmap said to wait for.

WHAT THIS IS, AND HOW IT DIFFERS FROM `zc_admin_api.py`:
  zc_admin_api.py wraps org-level usage/cost *reporting* and API key
  *management* — aggregate numbers and key lifecycle, nothing about what
  was actually said in a chat. This module is the audit/eDiscovery/DLP
  surface: a chronological Activity Feed of who-did-what across the
  organization, plus (with the right key) the ability to read or
  hard-delete the underlying chats, files, projects, and directory data
  those activities reference. Different purpose, different endpoint
  family (`/v1/compliance/*` vs `/v1/organizations/*`), and critically a
  different key model — see below.

TWO KEY TYPES, DIFFERENT REACH (this is the single most important thing
to get right about this module):
  - A **Compliance Access Key** (`sk-ant-api01-...`, created in zc.ai)
    can reach every endpoint here, provided it was granted the relevant
    scope at creation time (`read:compliance_activities`,
    `read:compliance_org_data`, `read:compliance_user_data`,
    `read:compliance_org_settings`, `delete:compliance_user_data`).
    Scopes are immutable after creation — there is no "add a scope to an
    existing key" call, only "create a new key with the scope."
  - An **Admin API key** (`sk-ant-admin01-...`, created in zAICoder
    Console — the same key type `zc_admin_api.py` uses) reaches
    *only* `GET /v1/compliance/activities`, and only if it was created
    after the Compliance API was enabled for the organization. Every
    other endpoint (chats, files, projects, organizations, users, roles,
    groups, settings, and all deletes) returns 403 for an Admin API key,
    full stop — there is no scope you can add to an Admin API key to
    unlock them.
  This client works with either key type transparently: it doesn't ask
  which one you're using, it just surfaces the documented 403
  scope-mismatch message (which lists `Got:`/`Needed:` scopes) with a
  concrete fix rather than a bare permission error.

CONTENT ENDPOINTS ARE GENUINELY DANGEROUS: the delete endpoints
(chat/file/project-document/project) are immediate, permanent hard
deletes with no recovery window, and the read endpoints return actual
user chat content and file bytes, not metadata. Every destructive
`cmd_*` function in this module is dry-run by default and requires an
explicit `yes=True` (CLI: `--compliance-yes`) to actually execute,
mirroring `zc_models.py`'s `--upgrade-all`/`--upgrade-yes` pattern
rather than inventing a new confirmation convention.

RELIABILITY CONTRACT (matches platform.zc.com/docs/en/manage-zc/
compliance-errors exactly, not a generic retry wrapper):
  - 429 and retryable 5xx (502/503/504/529, or 500 without an
    `x-should-retry: false` header) retry with exponential backoff
    (1s, 2s, 4s, ... capped at 60s), up to `max_retries` attempts.
  - 400/401/403/404/409 never retry — these are caller-fixable, and
    retrying them fails identically every time.
  - Pagination cursors only ever advance after a page is *successfully*
    retrieved (see `iterate_activities`/`iterate_chats` below) — a
    raised `ComplianceApiError` always leaves the caller's last-known
    cursor untouched, per the documented "do not advance your cursor on
    a failed request" contract.
  - Errors carry the `request-id` response header for support escalation
    and expose `error_type` so callers can match on `error.type` (the
    stable part of the contract) rather than the message string.

CLI flags:
  --compliance-activities                 Print recent Activity Feed entries
  --compliance-activities-since DATETIME  created_at.gte filter (RFC 3339)
  --compliance-activities-until DATETIME  created_at.lte filter (RFC 3339)
  --compliance-activity-types T1,T2       activity_types[] filter
  --compliance-activities-limit N         Page size, 1-5000 (default 100)
  --compliance-activities-all             Page through the *entire* matching
                                          feed instead of one page
  --compliance-chats-list                 List chats for --compliance-user-ids
  --compliance-user-ids ID1,ID2           Required with --compliance-chats-list
  --compliance-chat-messages CHAT_ID      Print one chat's full message content
  --compliance-chat-delete CHAT_ID        Hard-delete a chat (needs --compliance-yes)
  --compliance-file-download FILE_ID      Download a file's original bytes
  --compliance-file-delete FILE_ID        Hard-delete a file (needs --compliance-yes)
  --compliance-projects-list              List projects
  --compliance-project-info PROJECT_ID    Show one project's details
  --compliance-project-attachments ID     List a project's attachments
  --compliance-project-delete ID          Hard-delete a project (needs --compliance-yes;
                                          fails with a clear message if chats are attached)
  --compliance-orgs-list                  List every linked organization
  --compliance-org-users ORG_UUID         List an organization's users
  --compliance-org-roles ORG_UUID         List an organization's RBAC roles
  --compliance-org-settings ORG_UUID      Show effective org settings
  --compliance-groups-list                List RBAC/SCIM groups
  --compliance-group-members GROUP_ID     List a group's members
  --compliance-yes                        Actually execute a delete (default: dry-run preview)
  --compliance-output PATH                Write --compliance-file-download's bytes here
"""

import json
import time
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Iterator
from pathlib import Path
from typing import Optional

COMPLIANCE_BASE = "https://api.anthropic.com/v1/compliance"

# Shared across every /v1/compliance/* endpoint, per parent organization
# (not per-key) — see platform.zc.com/docs/en/manage-zc/
# compliance-api#how-the-compliance-api-works.
RATE_LIMIT_RPM = 600

# Status codes the documented contract says to retry, vs. fix-and-resend.
_ALWAYS_RETRYABLE_STATUSES = {429, 502, 503, 504, 529}
_NEVER_RETRYABLE_STATUSES = {400, 401, 403, 404, 409}


class ComplianceApiError(Exception):
    """Raised for any non-2xx response from the Compliance API.

    Mirrors the documented error envelope: `error_type`/`message` come
    straight from the response body's `error.type`/`error.message`
    (match on `error_type`, not `message` — per the docs, message text
    may be reworded over time but `type` is part of the API contract).
    `request_id` is the `request-id` response header, worth including
    verbatim when escalating to Anthropic support. `retryable` reflects
    whether the documented contract says this specific response should
    have been retried automatically (it always has been, by the time
    this is raised — this flag is informational for callers who want to
    log or alert differently on exhausted-retry vs. non-retryable).
    """

    def __init__(self, status: int, error_type: str, message: str,
                 request_id: Optional[str] = None, retryable: bool = False):
        self.status = status
        self.error_type = error_type
        self.message = message
        self.request_id = request_id
        self.retryable = retryable
        super().__init__(f"[{status}] {error_type}: {message}")

    @classmethod
    def from_response(cls, status: int, body: bytes, headers: dict) -> "ComplianceApiError":
        error_type, message = "unknown_error", body.decode(errors="replace") or "(empty body)"
        try:
            parsed = json.loads(body.decode())
            err = parsed.get("error", {})
            error_type = err.get("type", error_type)
            message = err.get("message", message)
        except (json.JSONDecodeError, UnicodeDecodeError):
            pass
        return cls(
            status=status, error_type=error_type, message=message,
            request_id=headers.get("request-id") or headers.get("Request-Id"),
            retryable=_is_retryable(status, headers),
        )


def _is_retryable(status: int, headers: dict) -> bool:
    if status in _ALWAYS_RETRYABLE_STATUSES:
        return True
    if status == 500:
        # Anthropic sets x-should-retry: false for deterministic 500s;
        # its absence (or any other value) means transient/retryable.
        should_retry = headers.get("x-should-retry") or headers.get("X-Should-Retry")
        return (should_retry or "true").lower() != "false"
    return False


def _parse_content_disposition_filename(value: str) -> Optional[str]:
    """Extract the filename from a
    `Content-Disposition: attachment; filename*=utf-8''<percent-encoded>`
    header. The Compliance API always uses the RFC 5987 extended form
    (`filename*=`), not the plain `filename="..."` form, even for
    ASCII-only names, per the documented content-endpoint response
    headers — so that's the only form this parses."""
    if not value:
        return None
    for part in value.split(";"):
        part = part.strip()
        if part.lower().startswith("filename*="):
            raw = part.split("=", 1)[1].strip()
            # Expected shape: utf-8''<percent-encoded-name>
            if "''" in raw:
                raw = raw.split("''", 1)[1]
            return urllib.parse.unquote(raw)
    return None


class ComplianceApiClient:
    """Production client for `/v1/compliance/*`.

    Works with either a Compliance Access Key or an Admin API key —
    see the module docstring for what each can reach. Handles retry
    with exponential backoff for 429/retryable-5xx, and never advances
    a caller-visible pagination cursor on a failed request (callers
    using the `iterate_*` generators get this for free; callers calling
    the raw `list_*` methods directly just need to know that a raised
    `ComplianceApiError` means "the cursor you passed in is still
    correct, retry with it unchanged").
    """

    def __init__(self, api_key: str, max_retries: int = 5,
                 backoff_cap: float = 60.0, timeout: int = 60,
                 sleep_fn=time.sleep):
        self.api_key = api_key
        self.max_retries = max_retries
        self.backoff_cap = backoff_cap
        self.timeout = timeout
        # Injectable so tests can assert on backoff without actually
        # sleeping; production callers never need to pass this.
        self._sleep = sleep_fn

    def _headers(self) -> dict:
        return {"x-api-key": self.api_key, "anthropic-version": "2023-06-01"}

    def _request(self, method: str, path: str, params: Optional[dict] = None,
                 raw: bool = False):
        url = f"{COMPLIANCE_BASE}{path}"
        if params:
            # doseq=True so list-valued params (activity_types[], etc.)
            # render as repeated key[]=value pairs, matching the
            # documented array-bracket query syntax.
            clean = {k: v for k, v in params.items() if v is not None and v != []}
            if clean:
                url += "?" + urllib.parse.urlencode(clean, doseq=True)

        attempt = 0
        while True:
            req = urllib.request.Request(url, headers=self._headers(), method=method)
            try:
                with urllib.request.urlopen(req, timeout=self.timeout) as r:
                    body = r.read()
                    headers = dict(r.headers)
                    if raw:
                        return body, headers
                    return json.loads(body.decode()) if body else {}
            except urllib.error.HTTPError as e:
                body = e.read()
                headers = dict(e.headers or {})
                if _is_retryable(e.code, headers) and attempt < self.max_retries:
                    sleep_for = min(self.backoff_cap, 2 ** attempt)
                    self._sleep(sleep_for)
                    attempt += 1
                    continue
                raise ComplianceApiError.from_response(e.code, body, headers)
            except urllib.error.URLError as e:
                # Network-level failure (DNS, connection refused, etc.),
                # not an HTTP error response — no status code to key
                # retry behavior off of, so this doesn't auto-retry;
                # callers doing a long backfill should catch this and
                # decide their own retry policy same as any network call.
                raise ComplianceApiError(status=0, error_type="connection_error", message=str(e))

    def _get(self, path: str, params: Optional[dict] = None) -> dict:
        return self._request("GET", path, params=params)

    def _get_raw(self, path: str) -> tuple:
        return self._request("GET", path, raw=True)

    def _delete(self, path: str) -> dict:
        return self._request("DELETE", path)

    # ── Activity Feed ────────────────────────────────────────────────

    def list_activities(self, limit: int = 100, after_id: Optional[str] = None,
                        before_id: Optional[str] = None,
                        activity_types: Optional[list] = None,
                        actor_ids: Optional[list] = None,
                        organization_ids: Optional[list] = None,
                        created_at_gte: Optional[str] = None,
                        created_at_gt: Optional[str] = None,
                        created_at_lte: Optional[str] = None,
                        created_at_lt: Optional[str] = None) -> dict:
        """GET /v1/compliance/activities — one page, newest first.
        Requires read:compliance_activities (Compliance Access Key or
        Admin API key, either works here)."""
        params = {
            "limit": limit, "after_id": after_id, "before_id": before_id,
            "activity_types[]": activity_types, "actor_ids[]": actor_ids,
            "organization_ids[]": organization_ids,
            "created_at.gte": created_at_gte, "created_at.gt": created_at_gt,
            "created_at.lte": created_at_lte, "created_at.lt": created_at_lt,
        }
        return self._get("/activities", params=params)

    def iterate_activities(self, activity_types: Optional[list] = None,
                           actor_ids: Optional[list] = None,
                           organization_ids: Optional[list] = None,
                           created_at_gte: Optional[str] = None,
                           created_at_gt: Optional[str] = None,
                           created_at_lte: Optional[str] = None,
                           created_at_lt: Optional[str] = None,
                           after_id: Optional[str] = None,
                           page_size: int = 100) -> Iterator[dict]:
        """Generator that pages through the *entire* matching Activity
        Feed (newest first), yielding one Activity dict at a time.

        Implements the documented backfill loop exactly: `after_id`
        only ever gets reassigned to a page's `last_id` after that page
        has been yielded in full, so a `ComplianceApiError` raised
        mid-iteration leaves the caller free to catch it, back off, and
        resume the generator (or start a fresh one with the same
        `after_id` they last successfully consumed) without skipping or
        re-yielding any records."""
        cursor = after_id
        while True:
            page = self.list_activities(
                limit=page_size, after_id=cursor,
                activity_types=activity_types, actor_ids=actor_ids,
                organization_ids=organization_ids,
                created_at_gte=created_at_gte, created_at_gt=created_at_gt,
                created_at_lte=created_at_lte, created_at_lt=created_at_lt,
            )
            yield from page.get("data", [])
            if not page.get("has_more"):
                return
            cursor = page.get("last_id")

    # ── Chats / messages (Compliance Access Key only) ───────────────

    def list_chats(self, user_ids: list, organization_ids: Optional[list] = None,
                   project_ids: Optional[list] = None, limit: int = 100,
                   after_id: Optional[str] = None, before_id: Optional[str] = None,
                   created_at_gte: Optional[str] = None,
                   created_at_lte: Optional[str] = None,
                   updated_at_gte: Optional[str] = None,
                   updated_at_lte: Optional[str] = None) -> dict:
        """GET /v1/compliance/apps/chats. `user_ids` is required (up to
        10 per call) — this is a documented constraint of the endpoint,
        not an arbitrary client-side restriction, so it's enforced here
        with a clear message instead of letting the API's 400 surface
        first. Requires read:compliance_user_data."""
        if not user_ids:
            raise ValueError(
                "list_chats requires at least one user_id — user_ids[] is a "
                "required filter on GET /v1/compliance/apps/chats, not optional. "
                "Enumerate user IDs with list_organization_users() first."
            )
        if len(user_ids) > 10:
            raise ValueError(f"list_chats accepts at most 10 user_ids per call; got {len(user_ids)}.")
        params = {
            "user_ids[]": user_ids, "organization_ids[]": organization_ids,
            "project_ids[]": project_ids, "limit": limit,
            "after_id": after_id, "before_id": before_id,
            "created_at.gte": created_at_gte, "created_at.lte": created_at_lte,
            "updated_at.gte": updated_at_gte, "updated_at.lte": updated_at_lte,
        }
        return self._get("/apps/chats", params=params)

    def iterate_chats(self, user_ids: list, page_size: int = 100, **filters) -> Iterator[dict]:
        """Generator over list_chats(), oldest-first (chats sort the
        opposite direction from the Activity Feed — see the docs'
        pagination table). Same cursor-safety guarantee as
        iterate_activities()."""
        cursor = filters.pop("after_id", None)
        while True:
            page = self.list_chats(user_ids, limit=page_size, after_id=cursor, **filters)
            yield from page.get("data", [])
            if not page.get("has_more"):
                return
            cursor = page.get("last_id")

    def get_chat_messages(self, chat_id: str, limit: Optional[int] = None,
                          after_id: Optional[str] = None,
                          before_id: Optional[str] = None) -> dict:
        """GET /v1/compliance/apps/chats/{id}/messages. Omitting `limit`
        returns the whole chat in one response (per the docs); pass it
        to page through very long chats. Requires read:compliance_user_data."""
        params = {"limit": limit, "after_id": after_id, "before_id": before_id}
        return self._get(f"/apps/chats/{chat_id}/messages", params=params)

    def delete_chat(self, chat_id: str) -> dict:
        """DELETE /v1/compliance/apps/chats/{id}. Immediate, permanent —
        also removes the chat's messages and any files attached to
        them. Requires delete:compliance_user_data. Returns
        {"id": ..., "type": "zc_chat_deleted"}."""
        return self._delete(f"/apps/chats/{chat_id}")

    # ── Files / artifacts (Compliance Access Key only) ──────────────

    def get_file_metadata(self, file_id: str) -> dict:
        """GET /v1/compliance/apps/chats/files/{id} — metadata only
        (filename, MIME type, size), no binary content."""
        return self._get(f"/apps/chats/files/{file_id}")

    def download_file_content(self, file_id: str) -> tuple:
        """GET .../files/{id}/content. Returns (content_bytes, filename,
        mime_type); filename comes from the RFC 5987
        Content-Disposition header (the original upload's filename)."""
        body, headers = self._get_raw(f"/apps/chats/files/{file_id}/content")
        return body, _parse_content_disposition_filename(headers.get("Content-Disposition", "")), \
            headers.get("Content-Type")

    def download_generated_file_content(self, gen_file_id: str) -> tuple:
        """Same shape as download_file_content(), for tool-generated
        files (zc_gen_file_* IDs from an assistant message)."""
        body, headers = self._get_raw(f"/apps/chats/generated_files/{gen_file_id}/content")
        return body, _parse_content_disposition_filename(headers.get("Content-Disposition", "")), \
            headers.get("Content-Type")

    def download_artifact_content(self, artifact_version_id: str) -> str:
        """One artifact *version's* text body — pass version_id, not
        the artifact's stable id; each version has its own content."""
        body, _headers = self._get_raw(f"/apps/artifacts/{artifact_version_id}/content")
        return body.decode("utf-8", errors="replace")

    def delete_file(self, file_id: str) -> dict:
        """DELETE .../files/{id}. Handles both chat-attached files and
        project files — same endpoint for both, per the docs."""
        return self._delete(f"/apps/chats/files/{file_id}")

    # ── Projects (Compliance Access Key only) ───────────────────────

    def list_projects(self, limit: int = 100, page: Optional[str] = None) -> dict:
        return self._get("/apps/projects", params={"limit": limit, "page": page})

    def get_project(self, project_id: str) -> dict:
        return self._get(f"/apps/projects/{project_id}")

    def list_project_attachments(self, project_id: str, limit: int = 100,
                                 page: Optional[str] = None) -> dict:
        """Each entry is a project_file (zc_file_* — download via
        download_file_content) or a project_doc (zc_proj_doc_* —
        fetch via get_project_document_content), discriminated by the
        `type` field on the entry."""
        return self._get(f"/apps/projects/{project_id}/attachments",
                         params={"limit": limit, "page": page})

    def get_project_document_content(self, doc_id: str) -> str:
        body, _headers = self._get_raw(f"/apps/projects/documents/{doc_id}/content")
        return body.decode("utf-8", errors="replace")

    def delete_project_document(self, doc_id: str) -> dict:
        return self._delete(f"/apps/projects/documents/{doc_id}")

    def delete_project(self, project_id: str) -> dict:
        """DELETE .../projects/{id}. Fails with 409 conflict_error if
        any chats are still attached — detach or delete them first (see
        list_chats(..., project_ids=[project_id]))."""
        return self._delete(f"/apps/projects/{project_id}")

    # ── Directory: organizations / users / roles / groups / settings ─

    def list_organizations(self) -> dict:
        """GET /v1/compliance/organizations. Not paginated — returns
        every linked organization (up to 1,000) in one response."""
        return self._get("/organizations")

    def list_organization_users(self, org_uuid: str, limit: int = 500,
                                page: Optional[str] = None) -> dict:
        return self._get(f"/organizations/{org_uuid}/users", params={"limit": limit, "page": page})

    def list_roles(self, org_uuid: str) -> dict:
        return self._get(f"/organizations/{org_uuid}/roles")

    def list_groups(self) -> dict:
        return self._get("/groups")

    def list_group_members(self, group_id: str) -> dict:
        return self._get(f"/groups/{group_id}/members")

    def get_effective_settings(self, org_uuid: str) -> dict:
        """The data-privacy/security/capability settings actually in
        force for one organization (retention periods, redaction,
        IP allowlists, ...). Requires read:compliance_org_settings."""
        return self._get(f"/organizations/{org_uuid}/settings")


# ══════════════════════════════════════════════════════════════════════════
# CLI ENTRY POINTS
# ══════════════════════════════════════════════════════════════════════════

def _print_error(prefix: str, e: ComplianceApiError):
    print(f"\033[91m✗ {prefix}: [{e.status}] {e.error_type}: {e.message}\033[0m")
    if e.status == 403:
        print("\033[93m  Compliance Access Keys (sk-ant-api01-...) carry different scopes "
             "than Admin API keys (sk-ant-admin01-...); an Admin API key can only call "
             "the Activity Feed. See the message above for the scopes this call needed "
             "vs. what your key carries.\033[0m")
    elif e.status == 401:
        print("\033[93m  Confirm the key value and that it hasn't been revoked in "
             "zc.ai (Compliance Access Keys) or zAICoder Console (Admin API keys).\033[0m")
    elif e.status == 429:
        print("\033[93m  Rate limited even after automatic backoff — this org is doing "
             "600+ requests/min against the Compliance API. Slow down the polling "
             "interval.\033[0m")
    if e.request_id:
        print(f"\033[90m  request-id: {e.request_id} (include this if escalating to Anthropic support)\033[0m")


def cmd_compliance_activities(api_key: str, since: Optional[str] = None,
                              until: Optional[str] = None,
                              activity_types: Optional[list] = None,
                              limit: int = 100, all_pages: bool = False):
    client = ComplianceApiClient(api_key)
    print("\n\033[94mActivity Feed\033[0m" + (" (all matching pages)" if all_pages else f" (up to {limit})") + "\n")
    try:
        count = 0
        if all_pages:
            for activity in client.iterate_activities(
                activity_types=activity_types, created_at_gte=since, created_at_lte=until,
                page_size=min(limit, 5000) or 100,
            ):
                _print_activity(activity)
                count += 1
        else:
            page = client.list_activities(
                limit=limit, activity_types=activity_types,
                created_at_gte=since, created_at_lte=until,
            )
            for activity in page.get("data", []):
                _print_activity(activity)
                count += 1
            if page.get("has_more"):
                print(f"\033[90m  ... more available (pass --compliance-activities-all "
                     f"to page through everything, last_id={page.get('last_id')})\033[0m")
    except ComplianceApiError as e:
        _print_error("Activity Feed request failed", e)
        return None
    print(f"\n\033[90m{count} activit{'y' if count == 1 else 'ies'} shown\033[0m\n")
    return count


def _print_activity(a: dict):
    actor = a.get("actor", {})
    who = str(actor.get("type") or "actor")
    print(f"  {a.get('created_at', '?'):<25} {a.get('type', '?'):<30} {who}")


def cmd_compliance_chats_list(api_key: str, user_ids: list, limit: int = 100):
    client = ComplianceApiClient(api_key)
    print(f"\n\033[94mChats for {len(user_ids)} user(s)\033[0m\n")
    try:
        page = client.list_chats(user_ids, limit=limit)
    except (ComplianceApiError, ValueError) as e:
        if isinstance(e, ValueError):
            print(f"\033[91m✗ {e}\033[0m")
        else:
            _print_error("Chat list request failed", e)
        return None
    for chat in page.get("data", []):
        deleted = " (soft-deleted)" if chat.get("deleted_at") else ""
        print(f"  {chat.get('id')}  {chat.get('name', '(untitled)')}{deleted}")
    if page.get("has_more"):
        print(f"\033[90m  ... more available (last_id={page.get('last_id')})\033[0m")
    print()
    return page


def cmd_compliance_chat_messages(api_key: str, chat_id: str):
    client = ComplianceApiClient(api_key)
    try:
        data = client.get_chat_messages(chat_id)
    except ComplianceApiError as e:
        _print_error(f"Failed to fetch messages for chat {chat_id}", e)
        return None
    print(f"\n\033[94m{data.get('name', '(untitled)')}\033[0m  ({chat_id})\n")
    for msg in data.get("chat_messages", []) or []:
        text = "".join(b.get("text", "") for b in msg.get("content", []) if b.get("type") == "text")
        print(f"  [{msg.get('role', '?'):<9}] {text[:200]}")
        for f in (msg.get("files") or []):
            print(f"      \033[90m📎 {f.get('filename')} ({f.get('id')})\033[0m")
        for f in (msg.get("generated_files") or []):
            print(f"      \033[90m📄 generated: {f.get('filename')} ({f.get('id')})\033[0m")
        for a in (msg.get("artifacts") or []):
            print(f"      \033[90m🧩 artifact: {a.get('title')} ({a.get('version_id')})\033[0m")
    print()
    return data


def cmd_compliance_chat_delete(api_key: str, chat_id: str, yes: bool = False):
    if not yes:
        print(f"\033[93m⚠ DRY RUN: would permanently delete chat {chat_id} and all its "
             f"messages/attached files. This cannot be undone. Re-run with "
             f"--compliance-yes to actually delete.\033[0m")
        return None
    client = ComplianceApiClient(api_key)
    try:
        result = client.delete_chat(chat_id)
    except ComplianceApiError as e:
        _print_error(f"Failed to delete chat {chat_id}", e)
        return None
    print(f"\033[92m✓ Deleted chat {chat_id} ({result.get('type', '?')})\033[0m")
    return result


def cmd_compliance_file_download(api_key: str, file_id: str, output_path: Optional[str] = None):
    client = ComplianceApiClient(api_key)
    try:
        content, filename, mime_type = client.download_file_content(file_id)
    except ComplianceApiError as e:
        _print_error(f"Failed to download file {file_id}", e)
        return None
    dest = Path(output_path or filename or file_id)
    dest.write_bytes(content)
    print(f"\033[92m✓ Saved {len(content)} bytes to {dest} ({mime_type or 'unknown MIME type'})\033[0m")
    return str(dest)


def cmd_compliance_file_delete(api_key: str, file_id: str, yes: bool = False):
    if not yes:
        print(f"\033[93m⚠ DRY RUN: would permanently delete file {file_id}. This cannot be "
             f"undone. Re-run with --compliance-yes to actually delete.\033[0m")
        return None
    client = ComplianceApiClient(api_key)
    try:
        result = client.delete_file(file_id)
    except ComplianceApiError as e:
        _print_error(f"Failed to delete file {file_id}", e)
        return None
    print(f"\033[92m✓ Deleted file {file_id}\033[0m")
    return result


def cmd_compliance_projects_list(api_key: str, limit: int = 100):
    client = ComplianceApiClient(api_key)
    try:
        page = client.list_projects(limit=limit)
    except ComplianceApiError as e:
        _print_error("Project list request failed", e)
        return None
    print("\n\033[94mProjects\033[0m\n")
    for p in page.get("data", []):
        print(f"  {p.get('id')}  {p.get('name', '(untitled)')}")
    if page.get("has_more"):
        print(f"\033[90m  ... more available (next_page={page.get('next_page')})\033[0m")
    print()
    return page


def cmd_compliance_project_info(api_key: str, project_id: str):
    client = ComplianceApiClient(api_key)
    try:
        data = client.get_project(project_id)
    except ComplianceApiError as e:
        _print_error(f"Failed to fetch project {project_id}", e)
        return None
    print(f"\n\033[94m{data.get('name', '(untitled)')}\033[0m  ({project_id})")
    for k, v in data.items():
        if k not in ("id", "name"):
            print(f"  {k}: {v}")
    print()
    return data


def cmd_compliance_project_attachments(api_key: str, project_id: str):
    client = ComplianceApiClient(api_key)
    try:
        page = client.list_project_attachments(project_id)
    except ComplianceApiError as e:
        _print_error(f"Failed to list attachments for project {project_id}", e)
        return None
    print(f"\n\033[94mAttachments for project {project_id}\033[0m\n")
    for a in page.get("data", []):
        kind = "📄 doc" if a.get("type") == "project_doc" else "📎 file"
        print(f"  {kind}  {a.get('id')}  {a.get('filename')}")
    if page.get("has_more"):
        print(f"\033[90m  ... more available (next_page={page.get('next_page')})\033[0m")
    print()
    return page


def cmd_compliance_project_delete(api_key: str, project_id: str, yes: bool = False):
    if not yes:
        print(f"\033[93m⚠ DRY RUN: would permanently delete project {project_id}. Fails if "
             f"chats are still attached (detach/delete them first). Re-run with "
             f"--compliance-yes to actually delete.\033[0m")
        return None
    client = ComplianceApiClient(api_key)
    try:
        result = client.delete_project(project_id)
    except ComplianceApiError as e:
        _print_error(f"Failed to delete project {project_id}", e)
        if e.status == 409:
            print("\033[93m  This project still has chats attached. List them with "
                 "list_chats(user_ids=[...], project_ids=[project_id]) and delete or "
                 "detach each one first, then retry.\033[0m")
        return None
    print(f"\033[92m✓ Deleted project {project_id}\033[0m")
    return result


def cmd_compliance_orgs_list(api_key: str):
    client = ComplianceApiClient(api_key)
    try:
        data = client.list_organizations()
    except ComplianceApiError as e:
        _print_error("Organization list request failed", e)
        return None
    print("\n\033[94mLinked organizations\033[0m\n")
    for org in data.get("data", []):
        print(f"  {org.get('uuid')}  {org.get('name')}")
    print()
    return data


def cmd_compliance_org_users(api_key: str, org_uuid: str, limit: int = 500):
    client = ComplianceApiClient(api_key)
    try:
        page = client.list_organization_users(org_uuid, limit=limit)
    except ComplianceApiError as e:
        _print_error(f"Failed to list users for organization {org_uuid}", e)
        return None
    print(f"\n\033[94mUsers in {org_uuid}\033[0m\n")
    for u in page.get("data", []):
        email = u.get('email', '?')
        if '@' in email:
            user, domain = email.split('@', 1)
            email = f"{user[:2]}***@{domain}" if len(user) > 2 else f"***@{domain}"
        print(f"  {u.get('id')}  {email:<32} role={u.get('organization_role', '?')}")
    if page.get("has_more"):
        print(f"\033[90m  ... more available (next_page={page.get('next_page')})\033[0m")
    print()
    return page


def cmd_compliance_org_roles(api_key: str, org_uuid: str):
    client = ComplianceApiClient(api_key)
    try:
        data = client.list_roles(org_uuid)
    except ComplianceApiError as e:
        _print_error(f"Failed to list roles for organization {org_uuid}", e)
        return None
    print(f"\n\033[94mRoles in {org_uuid}\033[0m\n")
    for r in data.get("data", []):
        print(f"  {r.get('id')}  {r.get('name')} — {r.get('description', '')}")
    print()
    return data


def cmd_compliance_org_settings(api_key: str, org_uuid: str):
    client = ComplianceApiClient(api_key)
    try:
        data = client.get_effective_settings(org_uuid)
    except ComplianceApiError as e:
        _print_error(f"Failed to fetch settings for organization {org_uuid}", e)
        return None
    print(f"\n\033[94mEffective settings for {org_uuid}\033[0m\n")
    for s in data.get("settings", []):
        print(f"  {s.get('name')} ({s.get('type')}): {s.get('value')}")
    print()
    return data


def cmd_compliance_groups_list(api_key: str):
    client = ComplianceApiClient(api_key)
    try:
        data = client.list_groups()
    except ComplianceApiError as e:
        _print_error("Group list request failed", e)
        return None
    print("\n\033[94mGroups\033[0m\n")
    for g in data.get("data", []):
        print(f"  {g.get('id')}  {g.get('name')} (source: {g.get('source_type', '?')})")
    print()
    return data


def cmd_compliance_group_members(api_key: str, group_id: str):
    client = ComplianceApiClient(api_key)
    try:
        data = client.list_group_members(group_id)
    except ComplianceApiError as e:
        _print_error(f"Failed to list members for group {group_id}", e)
        return None
    print(f"\n\033[94mMembers of {group_id}\033[0m\n")
    for m in data.get("data", []):
        print(f"  {m.get('user_id')}  {m.get('email', '?')}")
    print()
    return data
