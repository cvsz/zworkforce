# U.Perfect Audit Remediation Implementation Plan

> Historical implementation plan. The final canonical asset path and runtime
> hardening are recorded in `2026-08-10-scrutinize-hardening.md`.

> For agentic workers: REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox syntax for tracking.

**Goal:** Close the audited test, asset, CI, and deployment gaps while preserving the local-only U.Perfect runtime and fact-bound catalog.

**Architecture:** Extend the existing SQLite/service test surface without changing domain interfaces. Normalize repository-owned asset paths and update the single asset manifest that drives the Dashboard. Add isolated GitHub Actions, Docker Compose, and optional Nginx templates that document boundaries rather than enabling external providers.

**Tech Stack:** Python 3.12+, FastAPI, SQLite, pytest, GitHub Actions, Docker Compose, Nginx, Uvicorn.

## Global Constraints

- Do not add provider credentials, tokens, PINs, passphrases, or real customer data.
- Do not invent product prices, stock, shipping, efficacy, or provider approval.
- Preserve 192.168.74.130 as the LAN host and 192.168.74.130:11434 as the Ollama endpoint.
- Keep unpriced products unavailable for order creation and external providers unconfigured.
- Use ASCII lowercase underscore-separated directory names for canonical asset directories.
- Run focused tests after each test-first change and the full suite before release verification.

## File map

| Area | Create | Modify or move |
| --- | --- | --- |
| Tests | tests/test_notifications.py, tests/test_settings.py, tests/test_schemas.py, tests/test_repositories.py, tests/test_asset_manifest.py, tests/test_ci_and_deploy.py | Production code only if a behavior test exposes a defect |
| Assets | assets/loe_soap/LOE_Charcoal_Mud_Soap_TH.md, assets/loe_soap/LOE_Charcoal_Mud_Soap_EN.md | Move every manifest-referenced product directory to canonical ASCII names |
| Catalog | None | assets/chatbot/asset-manifest.json, docs/ASSET-CATALOG.md, sales_response_assets.json only when synchronization is necessary |
| CI | .github/workflows/ci.yml | .github/README.md and README.md |
| Deployment | deploy/Dockerfile, deploy/docker-compose.yml, deploy/nginx/uperfect.conf.example, deploy/README.md | docs/DEPLOYMENT.md, PROJECT-DOCUMENTATION.md, final report, CHANGELOG.md |

---

### Task 1: Add notification service tests

**Files:**
- Create: tests/test_notifications.py
- Read: app/services/notifications.py, app/repositories.py, tests/conftest.py

**Interfaces:**
- Consumes: the notifications fixture and NotificationService.enqueue,
  deliver_pending, list_pending.
- Produces: coverage for successful delivery and retryable failure.

- [ ] Step 1: Write tests for successful delivery and failed delivery.
  The success test must assert the sender receives destination/body, the
  summary is sent=1/failed=0/remaining=0, and list_pending() is empty. The
  failure test must enqueue one event, raise RuntimeError("offline") from the
  sender, and assert failed=1, remaining=1, and the row status is failed.
- [ ] Step 2: Run .venv/bin/python -m pytest -q tests/test_notifications.py.
  Before the new file exists this command must report that the path is not
  found; after writing the test, confirm collection succeeds and any assertion
  failure is about the specified behavior rather than a test typo.
- [ ] Step 3: Make the smallest production correction only if the focused
  failure identifies one. Keep failed rows retryable and keep sender errors
  server-side.
- [ ] Step 4: Run
  .venv/bin/python -m pytest -q tests/test_notifications.py tests/test_integrations.py tests/test_orders.py.
- [ ] Step 5: Commit with
  git add tests/test_notifications.py app/services/notifications.py app/repositories.py
  followed by git commit -S -m "test: cover notification outbox delivery".

### Task 2: Add settings and schema tests

**Files:**
- Create: tests/test_settings.py
- Create: tests/test_schemas.py
- Read: app/services/settings.py, app/settings.py, app/schemas.py, tests/conftest.py

**Interfaces:**
- Consumes: services.workspace_settings, default_workspace_settings, decimal_value,
  decimal_json, parse_json_object, and domain errors.
- Produces: direct coverage for settings allow-list behavior and schema helpers.

- [ ] Step 1: Write settings tests that update store_name and assistant_tone,
  assert the update persists, assert facebook_page_url is unchanged, and
  assert updating FACEBOOK_PAGE_ACCESS_TOKEN raises ValueError with
  "Unsupported workspace setting".
- [ ] Step 2: Write schema tests that assert decimal_value("169") is
  Decimal("169.00"), decimal_value("") is None, decimal_json(Decimal("169.00"))
  is 169, decimal_json(Decimal("169.50")) is 169.5, and parse_json_object("not-json")
  is {}. Also assert DomainError preserves its custom code and http_status.
