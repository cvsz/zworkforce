# Scrutinize Hardening Design

**Date:** 2026-08-10

**Status:** Approved for implementation by `/scrutinize do all to complete`

## Goal

Close the four repository audit findings with the smallest design that makes the
existing U.Perfect local release truthful, testable, and operable without paid
infrastructure or provider credentials.

## Simpler Alternative Check

The tempting alternatives are to add Celery/Redis, install Alembic/SQLAlchemy,
or claim that the current boolean webhook header is provider verification. None
fits this repository. The application already has SQLite transactions, a
notification outbox, and a normalized webhook boundary. A native SQLite
migration runner, a small polling worker, and HMAC verification at the HTTP
boundary solve the load-bearing gaps with no new service dependency. Real
Facebook, LINE, TikTok Shop, and Shopee adapters remain a separate account-owner
and provider-approval gate.

## Scope

### 1. Canonical product assets

`assets/loe_vit_c_aura_serum/` becomes the sole canonical VIT C media directory.
The existing body-serum media and documents are moved there with `git mv`, not
regenerated or deleted. The two different dossiers keep distinct names:

- `Loe_Vit_C_Aura_Serum_EN(1).md` and `_TH(1).md` remain the technical dossier.
- The shorter body/promotion dossier becomes
  `Loe_Vit_C_Aura_Serum_Promo_EN.md` and `_TH.md`.
- `body.txt` becomes `body_notes.txt`.

The asset manifest is updated to the canonical path and a test rejects the old
directory name, missing files, spaces, and non-ASCII directory components.
`assets/chatbot/sales_response_assets.json` retains stable asset IDs and is
checked against the manifest where filesystem paths are involved.

### 2. Native schema migration metadata

`app/migrations.py` owns an idempotent SQLite migration runner. Existing
databases record schema version 1 as a baseline. Version 2 adds notification
outbox leasing and retry scheduling columns:

- `locked_until`
- `locked_by`
- `next_attempt_at`

Fresh database DDL includes these columns. A PostgreSQL companion migration is
kept under `migrations/002_notification_outbox_retry.sql`, and
`database_schema.sql` stays aligned. No Alembic, ORM, Redis, or paid service is
introduced.

### 3. Notification worker

The repository gets atomic notification claiming with a short lease. Delivery
claims one event at a time, sends it, marks it sent, or records a retryable
failure with bounded exponential backoff. Leases are cleared on either result,
so a crashed worker can be recovered after the lease expires.

`app/worker.py` provides `run_once()` and a polling `run_forever()` entrypoint.
`app/services/line.py` is the server-only LINE push sender using the existing
Python standard library. The worker is dormant when
`LINE_CHANNEL_ACCESS_TOKEN` or `LINE_ADMIN_DESTINATION` is absent; it never
pretends an unconfigured event was delivered and never logs secrets.

### 4. Signed webhook boundary

`app/services/webhook_auth.py` verifies the raw request body with
constant-time HMAC comparison:

- Facebook: `X-Hub-Signature-256` with `FACEBOOK_APP_SECRET`.
- LINE: `X-Line-Signature` with `LINE_CHANNEL_SECRET`.
- TikTok and Shopee: `X-UPerfect-Webhook-Signature` with dedicated local
  normalized-boundary secrets.

`POST /api/webhooks/{provider}` reads the raw body before accepting the
normalized payload. The old `X-UPerfect-Webhook-Verified: true` bypass is
removed. Missing configuration or an invalid signature returns
`WEBHOOK_SIGNATURE_INVALID` with HTTP 401. TikTok/Shopee documentation clearly
labels the endpoint as an internal normalized boundary; it is not a substitute
for their raw provider adapters.

### 5. End-to-end coverage

The suite covers the real API path from message intake through product memory,
order creation, payment evidence, confirmation, and notification outbox state.
Security tests sign the exact raw JSON bytes and cover valid, missing, tampered,
provider-specific, and duplicate requests. Worker tests cover lease claims,
success, failure, retry timing, and recovery. A browser contract check verifies
`web/app.js` calls the same API routes and contains the TH/EN settings controls;
an optional Playwright smoke test is used when the browser dependency is
available, without making the no-cost Python release depend on it.

### 6. Deployment and documentation

Docker Compose and systemd gain a separate worker process sharing the local
database volume. CI runs the complete Python test suite and compile checks.
README, operator/admin/developer manuals, API/architecture/deployment/operations
docs, asset catalog, release report, and integration guides describe the actual
worker and HMAC gates. Secrets remain environment-only and masked.

## Non-goals

- No real provider OAuth, API credentials, public webhook registration, or
  marketplace adapter is activated.
- No external queue, database, payment verifier, or paid automation platform is
  required.
- No ZIP exporter is restored; the user's earlier ZIP cancellation remains in
  force.
- No medical, inventory, shipping, payment, or provider-success claim is added
  without verified merchant/runtime data.

## Acceptance Criteria

1. All tracked VIT C assets live below one canonical directory and every
   manifest path resolves to a file.
2. A fresh database and a pre-existing database both finish at schema version 2
   without data loss; migration reruns are no-ops.
3. A confirmed order creates an outbox event that a local worker can claim and
   deliver when LINE is configured, while an unconfigured worker performs no
   network call.
4. Every normalized webhook request needs the correct provider signature over
   the exact raw body; tampering, missing secrets, and duplicates are explicit.
5. The full test suite includes the API order/outbox journey, asset and deploy
   contracts, migration/lease behavior, and frontend API/i18n contract checks.
6. Compose config, systemd unit syntax, compile checks, whitespace checks, local
   health, and public route health are freshly verified before the signed push.

## Rollback

Asset moves can be reversed with the corresponding `git mv` operations. Schema
migrations are additive and retain existing rows. The worker is independently
disabled by stopping its service. HMAC enforcement intentionally requires
updating any internal caller from the removed boolean header to a real signed
request; no provider is considered live until its adapter and credentials are
configured.
