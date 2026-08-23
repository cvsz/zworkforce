# U.Perfect Social Commerce OS

U.Perfect Social Commerce OS is a locally runnable FastAPI + PWA operations
workspace for product memory, cross-channel chat workflows, order review, and
LINE notification outbox management.

The dashboard is Thai-first with a complete TH/EN switch across navigation,
operational views, Sales Assets, status labels, and provider guides. It has
responsive layouts for Android, iOS, Windows, and desktop browsers. The local implementation uses
SQLite. A PostgreSQL schema is provided for deployment; a Redis-backed session
store and provider adapters remain deployment boundaries rather than fake local
connections.

## Manuals and documentation

- [User manual / คู่มือผู้ใช้](USER-MANUAL.md)
- [Admin manual / คู่มือผู้ดูแล](ADMIN-MANUAL.md)
- [Developer manual / คู่มือนักพัฒนา](DEV-MANUAL.md)
- [Project documentation map](PROJECT-DOCUMENTATION.md)
- [Thai API onboarding](docs/integrations/API_ONBOARDING_TH.md)
- [English API onboarding](docs/integrations/API_ONBOARDING_EN.md)
- [Thai provider approval form](docs/integrations/PROVIDER-APPROVAL-FORM_TH.md)
- [English provider approval form](docs/integrations/PROVIDER-APPROVAL-FORM_EN.md)
- [GitHub workflow and templates](.github/README.md)
- [Deployment templates](deploy/README.md)

## Run locally

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements-dev.txt
.venv/bin/uvicorn app.main:app --host 192.168.74.130 --port 18765
```

Open <http://192.168.74.130:18765/>. The default database is `uperfect.db`;
set `UPERFECT_DATABASE_PATH` for another location. Copy `.env.example` to a
deployment-only environment source and fill values outside this repository.

For a persistent local service, install `deploy/systemd/uperfect.service` and
`deploy/systemd/uperfect-worker.service` as user units and enable both with:

```bash
systemctl --user daemon-reload
systemctl --user enable --now uperfect.service uperfect-worker.service
```

## Local capabilities

- Product Memory: deterministic Thai/English aliases, ingredient summaries,
  source listing links, and merchant-editable catalogue records.
- Unified Inbox: Facebook, TikTok Shop, and Shopee conversation shape with
  active-product context and persisted human takeover.
- Safe closing: price and promotion replies are bound to catalog facts;
  payment evidence remains `pending_review` until an authorized reviewer acts.
- Orders: inventory reservation, promotion totals, explicit status transitions,
  audit events, and a leased LINE notification outbox delivered by the separate
  worker when LINE is configured.
- Persistence: additive SQLite schema migrations are recorded in
  `schema_migrations`; the PostgreSQL parity migration is under `migrations/`.
- Skills and Agents: visible runtime scopes for memory, safe closing, takeover,
  LINE, and n8n content workflows.
- Settings: server-persisted store profile, TH/EN default language, timezone,
  assistant tone, Autobot enablement, takeover timeout, n8n preferences, and
  LINE/payment-review notifications. Credentials and secrets are excluded.
- Local-only runtime: U.Perfect binds to `192.168.74.130:18765` and probes the
  no-cost Ollama endpoint at `192.168.74.130:11434` for `zCoder:latest`. The
  Settings page shows the live model status without exposing any key.
- Sales Assets: validated TH/EN intents, objection replies, closing CTAs, and
  local product media are served from `/api/sales-assets` and `/assets/`.
- API onboarding: `/api/integration-guides` links the full TH/EN setup guides
  and provider approval workbooks for Facebook Messenger, TikTok Shop, Shopee,
  and LINE.
- PWA shell: manifest and service worker cache only static shell files; API
  mutations are never cached.

## Product source boundary

The supplied merchant brief contains three TikTok listing URLs. The public
unauthenticated export recorded all three as blocked by TikTok Shop Security
Check CAPTCHA, so the project does not claim to have exported product media.
The application stores the supplied listing URLs and merchant text facts only.

The local seed contains two canonical products and three source listings:

| Canonical product | Source listings | Price state |
| --- | --- | --- |
| Loe VIT C Aura Serum, 200 ml | `1736533886654383714`, `1736534222483654242` | `98 THB` and brief promotion `2 for 169 THB`; verify before live checkout |
| น้ำพริกเสือร้องไห้ / Mala Chili Oil, 200 g | `1736721811552831074` | Not supplied; no price is invented |

The serum ingredient panel records the eight highlighted ingredients and the
full INCI list supplied in the brief. Product wording is merchant-provided and
does not make medical or guaranteed-result claims.

## Integration gates

Facebook Messenger, TikTok Shop, Shopee, LINE Messaging API, n8n, payment
verification, and Gemini remain deployment gates because no official
credentials or local service were supplied. The local Ollama connector is the
only configured AI provider and is restricted to `192.168.74.130`. The browser
never receives credential values. The normalized webhook boundary requires a
provider-specific HMAC over the exact raw body; raw provider adapters must
validate their own signatures/state before normalization, and duplicate event
IDs are ignored.

The response pack is friendly and sales-oriented, but it remains fact-bound:
unpriced products stay in admin review, sensitive-skin replies include patch-test
guidance, and payment evidence stays pending until authorized confirmation.

The Facebook page reference supplied by the merchant is
<https://www.facebook.com/spookyuperfect>. It is shown as a reference link,
not as proof of an active API connection.

## Tests and archive policy

```bash
.venv/bin/python -m pytest -q
.venv/bin/python -m compileall -q app scripts tests
node --check web/app.js
docker compose -f deploy/docker-compose.yml config
```

GitHub Actions repeats the compile, test, and whitespace checks from
`.github/workflows/ci.yml`. Docker and Nginx templates are optional deployment
artifacts under `deploy/`; the systemd unit remains the current local runtime.

ZIP export is canceled for this release: no archive is generated or
published. The unused local packaging helper remains outside the runtime path.
See `u_perfect_final_release_report.md` for the file-by-file release audit and
the distinction between locally verified behavior and deployment gates.
