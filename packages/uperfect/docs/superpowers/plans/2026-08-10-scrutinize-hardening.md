# Scrutinize Hardening Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remediate the repository audit with canonical assets, additive migrations, a local notification worker, HMAC webhook verification, full-path tests, and truthful deployment/docs.

**Architecture:** Keep the current FastAPI + SQLite design. Add a native migration runner and transactional outbox lease/retry primitives, then run delivery in a separate Python worker using the standard library LINE client. Verify raw webhook bytes in the API before the existing normalized integration service; provider adapters and credentials remain out of scope.

**Tech Stack:** Python 3.12, FastAPI, SQLite, standard-library `hmac`/`urllib`, pytest, Docker Compose, systemd, static PWA JavaScript.

## Global Constraints

- Keep the runtime local-only on `192.168.74.130` and add no paid dependencies.
- Never store, print, or return tokens, signing secrets, PINs, or passphrases.
- Preserve every existing VIT C asset byte while consolidating paths with `git mv`.
- Use TDD for behavior changes: write a failing test, run it red, implement minimally, then run green.
- Keep normalized TikTok/Shopee webhook intake explicitly distinct from raw provider adapters.
- Keep the canceled ZIP exporter canceled.

---

### Task 1: Lock the approved design

**Files:**
- Create: `docs/superpowers/specs/2026-08-10-scrutinize-hardening-design.md`
- Create: `docs/superpowers/plans/2026-08-10-scrutinize-hardening.md`

**Interfaces:**
- Produces the architecture, boundaries, acceptance criteria, and ordered test-first work used by all later tasks.

- [x] **Step 1: Write and self-review the spec and plan**

  Check for placeholders, contradictory provider claims, secret leakage, and a task for every acceptance criterion.

- [x] **Step 2: Commit the design checkpoint**

  Run:

  ```bash
  git add docs/superpowers/specs/2026-08-10-scrutinize-hardening-design.md docs/superpowers/plans/2026-08-10-scrutinize-hardening.md
  git commit -S -m "docs: define scrutinize hardening"
  ```

### Task 2: Make the asset and deployment contracts fail first

**Files:**
- Modify: `tests/test_asset_manifest.py`
- Modify: `tests/test_ci_and_deploy.py`

**Interfaces:**
- Tests require one canonical VIT C directory, a worker service, and a worker systemd unit.

- [ ] **Step 1: Add failing assertions**

  Assert no manifest path or directory uses `loe_vit_c_aura_body_serum`, all VIT C files are under `assets/loe_vit_c_aura_serum/`, and Compose/systemd expose `python -m app.worker`.

- [ ] **Step 2: Run the focused tests red**

  Run `python -m pytest -q tests/test_asset_manifest.py tests/test_ci_and_deploy.py`.
  Expected: failure because the old directory and worker deployment do not yet satisfy the contract.

- [ ] **Step 3: Consolidate assets and update manifest/catalog**

  Use `git mv` for media and dossier renames, update `assets/chatbot/asset-manifest.json`, then update `docs/ASSET-CATALOG.md` with canonical VIT C and mala/soap coverage.

- [ ] **Step 4: Run the focused tests green**

  Run the same pytest command and verify every path resolves.

### Task 3: Add migration metadata and outbox leasing

**Files:**
- Create: `app/migrations.py`
- Create: `migrations/002_notification_outbox_retry.sql`
- Modify: `app/database.py`
- Modify: `app/repositories.py`
- Modify: `database_schema.sql`
- Create: `tests/test_migrations.py`
- Modify: `tests/test_repositories.py`

**Interfaces:**
- `Database.initialize()` records baseline version 1 and applies version 2.
- `Repository.claim_next_notification(worker_id, lease_seconds=60)` atomically claims one retryable event.
- `Repository.pending_notifications()` remains the UI listing; `claim_notification()` is the worker-only mutation.

- [ ] **Step 1: Write migration/lease tests**

  Cover fresh and legacy databases, idempotent rerun, schema version 2, one successful claim, a live lease blocking a second claim, expired lease recovery, and retry scheduling after failure.

- [ ] **Step 2: Run migration tests red**

  Run `python -m pytest -q tests/test_migrations.py tests/test_repositories.py`.
  Expected: failure because migration metadata, columns, and claim APIs do not exist.

- [ ] **Step 3: Implement additive migration and repository primitives**

  Keep existing tables/data, add the three outbox columns, filter worker claims by `next_attempt_at`, clear leases on success/failure, and use bounded exponential retry timestamps.

- [ ] **Step 4: Run focused tests green**

  Run `python -m pytest -q tests/test_migrations.py tests/test_repositories.py tests/test_notifications.py`.

### Task 4: Add a real local notification worker

**Files:**
- Create: `app/services/line.py`
- Create: `app/worker.py`
- Create: `tests/test_worker.py`
- Modify: `app/services/notifications.py`
- Modify: `tests/test_notifications.py`

**Interfaces:**
- `NotificationService.deliver_pending(sender, worker_id=None)` claims leased events and returns `DeliverySummary`.
- `NotificationWorker.run_once()` delivers only when LINE token and destination are configured.
- `app.worker` runs a bounded polling loop with `UPERFECT_WORKER_INTERVAL_SECONDS`.

- [ ] **Step 1: Write worker tests**

  Cover configured delivery through an injected sender, dormant no-credential behavior with no sender call, success/failure summaries, and recovery after a lease expires.

- [ ] **Step 2: Run worker tests red**

  Run `python -m pytest -q tests/test_worker.py tests/test_notifications.py`.
  Expected: failure because the worker, sender, and lease-aware service are absent.