- [ ] Step 3: Run
  .venv/bin/python -m pytest -q tests/test_settings.py tests/test_schemas.py.
  Before the new files exist this command must report missing paths; after
  writing them, confirm collection succeeds and any failure is behavior-level.
- [ ] Step 4: Make only the minimal correction identified by a failing test.
  Do not add token-bearing settings or change the immutable Facebook reference.
- [ ] Step 5: Run
  .venv/bin/python -m pytest -q tests/test_settings.py tests/test_schemas.py tests/test_api.py.
- [ ] Step 6: Commit with
  git add tests/test_settings.py tests/test_schemas.py app/services/settings.py app/schemas.py
  followed by git commit -S -m "test: cover settings and domain schemas".

### Task 3: Add repository persistence tests

**Files:**
- Create: tests/test_repositories.py
- Read: app/database.py, app/repositories.py, app/seed.py

**Interfaces:**
- Consumes: a temporary Database initialized with seed=True and a Repository.
- Produces: regression coverage independent of service policy.

- [ ] Step 1: Add a repository fixture that creates Database(str(tmp_path / "repository.db")),
  calls initialize(), and returns Repository(database).
- [ ] Step 2: Write tests for find_keyword_matches("วิตซีโลเอ้") returning
  LOE_VITC_SERUM with matched_alias, get_or_create_conversation returning the
  same ID for the same platform/customer, claim_webhook returning True then
  False for the same event, and notification failure followed by mark sent
  changing pending_notification_count from 1 to 0.
- [ ] Step 3: Add tests for reserve_inventory success and out-of-stock failure,
  create_order/get_order round-trip, and save_workspace_settings/load_workspace_settings.
- [ ] Step 4: Run .venv/bin/python -m pytest -q tests/test_repositories.py and
  before the new file exists confirm the path is missing; after writing it,
  confirm collection succeeds and any failure is behavior-level.
- [ ] Step 5: Make no SQL or transaction change unless a test demonstrates a
  real defect; preserve foreign keys and exact Decimal storage.
- [ ] Step 6: Run
  .venv/bin/python -m pytest -q tests/test_repositories.py tests/test_catalog.py tests/test_orders.py tests/test_integrations.py.
- [ ] Step 7: Commit with
  git add tests/test_repositories.py app/repositories.py app/database.py
  followed by git commit -S -m "test: cover sqlite repository behavior".

### Task 4: Normalize product asset ownership and paths

**Files:**
- Create: assets/loe_soap/LOE_Charcoal_Mud_Soap_TH.md
- Create: assets/loe_soap/LOE_Charcoal_Mud_Soap_EN.md
- Create: tests/test_asset_manifest.py
- Move: assets/น้ำพริกเสือร้องไห้/ to assets/suea_rong_hai_mala_chili_oil/
- Move: assets/VIT C AURA SERUM/ to assets/loe_vit_c_aura_serum/
- Move: assets/VIT C AURA BODY SERUM/ to assets/loe_vit_c_aura_body_serum/
- Move: assets/the copper/ to assets/the_copper/
- Move: the existing 707931534_10164994697921122_6595834135060529509_n.jpg to assets/loe_soap/
- Modify: assets/chatbot/asset-manifest.json and docs/ASSET-CATALOG.md

**Interfaces:**
- Consumes: the local media manifest loaded by app.services.sales_assets.
- Produces: canonical paths the API and Dashboard can serve.

- [ ] Step 1: Write a manifest test asserting a Mala path starts with
  assets/suea_rong_hai_mala_chili_oil/, a soap path starts with assets/loe_soap/,
  no path contains the old Thai directory or a non-ASCII/space-containing
  product directory, and every manifest path exists.
- [ ] Step 2: Run .venv/bin/python -m pytest -q tests/test_asset_manifest.py.
  Confirm it fails before the move because current paths use the Thai directory
  and the soap image is stored under the serum directory.
- [ ] Step 3: Move existing files without changing bytes:
  mkdir -p assets/loe_soap
  git mv assets/น้ำพริกเสือร้องไห้ assets/suea_rong_hai_mala_chili_oil
  git mv assets/VIT\ C\ AURA\ SERUM assets/loe_vit_c_aura_serum
  git mv assets/VIT\ C\ AURA\ BODY\ SERUM assets/loe_vit_c_aura_body_serum
  git mv assets/the\ copper assets/the_copper
  git mv assets/loe_vit_c_aura_serum/707931534_10164994697921122_6595834135060529509_n.jpg assets/loe_soap/
- [ ] Step 4: Add bilingual reference-only soap docs. State that price,
  stock, and final product claims require merchant confirmation.
- [ ] Step 5: Replace moved manifest paths while keeping asset IDs stable.
  Document both canonical directories in docs/ASSET-CATALOG.md and update any
  Markdown links to the old path.
- [ ] Step 6: Run
  .venv/bin/python -m pytest -q tests/test_asset_manifest.py tests/test_sales_assets.py tests/test_api.py.
