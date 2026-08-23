# U.Perfect Project Documentation / สารบัญเอกสารโครงการ

This is the documentation map for the U.Perfect Social Commerce OS. It records
what is runnable locally, what is intentionally gated, and where each role
should start.

นี่คือแผนผังเอกสารของ U.Perfect Social Commerce OS ใช้แยกสิ่งที่รันได้ใน local
ออกจากสิ่งที่ยังต้องขอสิทธิ์และตรวจสอบกับ provider ภายนอก

## Start here / เริ่มจากตรงนี้

| Audience | Thai/English guide | Use it for |
| --- | --- | --- |
| Shop user | [USER-MANUAL.md](USER-MANUAL.md) | Daily inbox, assets, orders, language switch |
| Admin/owner | [ADMIN-MANUAL.md](ADMIN-MANUAL.md) | Provider gates, catalog, review, operations |
| Developer | [DEV-MANUAL.md](DEV-MANUAL.md) | Code, API, tests, adapters, release |
| Everyone | [README.md](README.md) | Quick start and release boundary |

## Project documents / เอกสารโครงการ

- [Architecture / สถาปัตยกรรม](docs/ARCHITECTURE.md)
- [API contract / สัญญา API](docs/API.md)
- [Schema migrations](migrations/002_notification_outbox_retry.sql)
- [Dashboard i18n / ระบบสองภาษา](docs/I18N.md)
- [Operations / ปฏิบัติการ](docs/OPERATIONS.md)
- [Deployment / การ deploy](docs/DEPLOYMENT.md)
- [Deployment templates / แม่แบบ deploy](deploy/README.md)
- [Product and chatbot assets / สินค้าและ asset แชท](docs/ASSET-CATALOG.md)
- [Release checklist / เช็กลิสต์ release](docs/RELEASE-CHECKLIST.md)
- [Thai API onboarding](docs/integrations/API_ONBOARDING_TH.md)
- [English API onboarding](docs/integrations/API_ONBOARDING_EN.md)
- [Thai provider approval form](docs/integrations/PROVIDER-APPROVAL-FORM_TH.md)
- [English provider approval form](docs/integrations/PROVIDER-APPROVAL-FORM_EN.md)
- [Integration index](docs/integrations/README.md)
- [Final release report](u_perfect_final_release_report.md)
- [Changelog](CHANGELOG.md)
- [Security](SECURITY.md)
- [Contribution rules](CONTRIBUTING.md)

## GitHub documents / เอกสาร GitHub

- [GitHub workflow](.github/README.md)
- [GitHub Actions CI](.github/workflows/ci.yml)
- [Pull request template](.github/PULL_REQUEST_TEMPLATE.md)
- [Bug report](.github/ISSUE_TEMPLATE/bug_report.md)
- [Feature request](.github/ISSUE_TEMPLATE/feature_request.md)
- [Integration request](.github/ISSUE_TEMPLATE/integration_request.md)
- [Documentation request](.github/ISSUE_TEMPLATE/documentation_request.md)

## Release truth / สถานะ release

- Local FastAPI + PWA: runnable and tested.
- Notification worker: separate local process with leased outbox delivery and
  retry/backoff; dormant until LINE server configuration exists.
- SQLite migration metadata: `schema_migrations` version 2 is additive and
  rerunnable; PostgreSQL parity is in `migrations/`.
- CI workflow: compile, pytest, and whitespace checks are defined.
- Docker Compose/Nginx: templates exist; systemd remains the current local
  runtime owner.
- SQLite local persistence: active runtime boundary.
- Product memory and sales assets: validated from local files.
- TH/EN Dashboard: language switch and bilingual API guide links are implemented.
- Local AI: only configured when Ollama at `192.168.74.130:11434` exposes
  `zCoder:latest`.
- Facebook, TikTok Shop, Shopee, LINE, n8n, and Gemini: deployment gates until
  account-owner credentials and official verification exist. The normalized
  webhook route requires provider-specific HMAC but is not a live provider
  adapter.
- ZIP export: canceled; no archive is generated or published.

## Evidence commands / คำสั่งหลักฐาน

```bash
.venv/bin/python -m pytest -q
.venv/bin/python -m compileall -q app scripts tests
node --check web/app.js
docker compose -f deploy/docker-compose.yml config
curl http://192.168.74.130:18765/api/health
curl http://192.168.74.130:18765/api/integrations
```

Local health, public routing, and provider verification are separate claims and
must be recorded separately.
