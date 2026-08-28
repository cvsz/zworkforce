# v1.16.0 upgrade notes — Compliance API

v1.15.0 left the Compliance API as a documented gap on purpose: it's an
enterprise audit/eDiscovery/DLP surface, and the roadmap's own
recommendation was "revisit only if there's an actual concrete request
for it." That request has now landed — `zc_compliance_api.py` closes
the gap.

Nothing here changes default behavior. Every `cmd_*` in the module is
read-only except the four hard-deletes (chat/file/project-document/
project), and those are dry-run by default — they only execute with an
explicit `--compliance-yes`.

## What this is, and how it differs from `zc_admin_api.py`

`zc_admin_api.py` wraps org-level usage/cost *reporting* and API key
*lifecycle* — aggregate numbers, not content. `zc_compliance_api.py`
is the Activity Feed (who did what, chronologically, across the org)
plus, with the right key, the ability to read or hard-delete the actual
chats, files, and projects those activities reference. Different
endpoint family (`/v1/compliance/*` vs `/v1/organizations/*`), different
purpose, and — the single most important operational detail — a
different key model:

- A **Compliance Access Key** (`sk-ant-api01-...`, created in zc.ai)
  reaches every endpoint here, but only the scopes it was granted at
  creation time (`read:compliance_activities`,
  `read:compliance_org_data`, `read:compliance_user_data`,
  `read:compliance_org_settings`, `delete:compliance_user_data`).
  Scopes are immutable after creation.
- An **Admin API key** (`sk-ant-admin01-...`, the same key type
  `zc_admin_api.py` uses) reaches *only*
  `GET /v1/compliance/activities`, and only if it was created after the
  Compliance API was enabled for the org. Every other endpoint returns
  403 for an Admin API key — there's no scope to add to unlock them.

```bash
ai-coder --compliance-activities --compliance-api-key sk-ant-api01-...
ai-coder --compliance-activities-all \
  --compliance-activities-since 2026-06-01T00:00:00Z \
  --compliance-activity-types zc_chat_created,zc_file_uploaded

ai-coder --compliance-chats-list --compliance-user-ids user_abc,user_def
ai-coder --compliance-chat-messages chat_123

# Destructive — dry-run by default, prints what *would* happen:
ai-coder --compliance-chat-delete chat_123
# Actually deletes, permanently, no recovery window:
ai-coder --compliance-chat-delete chat_123 --compliance-yes
```

Directory endpoints (`--compliance-orgs-list`, `--compliance-org-users`,
`--compliance-org-roles`, `--compliance-org-settings`,
`--compliance-groups-list`, `--compliance-group-members`) round out the
module for RBAC/SCIM inspection.

## Reliability contract

Matches `platform.zc.com/docs/en/manage-zc/compliance-errors`
exactly rather than using a generic retry wrapper:

- 429 and retryable 5xx (502/503/504/529, or 500 without
  `x-should-retry: false`) retry with exponential backoff (1s, 2s, 4s,
  ... capped at 60s), up to `max_retries`.
- 400/401/403/404/409 never retry.
- Pagination cursors in `iterate_activities`/`iterate_chats` only advance
  after a page is *successfully* retrieved — a raised
  `ComplianceApiError` always leaves the last-known cursor untouched.
- Errors carry the `request-id` header and a stable `error_type` for
  callers to match on instead of the message string.

## Key fallback order

`--compliance-api-key` → `ZC_COMPLIANCE_API_KEY` →
`--admin-api-key` → `ZC_ADMIN_API_KEY`. The Admin API key
fallback only unlocks `--compliance-activities`; every other flag will
hit a 403 with an Admin API key and the error message says so.
