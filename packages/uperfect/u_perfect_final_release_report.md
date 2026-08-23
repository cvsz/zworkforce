# U.Perfect Social Commerce OS - Final Release Report

**Release:** `v1.0.0-local-final`
**Date:** 10 August 2026
**Brand:** U.Perfect
**Channels in scope:** Facebook Messenger, TikTok Shop, Shopee, LINE outbox
**Notification destination:** LINE outbox
**Client:** responsive installable PWA for Android, iOS, Windows, and desktop browsers

## Release position

This release is a runnable local product core and admin PWA. ZIP export is
canceled; no archive is generated or published. This is not a claim that the
external channels are live. All provider statuses start as
`unconfigured` until server-side credentials and official webhook checks are
completed by the account owner.

The deployed local-only profile is bound to `192.168.74.130`: U.Perfect listens
on `192.168.74.130:18765`, and the no-cost Ollama connector probes
`http://192.168.74.130:11434/api/tags` for `zCoder:latest`. No external model key
is used.

## File-by-file inventory

| File or directory | Purpose | Evidence/status |
| --- | --- | --- |
| `app/main.py` | FastAPI factory, database initialization, service wiring, static PWA routes | Local runtime |
| `app/config.py` | Environment-only configuration with secret-safe representation | Local tests |
| `app/database.py` | SQLite schema, migration hook, transaction boundary, exact currency binding | Local runtime |
| `app/schemas.py` | Domain values, stable errors, integration/order DTOs | Unit/API tests |
| `app/seed.py` | U.Perfect merchant-provided catalog facts and aliases | Catalog tests |
| `app/repositories.py` | SQLite persistence, idempotency, inventory, audit, outbox | Domain tests |
| `app/services/catalog.py` | Product and keyword memory lookup | Verified locally |
| `app/services/conversations.py` | Intent rules, active-product context, safe replies, takeover | Verified locally |
| `app/services/sales_assets.py` | Validated bilingual TH/EN response and local-media loader | Asset/API tests |
| `app/settings.py` | Safe workspace setting defaults and public setting contract | Verified locally |
| `app/services/orders.py` | Promotion totals, inventory reserve, payment review, transitions | Verified locally |
| `app/services/integrations.py` | Provider status truth and webhook deduplication boundary | Verified locally |
| `app/services/settings.py` | Persisted workspace preferences and Autobot policy provider | Verified locally |
| `app/services/notifications.py` | Retryable LINE notification outbox | Verified locally |
| `app/migrations.py` | Additive SQLite schema version runner through v2 | Migration tests |
| `app/services/line.py` | Server-only LINE push transport with masked failure messages | Worker tests |
| `app/services/webhook_auth.py` | Provider-specific HMAC verification over raw request bytes | Security tests |
| `app/worker.py` | Separate leased notification polling worker | Worker tests |
| `migrations/002_notification_outbox_retry.sql` | PostgreSQL parity for outbox lease/retry columns | Schema review |
| `deploy/systemd/uperfect.service` | LAN binding and local Ollama environment | Active service |
| `deploy/systemd/uperfect-worker.service` | Separate notification worker unit | Static contract test |
| `deploy/Dockerfile` | Non-root Python 3.12 container template | Static contract test |
| `deploy/docker-compose.yml` | Local-only Compose template with SQLite volume and health check | Compose config validated |
| `deploy/nginx/uperfect.conf.example` | Optional `uperfect.zeaz.dev` reverse-proxy template | Static contract test |
| `deploy/README.md` | TH/EN deployment instructions and ownership boundary | Documentation |
| `app/api.py` | JSON routes for dashboard, catalog, inbox, orders, integrations, webhooks | API tests |
| `web/index.html` | Semantic dashboard shell and TH/EN controls | PWA tests |
| `web/styles.css` | Responsive operational UI for mobile/desktop | Browser smoke target |
| `web/app.js` | API-driven overview, inbox, memory, orders, Skills, Agents, n8n, Channels, Sales Assets, Settings, TH/EN i18n | Node syntax + browser target |
| `web/manifest.webmanifest` | Standalone PWA install metadata | PWA test |
| `web/service-worker.js` | Static shell cache only; no API mutation caching | Source audit |
| `database_schema.sql` | PostgreSQL deployment schema plus safe catalog seed | Schema audit |
| `.env.example` | Secret names with empty values only | Secret audit |
| `assets/chatbot/sales_response_assets.json` | TH/EN intents, objections, selling points, and closing CTAs | Validated locally |
| `assets/chatbot/asset-manifest.json` | Local product media manifest and asset policy | Validated locally |
| `assets/loe_soap/` and canonical product asset directories | Normalized local media paths and bilingual soap reference | Manifest test |
| `docs/integrations/API_ONBOARDING_TH.md` | Full Thai provider setup guide | Documentation |
| `docs/integrations/API_ONBOARDING_EN.md` | Full English provider setup guide | Documentation |
| `docs/integrations/PROVIDER-APPROVAL-FORM_TH.md` | Thai owner approval/evidence workbook | Documentation; no secrets |
| `docs/integrations/PROVIDER-APPROVAL-FORM_EN.md` | English owner approval/evidence workbook | Documentation; no secrets |
| `USER-MANUAL.md` | Daily user workflow in TH/EN | Documentation |
| `ADMIN-MANUAL.md` | Owner/admin/provider/review workflow in TH/EN | Documentation |
| `DEV-MANUAL.md` | Runtime, API, i18n, assets, testing, and release workflow in TH/EN | Documentation |
| `PROJECT-DOCUMENTATION.md` and `docs/` | Project map, architecture, API, operations, assets, i18n, release checklist | Documentation |
| `.github/` | TH/EN contribution, PR, bug, feature, integration, and docs templates | GitHub workflow |
| `.github/workflows/ci.yml` | Compile, pytest, and whitespace checks on push/PR | Static contract test |
| `docs/DEPLOYMENT.md` | Local service, Cloudflare/Terraform ownership, public-route verification, and rollback boundary | Documentation; infrastructure is managed outside this repo |
| `scripts/package_release.py` | Unused local packaging helper retained outside runtime deployment | Not executed; ZIP export canceled |
| `tests/` | Unit, API, integration, migration, worker, frontend-contract, E2E, PWA, and package regression coverage | `pytest -q` |
| `tests/test_asset_manifest.py` and `tests/test_ci_and_deploy.py` | Canonical asset and deployment contract coverage | Focused tests |
| `export-manifest.json` | Original TikTok public retrieval boundary | CAPTCHA status recorded |