- [ ] **Step 3: Implement the worker and LINE sender**

  Use `urllib.request` for LINE push, cap text at the LINE message limit, never log Authorization headers, and make missing configuration a no-op rather than a fake success.

- [ ] **Step 4: Run focused tests green**

  Run `python -m pytest -q tests/test_worker.py tests/test_notifications.py tests/test_orders.py`.

### Task 5: Enforce signed normalized webhooks

**Files:**
- Create: `app/services/webhook_auth.py`
- Create: `tests/test_webhook_security.py`
- Modify: `app/config.py`
- Modify: `app/api.py`
- Modify: `app/services/integrations.py`
- Modify: `app/seed.py`
- Modify: `tests/conftest.py`
- Modify: `tests/test_api.py`
- Modify: `tests/test_integrations.py`
- Modify: `.env.example`

**Interfaces:**
- `WebhookVerifier.verify(provider, raw_body, headers)` returns a boolean after constant-time comparison.
- `IntegrationService.verify_request(provider, raw_body, headers)` delegates to the verifier.
- `POST /api/webhooks/{provider}` accepts only a valid provider signature over the exact body bytes.

- [ ] **Step 1: Write signed-request tests**

  Cover Facebook hex, LINE base64, normalized TikTok/Shopee HMAC, missing secret, tampered body, removed boolean bypass, valid duplicate idempotency, and secret-free API output.

- [ ] **Step 2: Run security tests red**

  Run `python -m pytest -q tests/test_webhook_security.py tests/test_api.py tests/test_integrations.py`.
  Expected: failure because the route still trusts `X-UPerfect-Webhook-Verified` and no HMAC verifier exists.

- [ ] **Step 3: Implement raw-body verification**

  Add environment-only secret fields, LINE support in `SUPPORTED_PROVIDERS`, exact header parsing, HTTP 401 `WEBHOOK_SIGNATURE_INVALID`, and no secret exposure in status/UI responses.

- [ ] **Step 4: Run focused tests green**

  Run the same pytest command and verify all webhook callers use signed bytes.

### Task 6: Add API-path E2E and frontend contracts

**Files:**
- Create: `tests/test_e2e.py`
- Create: `tests/test_frontend_contract.py`
- Modify: `web/app.js` only if the contract exposes a real defect

**Interfaces:**
- E2E follows `/api/messages` -> memory -> `/api/orders` -> payment evidence -> confirmation -> `/api/notifications`.
- Frontend contract checks the actual `fetch` routes, settings form, and TH/EN translation keys without pretending to be a browser integration test.

- [ ] **Step 1: Write the full-flow tests**

  Assert the response, persisted conversation, order state, confirmed-order outbox row, and bilingual settings/API route contract.

- [ ] **Step 2: Run E2E/contract tests red or prove existing behavior**

  Run `python -m pytest -q tests/test_e2e.py tests/test_frontend_contract.py` and fix only failures caused by the hardening work.

- [ ] **Step 3: Add an optional Playwright smoke path**

  Keep it skipped when Playwright is unavailable; when installed, load the local server, toggle TH/EN, open settings, and submit a local message.

- [ ] **Step 4: Run focused tests green**

  Run the focused command again and record whether the optional browser test was skipped or executed.

### Task 7: Wire deployment, CI, and all project documents

**Files:**
- Create: `deploy/systemd/uperfect-worker.service`
- Modify: `deploy/docker-compose.yml`
- Modify: `.github/workflows/ci.yml`
- Modify: `README.md`, `USER-MANUAL.md`, `ADMIN-MANUAL.md`, `DEV-MANUAL.md`
- Modify: `docs/API.md`, `docs/ARCHITECTURE.md`, `docs/DEPLOYMENT.md`, `docs/OPERATIONS.md`, `docs/ASSET-CATALOG.md`
- Modify: `PROJECT-DOCUMENTATION.md`, `CHANGELOG.md`, `u_perfect_final_release_report.md`
- Modify: `docs/integrations/API_ONBOARDING_TH.md`, `docs/integrations/API_ONBOARDING_EN.md`

**Interfaces:**
- Compose runs `uperfect` and a separate `worker`, both using the same local-only data volume.
- systemd runs the API and worker as separate units with the same local host contract.
- Documentation states what is configured, what is not, how to run the worker, and how to sign normalized test webhooks.

- [ ] **Step 1: Add deployment/docs tests or assertions**

  Extend static contracts for worker command, service unit, env names, and no-cost local boundary.

- [ ] **Step 2: Implement deployment and documentation updates**

  Keep all provider credentials blank and all callback guidance public-HTTPS/account-owner gated.

- [ ] **Step 3: Run complete verification**

  Run `python -m pytest -q`, `python -m compileall -q app scripts tests`, `python -m json.tool assets/chatbot/asset-manifest.json`, `docker compose -f deploy/docker-compose.yml config`, `git diff --check`, and the secret scan.

### Task 8: Release verification and signed push

**Files:**
- Modify: any release files required by verification only.

- [ ] **Step 1: Inspect the complete diff and requirements**

  Use `git diff --stat`, `git diff --check`, `git status --short`, and review every changed path for unrelated edits or secret values.

- [ ] **Step 2: Verify local runtime and routes**

  Check `http://192.168.74.130:18765/api/health`, the asset manifest, signed webhook behavior, worker dormant behavior, and `https://uperfect.zeaz.dev/api/health` if the current route is available.

- [ ] **Step 3: Create a signed implementation commit**

  Run `git add -A && git commit -S -m "feat: harden local social commerce runtime"` only after fresh verification passes.

- [ ] **Step 4: Push and verify remote state**

  Push with the configured GitHub SSH-over-443 command if HTTPS workflow scope rejects the push, then compare `origin/main` to `HEAD` and verify the commit signature locally and remotely.
