# U.Perfect Audit Remediation Design

> Historical design note. The final canonical asset consolidation is documented
> in `2026-08-10-scrutinize-hardening-design.md` and moves all VIT C media under
> `assets/loe_vit_c_aura_serum/`.

**Date:** 2026-08-10

**Status:** Approved for implementation

## Goal

Close the repository audit gaps for unit-test coverage, canonical product asset
paths, GitHub automation, and optional container/reverse-proxy deployment while
preserving U.Perfect's local-only, fact-bound runtime contract.

## Current findings

- `app/services/notifications.py` and `app/services/settings.py` have no direct
  service tests.
- `app/schemas.py` and `app/repositories.py` have no direct unit-test modules.
- The reported `assets/ /` path is not present in the current checkout. The
  Mala Chili Oil files are in `assets/น้ำพริกเสือร้องไห้/` and are already
  referenced by `assets/chatbot/asset-manifest.json`.
- `LOE_CHARCOAL_SOAP` has a reference image in the serum directory but no
  product-specific asset directory or bilingual product reference files.
- `.github/` has issue and pull-request templates but no workflow.
- `deploy/systemd/uperfect.service` exists, but container and reverse-proxy
  templates are absent.

## Design principles

1. Preserve existing public service interfaces and SQLite behavior.
2. Test behavior through real repository/service objects and the existing test
   fixtures; use mocks only for the notification transport boundary.
3. Normalize all manifest product paths to ASCII, lowercase,
   underscore-separated directory names.
4. Do not invent prices, stock, shipping, product efficacy, provider approval,
   or credential values.
5. Keep provider integrations unconfigured until an account owner supplies
   approved server-side credentials and evidence.
6. Keep the no-cost local runtime on `192.168.74.130`; Docker binds inside the
   container to `0.0.0.0` and publishes only to the host LAN address.

## File plan

### Test modules

Create:

- `tests/test_notifications.py`: enqueue, successful delivery, retryable
  failure, pending listing, and delivery summary behavior.
- `tests/test_settings.py`: default merge, persisted update, immutable
  Facebook reference URL, and rejection of unknown settings.
- `tests/test_schemas.py`: domain error metadata, decimal conversion/JSON
  serialization, timestamp-safe dataclass defaults, and invalid JSON fallback.
- `tests/test_repositories.py`: product lookup/save, conversation persistence,
  order/inventory behavior, workspace settings persistence, notification
  outbox state changes, and webhook idempotency.

The tests will use `tests/conftest.py`'s temporary SQLite database and service
fixtures. Each new test module will first be written in a failing state and
then made green without changing production behavior unless the test exposes a
real defect.

### Canonical assets

Rename all product directories referenced by the manifest:

- `assets/น้ำพริกเสือร้องไห้/` to
  `assets/suea_rong_hai_mala_chili_oil/`.
- `assets/VIT C AURA SERUM/` to `assets/loe_vit_c_aura_serum/`.
- `assets/VIT C AURA BODY SERUM/` to `assets/loe_vit_c_aura_body_serum/`.
- `assets/the copper/` to `assets/the_copper/`.

Move and add:

- Move the existing
  `707931534_10165024508616122_6595834135060529509_n.jpg` reference image to
  `assets/loe_soap/`.
- Add `assets/loe_soap/LOE_Charcoal_Mud_Soap_TH.md` and
  `assets/loe_soap/LOE_Charcoal_Mud_Soap_EN.md` as reference-only facts. The
  documents will state that price and stock are unverified.

Update:

- `assets/chatbot/asset-manifest.json` to use the canonical paths and reject
  spaces or non-ASCII product directory names.
- `assets/chatbot/sales_response_assets.json` if any product asset path or
  asset identifier needs synchronization.
- `docs/ASSET-CATALOG.md` with canonical directories, Mala documentation, and
  the soap reference directory.
- Asset tests to assert every manifest file exists, no manifest path contains
  the old Thai directory, and the canonical product directories are present.

No image will be downloaded or generated for this remediation. Existing local
media will be preserved and only moved to its canonical owner directory.

### GitHub Actions

Create `.github/workflows/ci.yml` with:

- `actions/checkout@v4`
- `actions/setup-python@v5` using Python 3.12
- pip cache keyed by `requirements-dev.txt`
- installation from `requirements-dev.txt`
- `python -m compileall -q app scripts`
- `pytest -q`
- `git diff --check`

The workflow will not request provider credentials or access external APIs.

### Deployment templates

Create:

- `deploy/Dockerfile`: Python 3.12 slim image, dependency installation,
  non-root runtime user, application files, and Uvicorn on port 18765.
- `deploy/docker-compose.yml`: builds the image from the repository root,
  mounts a named SQLite data volume, publishes
  `192.168.74.130:18765:18765`, configures local-only mode and the LAN Ollama
  endpoint, and includes a local healthcheck.
- `deploy/nginx/uperfect.conf.example`: optional HTTPS reverse-proxy template
  for `uperfect.zeaz.dev`, with placeholder certificate paths and proxy headers.
- `deploy/README.md`: Thai/English instructions for systemd, Docker Compose,
  Nginx, LAN binding, health checks, rollback, and the distinction between a
  template and a live provider/public deployment.

The container command binds to `0.0.0.0` only inside the container. The Compose
port mapping is the LAN boundary. No Cloudflare, marketplace, LINE, n8n, or
Gemini credential is placed in the image or Compose file.

## Error and safety behavior

- Existing domain errors and stable API error codes remain unchanged.
- Notification sender failures remain pending and retain an error for retry.
- Unknown workspace settings remain rejected.
- Unpriced products remain unavailable for order creation.
- Asset paths are validated at test time and served only from the local asset
  root.
- Deployment templates document required external TLS/provider setup but do not
  claim it is configured.

## Verification contract

The implementation is complete only when all of the following are true:

1. The four new test modules exist and cover the listed behavior.
2. The full test suite passes.
3. `compileall`, JavaScript syntax checks, and `git diff --check` pass.
4. Every asset-manifest path resolves to a tracked file.
5. No canonical manifest path contains a blank or Unicode product directory.
6. CI YAML parses and contains the required test/check commands.
7. Dockerfile and Compose files contain no credentials and pass static syntax
   checks available in the environment.
8. The local systemd service remains active and the health endpoint returns
   `{"status":"ok","brand":"U.Perfect"}`.
9. The release documentation identifies the new files and does not claim
   provider approval or live marketplace connectivity.