## Product memory

The seed has two canonical products from the supplied brief:

1. **Loe VIT C Aura Serum, 200 ml** with two TikTok source listings,
   eight highlighted ingredients, full supplied INCI list, seller name,
   usage/warning, aliases, and the brief price/promotion values marked for
   verification before live checkout.
2. **น้ำพริกเสือร้องไห้ / Mala Chili Oil, 200 g** with its supplied listing,
   ingredients, vegan wording, storage guidance, and peanut allergy warning.
   No price is stored because the brief did not provide one.

TikTok product media was not exported from the public listing pages. The public
export returned Security Check CAPTCHA for each requested listing; CAPTCHA
images are not product assets and were excluded. Separately, supplied local
merchant media in `assets/` is included and served only under the local asset
manifest policy.

## Dashboard i18n and sales behavior

The Dashboard defaults to Thai and supports English across navigation, titles,
status labels, forms, provider guide links, and the Sales Assets view. The
response pack uses a friendly, cute admin voice with one clear closing CTA, but
keeps unpriced/reference-only products in admin review and includes sensitive-
skin patch-test guidance.

Product media directories referenced by the manifest are normalized to ASCII
lowercase underscore names. `LOE_CHARCOAL_SOAP` now has a bilingual
reference-only document and image path; price, stock, and final claims remain
admin-verification requirements.

The runtime endpoints are `GET /api/sales-assets`, `GET /api/integration-guides`,
`/assets/`, and `/guides/`. These routes expose no credential values. The
approval workbooks record only non-secret identifiers and redacted evidence.

## Safety and external gates

- The bot uses deterministic keyword and intent rules. It does not invent a
  product, price, shipping fee, medical outcome, or payment approval.
- Human takeover prevents an automated outbound reply for the active session.
- Payment evidence moves an order to `pending_review`; only an authorized
  transition can move it to `confirmed` and then `fulfilled`.
- Facebook, LINE, TikTok Shop, and Shopee normalized webhooks require
  provider-specific HMAC over the exact raw body and event idempotency.
  Credentials never enter the browser or generated artifacts.
- Confirmed orders create a retryable LINE outbox event. A separate worker claims
  it with a lease and bounded backoff; delivery remains visible when LINE is
  unconfigured or transport fails.
- n8n post/comment/schedule and Auto Update views are present as explicit
  deployment-gated workflows, not fabricated live automation.
- The no-cost local profile does not enable Gemini, LINE inbound, n8n, Facebook,
  TikTok Shop, or Shopee without their official credentials and verification.
- External provider callbacks cannot target the private LAN host directly; a
  public HTTPS adapter with provider-specific signature/state validation is a
  separate deployment gate.
- LINE July 2026 news was reviewed in the bilingual onboarding guides. LIFF,
  rich-menu statistics, and LINE MINI App IAP are outside this release; any
  future LINE sender must preserve outbox idempotency and provider retry rules.

## Verification record

Run from the project root:

```bash
.venv/bin/python -m pytest -q
.venv/bin/python -m compileall -q app scripts tests
node --check web/app.js
.venv/bin/python -m pytest -q tests/test_ci_and_deploy.py
docker compose -f deploy/docker-compose.yml config
git diff --check
```

Local tests establish the product-memory, conversation, order, PWA, migration,
leased worker, signed webhook boundary, API-path E2E, settings persistence,
Autobot policy, and sales asset behavior.
The live LAN smoke check establishes `local_ai=configured`; public
`https://uperfect.zeaz.dev` also returns the same status through Cloudflare.
Live channel delivery, LINE delivery, payment verification, n8n execution, and
external model providers remain account-owner deployment gates.