- [ ] Step 7: Commit with
  git add assets docs/ASSET-CATALOG.md tests/test_asset_manifest.py
  followed by git commit -S -m "fix: normalize product asset paths".

### Task 5: Add CI and deployment templates

**Files:**
- Create: .github/workflows/ci.yml
- Create: deploy/Dockerfile
- Create: deploy/docker-compose.yml
- Create: deploy/nginx/uperfect.conf.example
- Create: deploy/README.md
- Create: tests/test_ci_and_deploy.py
- Modify: .github/README.md, README.md, docs/DEPLOYMENT.md,
  PROJECT-DOCUMENTATION.md, u_perfect_final_release_report.md, CHANGELOG.md

**Interfaces:**
- Consumes: requirements-dev.txt, app.main:app, port 18765, and the local
  Ollama URL.
- Produces: repeatable CI checks and optional deployment templates without
  provider credential handling.

- [ ] Step 1: Write test_ci_and_deploy.py tests that require the workflow to
  contain actions/checkout@v4, actions/setup-python@v5, Python 3.12,
  requirements-dev.txt, compileall, pytest, and git diff --check. Also require
  Dockerfile to contain a Python 3.12 slim base and Uvicorn on 0.0.0.0:18765,
  Compose to contain 192.168.74.130:18765:18765, local-only mode, the Ollama
  URL, zCoder:latest, and /api/health, and Nginx to contain
  uperfect.zeaz.dev and proxy_pass.
- [ ] Step 2: Run .venv/bin/python -m pytest -q tests/test_ci_and_deploy.py.
  Confirm the path is missing because the workflow and deployment files do not exist.
- [ ] Step 3: Create ci.yml for pull_request and push, checkout/setup Python,
  cached requirements-dev install, compileall, pytest, and git diff --check.
- [ ] Step 4: Create a Python 3.12 slim Dockerfile, install requirements.txt,
  copy app/assets/web/database_schema.sql, use a non-root user, and run
  Uvicorn bound to 0.0.0.0 inside the container.
- [ ] Step 5: Create Compose with named SQLite volume, database path /data/uperfect.db,
  publish 192.168.74.130:18765:18765, set UPERFECT_LOCAL_ONLY=true,
  UPERFECT_LOCAL_AI_BASE_URL=http://192.168.74.130:11434,
  UPERFECT_LOCAL_AI_MODEL=zCoder:latest, and health-check /api/health.
- [ ] Step 6: Create the optional Nginx example with server_name
  uperfect.zeaz.dev, proxy_pass http://127.0.0.1:18765, proxy headers, and
  placeholder certificate paths. It must contain no private key material.
- [ ] Step 7: Add bilingual deploy/README.md instructions covering systemd,
  Compose, Nginx, LAN binding, health checks, backup/rollback, and the fact
  that deployment does not authorize external providers.
- [ ] Step 8: Run .venv/bin/python -m pytest -q tests/test_ci_and_deploy.py.
  If Docker Compose is installed, run docker compose -f deploy/docker-compose.yml
  config; otherwise record that static tests were used.
- [ ] Step 9: Commit with
  git add .github/workflows/ci.yml deploy tests/test_ci_and_deploy.py
  .github/README.md README.md docs/DEPLOYMENT.md PROJECT-DOCUMENTATION.md
  u_perfect_final_release_report.md CHANGELOG.md
  followed by git commit -S -m "build: add ci and deployment templates".

### Task 6: Full verification and release evidence

**Files:**
- Modify: docs/RELEASE-CHECKLIST.md and docs/README.md if their inventories
  omit new files.

**Interfaces:**
- Consumes: all preceding tests and deployment/documentation artifacts.
- Produces: an evidence-backed release state without false provider claims.

- [ ] Step 1: Run
  .venv/bin/python -m pytest -q
  .venv/bin/python -m compileall -q app scripts
  node --check web/app.js
  git diff --check
- [ ] Step 2: Scan the diff for credential patterns and stale asset paths.
  Search for EAA tokens, refresh-token prefixes, private-key headers,
  GPG_PIN, provider secret assignments, and the old Thai asset directory.
- [ ] Step 3: Verify
  systemctl --user is-active uperfect.service
  curl -fsS http://192.168.74.130:18765/api/health
  curl -fsS -o /dev/null -w "%{http_code}\n" http://192.168.74.130:18765/assets/chatbot/asset-manifest.json
  The expected health body is {"status":"ok","brand":"U.Perfect"} and the
  manifest response is 200.
- [ ] Step 4: Review git status, signed commit metadata, and remote SHA. Push
  only the intended branch after every check passes.

## Plan self-review

- Scope coverage: each approved design area has an implementation task and
  an acceptance command.
- Completeness scan: every implementation step has a concrete file, command,
  expected result, or explicit safety boundary.
- Interface consistency: tests use the current fixtures and public repository/
  service method names; deployment uses the existing app entrypoint and ports.
- Safety: asset docs remain reference-only and deployment templates contain no
  provider secrets.
